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

# --- 2. Table d'onde PURE (Sinusoïde douce type Piano Électrique / Rhodes) ---
WAVE_TABLE = bytearray(256)
for i in range(256):
    angle = 2.0 * math.pi * (i / 256.0)
    onde = (0.85 * math.sin(angle)) + (0.15 * math.sin(2.0 * angle))
    val = int(115 * onde)
    WAVE_TABLE[i] = val & 0xFF

MIDI_INCS = [int((440.0 * (2.0 ** ((n - 69) / 12.0)) * 65536) / SAMPLE_RATE) for n in range(128)]

# --- 3. Dictionnaire d'état partagé entre Core 0 et Core 1 ---
etat_synth = {
    "actif": True,
    "sr": SAMPLE_RATE,
    "wave": WAVE_TABLE,
    "audio": audio_out,
    "inc_base": 0,
    "inc_final": 0,
    "gain_cible": 0,
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

# --- 4. Moteur Audio Temps Réel (@micropython.viper) ---
@micropython.viper
def generer_bloc_audio(buf_ptr: ptr16, nb_samples: int, tbl: ptr8, inc: int, targ: int, cur: int, phase: int) -> int:
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

        s: int = tbl[phase >> 8]
        if s > 127:
            s -= 256

        out: int = s * cur

        idx: int = i << 1
        buf_ptr[idx] = out
        buf_ptr[idx + 1] = out
        i += 1

    return (cur << 16) | phase

def thread_audio(st, fn_viper, fn_recalc):
    """Boucle audio autonome sur Core 1 (aucune dépendance globale)"""
    CHUNK = 128
    buf = bytearray(CHUNK * 4)
    cur = 0
    phase = 0
    sr = st["sr"]
    wave = st["wave"]
    out_dev = st["audio"]
    lfo_step = (2.0 * math.pi * 5.5 * CHUNK) / sr
    deux_pi = 2.0 * math.pi

    while st["actif"]:
        if st["mod_profondeur"] > 0.0 and st["inc_base"] > 0:
            st["lfo_phase"] = (st["lfo_phase"] + lfo_step) % deux_pi
            fn_recalc(st)

        res = fn_viper(buf, CHUNK, wave, st["inc_final"], st["gain_cible"], cur, phase)
        cur = (res >> 16) & 0xFFFF
        phase = res & 0xFFFF
        out_dev.write(buf)

# --- 5. Gestionnaire MIDI (Core 0) ---
def note_on(note, velocite):
    gain = int((velocite / 127.0) * 220)
    if gain < 25:
        gain = 25

    if note in notes_tenues:
        notes_tenues.remove(note)
    notes_tenues.append(note)

    etat_synth["inc_base"] = MIDI_INCS[note]
    recalculer_frequence(etat_synth)
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
print("=== Synthétiseur Monophonique Pur + Pitch & Mod Wheel ===")
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
