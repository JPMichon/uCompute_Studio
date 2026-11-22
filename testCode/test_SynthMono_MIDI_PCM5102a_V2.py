import math
import time
import _thread
import machine
from machine import Pin, UART, I2S

machine.freq(133000000)

# --- 1. Configuration Matérielle (uCompute-Studio) ---
BCK_PIN = 17
LCK_PIN = 18
DIN_PIN = 16
SAMPLE_RATE = 32000

audio_out = I2S(
    0,
    sck=Pin(BCK_PIN),
    ws=Pin(LCK_PIN),
    sd=Pin(DIN_PIN),
    mode=I2S.TX,
    bits=16,
    format=I2S.STEREO,
    rate=SAMPLE_RATE,
    ibuf=2048
)

midi_uart = UART(0, baudrate=31250, bits=8, parity=None, stop=1, rx=Pin(1))

# --- 2. Deux Tables d'ondes pour la modulation de timbre ---
# Table 1 : Son très doux et rond (sinusoïde pure)
WAVE_SOFT = bytearray(256)
# Table 2 : Son brillant et riche en harmoniques (type Piano électrique / Clavecin doux)
WAVE_BRIGHT = bytearray(256)

for i in range(256):
    angle = 2.0 * math.pi * (i / 256.0)
    
    # Onde douce : 100% fondamentale
    val_soft = int(115 * math.sin(angle))
    WAVE_SOFT[i] = val_soft & 0xFF
    
    # Onde brillante : fondamentale + harmoniques 2, 3 et 4 dosées musicalement
    onde_br = (
        0.55 * math.sin(angle) +
        0.25 * math.sin(2.0 * angle) +
        0.13 * math.sin(3.0 * angle) +
        0.07 * math.sin(4.0 * angle)
    )
    val_bright = int(115 * onde_br)
    WAVE_BRIGHT[i] = val_bright & 0xFF

MIDI_INCS = [int((440.0 * (2.0 ** ((n - 69) / 12.0)) * 65536) / SAMPLE_RATE) for n in range(128)]

# --- 3. Dictionnaire d'état partagé entre Core 0 et Core 1 ---
etat_synth = {
    "actif": True,
    "sr": SAMPLE_RATE,
    "wave_soft": WAVE_SOFT,
    "wave_bright": WAVE_BRIGHT,
    "audio": audio_out,
    "inc_base": 0,
    "inc_final": 0,
    "gain_cible": 0,
    "brillance": 0,       # 0 (doux) à 128 (brillant maximal) selon la vélocité
    "pitch_mult": 1.0,
    "mod_profondeur": 0.0,
    "lfo_phase": 0.0
}

notes_tenues = []

def recalculer_frequence(st):
    if st["inc_base"] == 0:
        st["inc_final"] = 0
        return
    vibrato = 1.0 + (st["mod_profondeur"] * 0.035 * math.sin(st["lfo_phase"]))
    st["inc_final"] = int(st["inc_base"] * st["pitch_mult"] * vibrato)

# --- 4. Moteur Audio Temps Réel (@micropython.viper) avec Morphing de Timbre ---
@micropython.viper
def generer_bloc_audio(buf_ptr: ptr16, nb_samples: int,
                       tbl_soft: ptr8, tbl_bright: ptr8,
                       inc: int, targ: int, cur: int,
                       brillance: int, phase: int) -> int:
    # brillance va de 0 à 128 : mixage proportionnel entre WAVE_SOFT et WAVE_BRIGHT
    mix_soft: int = 128 - brillance
    mix_bright: int = brillance

    i: int = 0
    while i < nb_samples:
        if (i & 15) == 0:
            if cur < targ:
                cur += 5
                if cur > targ:
                    cur = targ
            elif cur > targ:
                cur -= 1
                if cur < targ:
                    cur = targ

        phase = (phase + inc) & 0xFFFF
        pos: int = phase >> 8

        # Lecture des deux tables d'ondes
        s_soft: int = tbl_soft[pos]
        if s_soft > 127:
            s_soft -= 256

        s_bright: int = tbl_bright[pos]
        if s_bright > 127:
            s_bright -= 256

        # Morphing dynamique du timbre (division par 128 via décalage >> 7)
        s_mix: int = ((s_soft * mix_soft) + (s_bright * mix_bright)) >> 7

        out: int = s_mix * cur

        idx: int = i << 1
        buf_ptr[idx] = out
        buf_ptr[idx + 1] = out
        i += 1

    return (cur << 16) | phase

def thread_audio(st, fn_viper, fn_recalc):
    CHUNK = 128
    buf = bytearray(CHUNK * 4)
    cur = 0
    phase = 0
    sr = st["sr"]
    w_soft = st["wave_soft"]
    w_bright = st["wave_bright"]
    out_dev = st["audio"]
    lfo_step = (2.0 * math.pi * 5.5 * CHUNK) / sr
    deux_pi = 2.0 * math.pi

    while st["actif"]:
        if st["mod_profondeur"] > 0.0 and st["inc_base"] > 0:
            st["lfo_phase"] = (st["lfo_phase"] + lfo_step) % deux_pi
            fn_recalc(st)

        res = fn_viper(buf, CHUNK, w_soft, w_bright,
                       st["inc_final"], st["gain_cible"], cur,
                       st["brillance"], phase)
        cur = (res >> 16) & 0xFFFF
        phase = res & 0xFFFF
        out_dev.write(buf)

# --- 5. Gestionnaire MIDI (Core 0) ---
def note_on(note, velocite):
    ratio = velocite / 127.0

    # 1. Volume : courbe dynamique progressive (de 20 à 230)
    gain = int((ratio ** 1.5) * 230)
    if gain < 20:
        gain = 20

    # 2. Brillance (timbre) : de 0 (son pur) à 128 (son riche en harmoniques)
    brill = int((ratio ** 1.8) * 128)
    if brill > 128:
        brill = 128

    if note in notes_tenues:
        notes_tenues.remove(note)
    notes_tenues.append(note)

    etat_synth["inc_base"] = MIDI_INCS[note]
    recalculer_frequence(etat_synth)
    etat_synth["brillance"] = brill
    etat_synth["gain_cible"] = gain

def note_off(note):
    if note in notes_tenues:
        notes_tenues.remove(note)

    if len(notes_tenues) > 0:
        note_precedente = notes_tenues[-1]
        etat_synth["inc_base"] = MIDI_INCS[note_precedente]
        recalculer_frequence(etat_synth)
    else:
        etat_synth["gain_cible"] = 0

# --- 6. Démarrage ---
print("=== Synthétiseur Expressif (Vélocité -> Volume & Brillance) ===")
_thread.start_new_thread(thread_audio, (etat_synth, generer_bloc_audio, recalculer_frequence))

status_courant = 0
data_buffer = []

try:
    while True:
        if midi_uart.any():
            octets = midi_uart.read()

            for b in octets:
                if b >= 0xF8:
                    continue

                if b & 0x80:
                    status_courant = b
                    data_buffer = []
                else:
                    data_buffer.append(b)
                    cmd = status_courant & 0xF0

                    if cmd in (0x80, 0x90, 0xA0, 0xB0, 0xE0) and len(data_buffer) == 2:
                        d1, d2 = data_buffer
                        data_buffer = []

                        if cmd == 0x90 and d2 > 0:
                            note_on(d1, d2)
                        elif cmd == 0x80 or (cmd == 0x90 and d2 == 0):
                            note_off(d1)
                        elif cmd == 0xB0 and d1 == 1:
                            etat_synth["mod_profondeur"] = d2 / 127.0
                            recalculer_frequence(etat_synth)
                        elif cmd == 0xE0:
                            valeur_14bit = (d2 << 7) | d1
                            demi_tons = ((valeur_14bit - 8192) / 8192.0) * 2.0
                            etat_synth["pitch_mult"] = 2.0 ** (demi_tons / 12.0)
                            recalculer_frequence(etat_synth)

                    elif cmd in (0xC0, 0xD0) and len(data_buffer) == 1:
                        data_buffer = []

        time.sleep_ms(1)

except KeyboardInterrupt:
    print("\nArrêt du synthétiseur...")
finally:
    etat_synth["actif"] = False
    time.sleep_ms(50)
    audio_out.deinit()
