import math
import struct
import time
from machine import Pin, I2S

# --- 1. Configuration des broches selon votre PCB ---
BCK_PIN = 17   # BCK sur PCM5102A
LCK_PIN = 18   # LCK sur PCM5102A (doit obligatoirement être BCK + 1)
DIN_PIN = 16   # DIN sur PCM5102A

# --- 2. Paramètres du son de test ---
SAMPLE_RATE = 44100   # Fréquence d'échantillonnage (Hz)
TONE_FREQ = 440       # Note La3 (440 Hz)
VOLUME = 0.2          # Volume à 20 % (évite de saturer un casque ou un ampli)

# --- 3. Initialisation du bus I2S ---
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

# --- 4. Génération d'une période d'onde sinusoïdale ---
samples_per_cycle = SAMPLE_RATE // TONE_FREQ
# Chaque échantillon stéréo fait 4 octets (2 octets Gauche + 2 octets Droite)
buffer = bytearray(samples_per_cycle * 4)

max_amplitude = int(32767 * VOLUME)

for i in range(samples_per_cycle):
    # Calcul de la valeur sinusoïdale sur 16 bits signés
    val = int(max_amplitude * math.sin(2 * math.pi * i / samples_per_cycle))
    # Écriture identique sur le canal Gauche et le canal Droit ('<hh' = 2 entiers 16-bit)
    struct.pack_into('<hh', buffer, i * 4, val, val)

# --- 5. Lecture en boucle ---
print("Diffusion du signal de test (440 Hz)... Appuyez sur Ctrl+C pour arrêter.")

try:
    while True:
        audio_out.write(buffer)
except KeyboardInterrupt:
    print("\nArrêt du test.")
finally:
    audio_out.deinit()