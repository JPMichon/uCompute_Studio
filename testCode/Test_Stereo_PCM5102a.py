import math
import struct
import machine
from machine import Pin, I2S

machine.freq(133000000)

# --- 1. Configuration des broches (selon votre PCB) ---
BCK_PIN = 17
LCK_PIN = 18
DIN_PIN = 16

SAMPLE_RATE = 44100
VOLUME = 0.28

audio_out = I2S(
    0,
    sck=Pin(BCK_PIN),
    ws=Pin(LCK_PIN),
    sd=Pin(DIN_PIN),
    mode=I2S.TX,
    bits=16,
    format=I2S.STEREO,
    rate=SAMPLE_RATE,
    ibuf=4096
)

# Tables d'ondes en bytearray signé (compatibles Viper)
WAVE_SQUARE = bytearray(256)
WAVE_TRI = bytearray(256)
for i in range(256):
    sq = 100 if i < 128 else -100
    tr = int(100 * (1.0 - 4.0 * abs(round(i / 256 - 0.25) - (i / 256 - 0.25))))
    WAVE_SQUARE[i] = sq & 0xFF
    WAVE_TRI[i] = tr & 0xFF

@micropython.viper
def remplir_buffer_viper(buf_ptr: ptr16, nb_samples: int,
                         inc1: int, inc2: int, inc3: int,
                         tbl1: ptr8, tbl2: ptr8, tbl3: ptr8,
                         gain: int):
    """Génère tout le buffer stéréo en code machine ARM natif (ultra-rapide)"""
    p1_g: int = 0
    p1_d: int = 0
    p2_g: int = 0
    p2_d: int = 0
    p3_g: int = 0
    p3_d: int = 0

    inc1_d: int = inc1 + 4
    inc2_d: int = inc2 + 6
    inc3_d: int = inc3 + 8

    i: int = 0
    while i < nb_samples:
        p1_g = (p1_g + inc1) & 0xFFFF
        p1_d = (p1_d + inc1_d) & 0xFFFF
        p2_g = (p2_g + inc2) & 0xFFFF
        p2_d = (p2_d + inc2_d) & 0xFFFF
        p3_g = (p3_g + inc3) & 0xFFFF
        p3_d = (p3_d + inc3_d) & 0xFFFF

        # Lecture signée dans les tables d'ondes
        v1_g: int = tbl1[p1_g >> 8]
        if v1_g > 127: v1_g -= 256
        v1_d: int = tbl1[p1_d >> 8]
        if v1_d > 127: v1_d -= 256

        v2_g: int = tbl2[p2_g >> 8]
        if v2_g > 127: v2_g -= 256
        v2_d: int = tbl2[p2_d >> 8]
        if v2_d > 127: v2_d -= 256

        v3_g: int = tbl3[p3_g >> 8]
        if v3_g > 127: v3_g -= 256
        v3_d: int = tbl3[p3_d >> 8]
        if v3_d > 127: v3_d -= 256

        out_g: int = (v1_g + v2_g + v3_g) * gain
        out_d: int = (v1_d + v2_d + v3_d) * gain

        idx: int = i << 1
        buf_ptr[idx] = out_g
        buf_ptr[idx + 1] = out_d
        i += 1

def silence(duree_sec):
    nb_samples = int(SAMPLE_RATE * duree_sec)
    if nb_samples > 0:
        audio_out.write(bytearray(nb_samples * 4))

def jouer_sine(freq, duree_sec, canal="BOTH"):
    """Onde sinusoïdale pure pour les tests Droite/Gauche et la gamme"""
    samples_per_cycle = int(SAMPLE_RATE / freq)
    buffer = bytearray(samples_per_cycle * 4)
    max_amp = int(32767 * VOLUME)

    for i in range(samples_per_cycle):
        val = int(max_amp * math.sin(2 * math.pi * i / samples_per_cycle))
        gauche = val if canal in ("LEFT", "BOTH") else 0
        droite = val if canal in ("RIGHT", "BOTH") else 0
        struct.pack_into('<hh', buffer, i * 4, gauche, droite)

    for _ in range(int(freq * duree_sec)):
        audio_out.write(buffer)

def jouer_mario_poly(freqs, duree_sec):
    """Joue jusqu'à 3 voix simultanées en temps réel grâce à Viper"""
    nb_samples = int(SAMPLE_RATE * duree_sec)
    buffer = bytearray(nb_samples * 4)

    f_sort = sorted(freqs)
    f1 = f_sort[0] if len(f_sort) > 0 else 0
    f2 = f_sort[1] if len(f_sort) > 1 else 0
    f3 = f_sort[2] if len(f_sort) > 2 else 0

    inc1 = int((f1 * 65536) / SAMPLE_RATE)
    inc2 = int((f2 * 65536) / SAMPLE_RATE)
    inc3 = int((f3 * 65536) / SAMPLE_RATE)

    # Voix 1 en triangle (basse) si plusieurs notes, sinon carrée
    t1 = WAVE_TRI if len(f_sort) > 1 else WAVE_SQUARE
    t2 = WAVE_SQUARE
    t3 = WAVE_SQUARE

    # Ajustement du gain selon le nombre de notes actives
    diviseur = 180 if len(f_sort) == 2 else 260
    gain = int((32767 * VOLUME) / diviseur)

    remplir_buffer_viper(buffer, nb_samples, inc1, inc2, inc3, t1, t2, t3, gain)
    audio_out.write(buffer)

# --- 3. Notes et Partition Super Mario ---
N = {
    "Do3": 130.81, "Ré3": 146.83, "Mi3": 164.81, "Fa3": 174.61,
    "Fa#3": 185.00, "Sol3": 196.00, "Sol#3": 207.65, "La3": 220.00,
    "Sib3": 233.08, "Si3": 246.94,
    "Do4": 261.63, "Do#4": 277.18, "Ré4": 293.66, "Mib4": 311.13,
    "Mi4": 329.63, "Fa4": 349.23, "Fa#4": 369.99, "Sol4": 392.00,
    "Sol#4": 415.30, "La4": 440.00, "Sib4": 466.16, "Si4": 493.88,
    "Do5": 523.25, "Do#5": 554.37, "Ré5": 587.33, "Mib5": 622.25,
    "Mi5": 659.25, "Fa5": 698.46, "Sol5": 783.99, "La5": 880.00
}

gamme_montante = ["Do4", "Ré4", "Mi4", "Fa4", "Sol4", "La4", "Si4", "Do5"]


T = 0.13  # Tempo authentique
mario_poly = [
    # --- Intro : Mi-Mi - Mi - Do-Mi - Sol - Sol(grave) ---
    (["Ré3", "Fa#4", "Mi5"], T, 0.02),
    (["Ré3", "Fa#4", "Mi5"], T, T),
    (["Ré3", "Fa#4", "Mi5"], T, T),
    (["Ré3", "Fa#4", "Do5"], T, 0.02),
    (["Ré3", "Fa#4", "Mi5"], T, T),
    (["Sol3", "Si4", "Sol5"], T*1.5, T*1.5),
    (["Sol3", "Sol4"], T*1.5, T*1.5),

    # --- Phrase 1 : Transition fluide + Do - Sol - Mi - La - Si - Sib - La ---
    (["Mi3", "Sol4", "Do5"], T*1.5, T*1.5),
    (["Do3", "Mi4", "Sol4"], T*1.5, T*1.5),
    (["Sol3", "Do4", "Mi4"], T*1.5, T*1.5),
    (["Fa3", "Do4", "La4"], T, T),
    (["Sol3", "Ré4", "Si4"], T, T),
    (["Fa#3", "Do#4", "Sib4"], T, 0.02),
    (["Fa3", "Do4", "La4"], T, T),

    # --- Triolet 1 : Sol - Mi - Sol - La - Fa - Sol - Mi - Do - Ré - Si ---
    (["Do3", "Mi4", "Sol4"], T*1.3, 0.02),
    (["Sol3", "Sol4", "Mi5"], T*1.3, 0.02),
    (["Si3", "Si4", "Sol5"], T*1.3, 0.02),
    (["Do4", "Do5", "La5"], T, T),
    (["Fa3", "La4", "Fa5"], T, 0.02),
    (["Sol3", "Si4", "Sol5"], T, T),
    (["Mi3", "Sol4", "Mi5"], T, T),
    (["Do3", "Mi4", "Do5"], T, 0.02),
    (["Ré3", "Fa4", "Ré5"], T, 0.02),
    (["Si3", "Ré4", "Si4"], T*1.5, T*1.5),

    # --- Phrase 2 (Reprise complète) : Do - Sol - Mi - La - Si - Sib - La ---
    (["Mi3", "Sol4", "Do5"], T*1.5, T*1.5),
    (["Do3", "Mi4", "Sol4"], T*1.5, T*1.5),
    (["Sol3", "Do4", "Mi4"], T*1.5, T*1.5),
    (["Fa3", "Do4", "La4"], T, T),
    (["Sol3", "Ré4", "Si4"], T, T),
    (["Fa#3", "Do#4", "Sib4"], T, 0.02),
    (["Fa3", "Do4", "La4"], T, T),

    # --- Triolet 2 + Conclusion ---
    (["Do3", "Mi4", "Sol4"], T*1.3, 0.02),
    (["Sol3", "Sol4", "Mi5"], T*1.3, 0.02),
    (["Si3", "Si4", "Sol5"], T*1.3, 0.02),
    (["Do4", "Do5", "La5"], T, T),
    (["Fa3", "La4", "Fa5"], T, 0.02),
    (["Sol3", "Si4", "Sol5"], T, T),
    (["Mi3", "Sol4", "Mi5"], T, T),
    (["Do3", "Mi4", "Do5"], T, 0.02),
    (["Ré3", "Fa4", "Ré5"], T, 0.02),
    (["Si3", "Ré4", "Si4"], T*2.0, T*0.5),
    (["Do3", "Mi4", "Do5"], T*2.5, 0)
]



# --- 4. Exécution ---
try:
    print("1. Test canal DROIT (Sine 440 Hz - 1s)")
    jouer_sine(440, 1.0, canal="RIGHT")
    silence(0.2)

    print("2. Test canal GAUCHE (Sine 440 Hz - 1s)")
    jouer_sine(440, 1.0, canal="LEFT")
    silence(0.3)

    print("3. Gamme montante et descendante (Sine wave)")
    for nom in gamme_montante:
        jouer_sine(N[nom], 0.1, canal="BOTH")
        silence(0.02)
    for nom in reversed(gamme_montante):
        jouer_sine(N[nom], 0.1, canal="BOTH")
        silence(0.02)

    silence(0.3)

    print("4. Thème Super Mario Polyphonique (Vitesse réelle Viper) !")
    for accord, duree, pause in mario_poly:
        freqs = [N[note] for note in accord]
        jouer_mario_poly(freqs, duree)
        if pause > 0:
            silence(pause)

    print("Test terminé !")

except KeyboardInterrupt:
    print("\nTest interrompu.")
finally:
    audio_out.deinit()
