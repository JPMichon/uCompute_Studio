from machine import Pin, UART
import time

# Initialisation de l'UART0 à la norme MIDI (31 250 bauds) sur GP0
midi = UART(0, baudrate=31250, bits=8, parity=None, stop=1, tx=Pin(0))

# Canal MIDI : 0 = Canal 1 (SoundFont), 1 = Canal 2 (MT-32 par défaut)
CANAL = 2  

def program_change(canal, instrument):
    """Sélectionne un patch/instrument (0 à 127)"""
    midi.write(bytes([0xC0 | (canal & 0x0F), instrument & 0x7F]))

def note_on(canal, note, velocite=100):
    """Envoie un message Note On"""
    midi.write(bytes([0x90 | (canal & 0x0F), note & 0x7F, velocite & 0x7F]))

def note_off(canal, note):
    """Envoie un message Note Off"""
    midi.write(bytes([0x80 | (canal & 0x0F), note & 0x7F, 0]))

# Petit arpège / mélodie (Notes MIDI : 60 = Do4, 64 = Mi4, 67 = Sol4, 72 = Do5)
melodie = [
    (60, 0.25), (64, 0.25), (67, 0.25), (72, 0.50),
    (67, 0.25), (72, 0.75),
    (62, 0.25), (65, 0.25), (69, 0.25), (74, 0.50),
    (69, 0.25), (74, 0.75),
]

# Sélectionne l'instrument #88 (Fantasia sur MT-32) sur le canal 2
program_change(CANAL, 88)
time.sleep(0.1)

print("Envoi de la mélodie MIDI en boucle (Ctrl+C pour arrêter)...")

try:
    while True:
        for note, duree in melodie:
            note_on(CANAL, note, 110)
            time.sleep(duree * 0.85)  # Temps de maintien de la note
            note_off(CANAL, note)
            time.sleep(duree * 0.15)  # Courte pause entre les notes
        time.sleep(1.0)
except KeyboardInterrupt:
    # Coupe toutes les notes en cas d'arrêt manuel
    for note, _ in melodie:
        note_off(CANAL, note)
    print("Arrêt du test MIDI.")
