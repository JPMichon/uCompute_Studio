from machine import Pin, SPI, UART
import os, struct, time
import sdcard  # Bibliothèque standard sdcard.py de MicroPython

# --- 1. INITIALISATION MATÉRIELLE (uCompute Junior) ---
uart_midi = UART(0, baudrate=31250, bits=8, parity=None, stop=1, tx=Pin(0))

spi = SPI(1, baudrate=10_000_000, polarity=0, phase=0,
          sck=Pin(14), mosi=Pin(15), miso=Pin(12))
sd = sdcard.SDCard(spi, Pin(13, Pin.OUT))
os.mount(sd, "/sd")

# --- 2. UTILITAIRES MIDI ---
def read_varlen(f):
    """Lit une valeur de longueur variable (VLQ) depuis le fichier"""
    val = 0
    while True:
        b = f.read(1)
        if not b:
            return 0
        byte = b[0]
        val = (val << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return val

def all_notes_off():
    """Coupe proprement tous les sons sur les 16 canaux"""
    for ch in range(16):
        uart_midi.write(bytes([0xB0 | ch, 123, 0]))

class MidiTrackStream:
    """Lit une piste MIDI en streaming sans saturer la RAM"""
    def __init__(self, filename, start_offset, length):
        self.f = open(filename, "rb")
        self.f.seek(start_offset)
        self.end_offset = start_offset + length
        self.running_status = 0
        self.finished = False
        self.next_tick = read_varlen(self.f)

    def read_next_event(self):
        if self.finished or self.f.tell() >= self.end_offset:
            self.finished = True
            return None

        b = self.f.read(1)
        if not b:
            self.finished = True
            return None
        status = b[0]

        # Gestion du Running Status MIDI
        if status < 0x80:
            first_data = bytes([status])
            status = self.running_status
        else:
            first_data = b""
            if status < 0xF0:
                self.running_status = status

        evt_type = status & 0xF0

        # Messages MIDI standard (2 ou 3 octets)
        if evt_type in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            rest = self.f.read(2 - len(first_data))
            payload = bytes([status]) + first_data + rest
            action = ("midi", payload)
        elif evt_type in (0xC0, 0xD0):
            rest = self.f.read(1 - len(first_data))
            payload = bytes([status]) + first_data + rest
            action = ("midi", payload)
        # Messages SysEx (important pour Roland MT-32 !)
        elif status in (0xF0, 0xF7):
            length = read_varlen(self.f)
            data = self.f.read(length)
            payload = (b"\xF0" + data) if status == 0xF0 else data
            action = ("midi", payload)
        # Méta-événements (Tempo, Fin de piste, etc.)
        elif status == 0xFF:
            meta_type = self.f.read(1)[0]
            length = read_varlen(self.f)
            data = self.f.read(length)
            if meta_type == 0x2F:  # End of Track
                self.finished = True
                return None
            elif meta_type == 0x51 and length == 3:  # Set Tempo (µs par noire)
                tempo = (data[0] << 16) | (data[1] << 8) | data[2]
                action = ("tempo", tempo)
            else:
                action = ("ignore", None)
        else:
            action = ("ignore", None)

        # Prépare le tick du prochain événement de cette piste
        if self.f.tell() < self.end_offset:
            self.next_tick += read_varlen(self.f)
        else:
            self.finished = True

        return action

    def close(self):
        self.f.close()

# --- 3. LECTEUR PRINCIPAL ---
def play_midi_file(filepath):
    print("Chargement :", filepath)
    tracks = []
    with open(filepath, "rb") as f:
        header = f.read(14)
        if header[:4] != b"MThd":
            print("Fichier MIDI invalide.")
            return
        _, fmt, num_tracks, division = struct.unpack(">LHHH", header)

        # Repère le début et la taille de chaque piste MTrk
        for _ in range(num_tracks):
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                break
            chunk_id, chunk_len = struct.unpack(">4sL", chunk_hdr)
            pos = f.tell()
            if chunk_id == b"MTrk":
                tracks.append(MidiTrackStream(filepath, pos, chunk_len))
            f.seek(pos + chunk_len)

    tempo_us = 500_000  # Tempo par défaut : 120 BPM (500 000 µs / noire)
    current_tick = 0
    last_time_us = time.ticks_us()

    try:
        while True:
            # Trouve la piste active ayant le prochain événement le plus proche
            active = [t for t in tracks if not t.finished]
            if not active:
                break

            next_track = min(active, key=lambda t: t.next_tick)
            delta_ticks = next_track.next_tick - current_tick

            if delta_ticks > 0:
                wait_us = int((delta_ticks * tempo_us) / division)
                target_us = time.ticks_add(last_time_us, wait_us)
                while time.ticks_diff(target_us, time.ticks_us()) > 0:
                    pass
                last_time_us = target_us
                current_tick = next_track.next_tick

            event = next_track.read_next_event()
            if event:
                kind, data = event
                if kind == "midi":
                    uart_midi.write(data)
                elif kind == "tempo":
                    tempo_us = data

    finally:
        for t in tracks:
            t.close()
        all_notes_off()
        print("Lecture terminée.")

# --- EXEMPLE D'UTILISATION ---
# Placez un fichier 'musique.mid' à la racine de la carte SD
play_midi_file("/sd/musique.mid")
