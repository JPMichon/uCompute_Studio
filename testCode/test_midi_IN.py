import time
from machine import Pin, UART

# --- 1. Configuration UART0 pour le MIDI standard (31 250 bauds) ---
# Selon votre PCB : GP00 = TX (MIDI-OUT), GP01 = RX (MIDI-IN)
midi_uart = UART(0, baudrate=31250, bits=8, parity=None, stop=1, tx=Pin(0), rx=Pin(1))

# LED intégrée du Pico pour un retour visuel supplémentaire à chaque message reçu
led_pico = Pin("LED", Pin.OUT)

NOMS_NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]

def note_vers_nom(num_note):
    octave = (num_note // 12) - 1
    nom = NOMS_NOTES[num_note % 12]
    return f"{nom}{octave} ({num_note})"

print("=== Test de l'interface MIDI (GP01 IN / GP00 OUT) ===")
print("Branchez un clavier ou contrôleur MIDI et appuyez sur une touche...")
print("(Appuyez sur Ctrl+C pour arrêter)\n")

status_courant = 0
data_buffer = []

try:
    while True:
        if midi_uart.any():
            # Lecture des octets reçus sur GP01
            octets = midi_uart.read()
            
            # Renvoi immédiat sur GP00 (MIDI Thru) pour tester la LED OUT et le 74HCT14D
            midi_uart.write(octets)
            
            for b in octets:
                # Ignorer les messages système temps réel (Active Sensing 0xFE, Clock 0xF8)
                if b >= 0xF8:
                    continue

                # Octet de statut (bit de poids fort à 1, donc >= 0x80)
                if b & 0x80:
                    status_courant = b
                    data_buffer = []
                else:
                    # Octet de donnée (0 à 127)
                    data_buffer.append(b)
                    cmd = status_courant & 0xF0
                    canal = (status_courant & 0x0F) + 1

                    # Messages à 2 octets de données (Note On, Note Off, Control Change, Pitch Bend)
                    if cmd in (0x80, 0x90, 0xA0, 0xB0, 0xE0) and len(data_buffer) == 2:
                        d1, d2 = data_buffer[0], data_buffer[1]
                        data_buffer = []

                        if cmd == 0x90 and d2 > 0:
                            led_pico.on()
                            print(f"[Canal {canal}] NOTE ON  : {note_vers_nom(d1)} | Vélocité : {d2}")
                        elif cmd == 0x80 or (cmd == 0x90 and d2 == 0):
                            led_pico.off()
                            print(f"[Canal {canal}] NOTE OFF : {note_vers_nom(d1)}")
                        elif cmd == 0xB0:
                            print(f"[Canal {canal}] CC #{d1}   : Valeur {d2}")
                        elif cmd == 0xE0:
                            valeur_pitch = (d2 << 7) | d1
                            print(f"[Canal {canal}] PITCH    : {valeur_pitch}")

                    # Messages à 1 octet de donnée (Program Change, Channel Pressure)
                    elif cmd in (0xC0, 0xD0) and len(data_buffer) == 1:
                        d1 = data_buffer[0]
                        data_buffer = []
                        if cmd == 0xC0:
                            print(f"[Canal {canal}] PROGRAM CHANGE : Instrument #{d1}")

        time.sleep_ms(1)

except KeyboardInterrupt:
    led_pico.off()
    print("\nTest MIDI terminé.")
