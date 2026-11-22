from machine import Pin, SPI, UART, ADC
import os, struct, time
import sdcard

# ==============================================================================
# 1. PILOTE LÉGER ST7789 (240x240) POUR uCompute Junior (GP2, GP3, GP4, GP5)
# ==============================================================================
class ST7789:
    def __init__(self, spi, dc, rst, width=240, height=240):
        self.spi = spi
        self.dc = dc
        self.rst = rst
        self.width = width
        self.height = height
        self.dc.init(Pin.OUT, value=0)
        self.rst.init(Pin.OUT, value=1)
        self.reset()
        self.init_display()

    def reset(self):
        self.rst(0)
        time.sleep_ms(50)
        self.rst(1)
        time.sleep_ms(50)

    def write_cmd(self, cmd):
        self.dc(0)
        self.spi.write(bytes([cmd]))

    def write_data(self, data):
        self.dc(1)
        self.spi.write(data)

    def init_display(self):
        self.write_cmd(0x01)  # SWRESET
        time.sleep_ms(150)
        self.write_cmd(0x11)  # SLPOUT
        time.sleep_ms(50)
        self.write_cmd(0x3A)  # COLMOD (16-bit RGB565)
        self.write_data(b"\x55")
        self.write_cmd(0x36)  # MADCTL (Rotation 90° vers la droite)
        self.write_data(b"\x60")
        self.write_cmd(0x21)  # INVON (Couleurs normales sur IPS)
        self.write_cmd(0x13)  # NORON
        self.write_cmd(0x29)  # DISPON

    def set_window(self, x0, y0, x1, y1):
        self.write_cmd(0x2A)
        self.write_data(struct.pack(">HH", x0, x1))
        self.write_cmd(0x2B)
        self.write_data(struct.pack(">HH", y0, y1))
        self.write_cmd(0x2C)

    def fill_rect(self, x, y, w, h, color):
        if x >= self.width or y >= self.height:
            return
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        self.set_window(x, y, x + w - 1, y + h - 1)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        chunk = bytes([hi, lo]) * w
        self.dc(1)
        for _ in range(h):
            self.spi.write(chunk)

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)

    def text(self, s, x, y, color=0xFFFF, bg=0x0000, scale=2):
        """Affiche du texte à l'aide de la police 8x8 intégrée à framebuf"""
        import framebuf
        buf = bytearray(8)
        fb = framebuf.FrameBuffer(buf, 8, 8, framebuf.MONO_HLSB)
        for idx, ch in enumerate(s):
            cx = x + idx * 8 * scale
            if cx + 8 * scale > self.width:
                break
            fb.fill(0)
            fb.text(ch, 0, 0, 1)
            for row in range(8):
                for col in range(8):
                    c = color if fb.pixel(col, row) else bg
                    if scale == 1:
                        self.fill_rect(cx + col, y + row, 1, 1, c)
                    else:
                        self.fill_rect(cx + col * scale, y + row * scale, scale, scale, c)

# Couleurs RGB565
BLACK  = 0x0000
WHITE  = 0xFFFF
CYAN   = 0x07FF
YELLOW = 0xFFE0
GREEN  = 0x07E0
BLUE   = 0x001F
DARKBG = 0x10A2
HILITE = 0x03EF

# ==============================================================================
# 2. INITIALISATION MATÉRIELLE (uCompute Junior)
# ==============================================================================
# Écran ST7789 sur SPI(0) : SCK=GP2, MOSI=GP3, RES=GP4, DC=GP5
spi_lcd = SPI(0, baudrate=40_000_000, polarity=1, phase=1, sck=Pin(2), mosi=Pin(3))
tft = ST7789(spi_lcd, dc=Pin(5), rst=Pin(4))

# Carte MicroSD sur SPI(1) : SCK=GP14, MOSI=GP15, MISO=GP12, CS=GP13
spi_sd = SPI(1, baudrate=10_000_000, polarity=0, phase=0,
             sck=Pin(14), mosi=Pin(15), miso=Pin(12))
sd = sdcard.SDCard(spi_sd, Pin(13, Pin.OUT))
try:
    os.mount(sd, "/sd")
except OSError:
    pass

# MIDI UART0 sur GP0 (TX)
uart_midi = UART(0, baudrate=31250, bits=8, parity=None, stop=1, tx=Pin(0))

# Échelle de 3 boutons sur GP26 (ADC0)
adc_btn = ADC(Pin(26))

def read_button():
    """
    Lit l'échelle analogique BTN1, BTN2, BTN3 sur GP26 :
    1 = BTN1 (Haut), 2 = BTN2 (Play/Stop), 3 = BTN3 (Bas)
    """
    val = adc_btn.read_u16()
    if val > 60000:      # Aucun bouton pressé (tiré à 3.3V)
        return 0
    elif val < 15000:    # BTN1 (Haut)
        return 1
    elif val < 35000:    # BTN2 (Play / Stop)
        return 2
    else:                # BTN3 (Bas)
        return 3

# ==============================================================================
# 3. MOTEUR DE LECTURE MIDI EN STREAMING
# ==============================================================================
def read_varlen(f):
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
    for ch in range(16):
        uart_midi.write(bytes([0xB0 | ch, 123, 0]))

class MidiTrackStream:
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

        if status < 0x80:
            first_data = bytes([status])
            status = self.running_status
        else:
            first_data = b""
            if status < 0xF0:
                self.running_status = status

        evt_type = status & 0xF0

        if evt_type in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            rest = self.f.read(2 - len(first_data))
            action = ("midi", bytes([status]) + first_data + rest)
        elif evt_type in (0xC0, 0xD0):
            rest = self.f.read(1 - len(first_data))
            action = ("midi", bytes([status]) + first_data + rest)
        elif status in (0xF0, 0xF7):
            length = read_varlen(self.f)
            data = self.f.read(length)
            action = ("midi", (b"\xF0" + data) if status == 0xF0 else data)
        elif status == 0xFF:
            meta_type = self.f.read(1)[0]
            length = read_varlen(self.f)
            data = self.f.read(length)
            if meta_type == 0x2F:
                self.finished = True
                return None
            elif meta_type == 0x51 and length == 3:
                tempo = (data[0] << 16) | (data[1] << 8) | data[2]
                action = ("tempo", tempo)
            else:
                action = ("ignore", None)
        else:
            action = ("ignore", None)

        if self.f.tell() < self.end_offset:
            self.next_tick += read_varlen(self.f)
        else:
            self.finished = True
        return action

    def close(self):
        self.f.close()

def play_midi_with_ui(filepath, filename):
    tft.fill(BLACK)
    tft.fill_rect(0, 0, 240, 32, BLUE)
    tft.text("uCompute Studio", 8, 8, WHITE, BLUE, scale=2)
    tft.text("LECTURE EN COURS", 16, 48, GREEN, BLACK, scale=2)

    display_name = filename[:-4][:14]
    tft.text(display_name, 8, 85, YELLOW, BLACK, scale=2)

    tempo_us = 500_000
    bpm = 120
    tft.text("Tempo: 120 BPM", 8, 125, CYAN, BLACK, scale=2)
    tft.text("[BTN2] = STOP", 20, 200, WHITE, DARKBG, scale=2)

    tracks = []
    with open(filepath, "rb") as f:
        header = f.read(14)
        if header[:4] != b"MThd":
            return
        _, _, fmt, num_tracks, division = struct.unpack(">4sLHHH", header)
        for _ in range(num_tracks):
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                break
            chunk_id, chunk_len = struct.unpack(">4sL", chunk_hdr)
            pos = f.tell()
            if chunk_id == b"MTrk":
                tracks.append(MidiTrackStream(filepath, pos, chunk_len))
            f.seek(pos + chunk_len)

    current_tick = 0
    last_time_us = time.ticks_us()
    event_counter = 0

    # Attendre que BTN2 soit relâché avant de lancer
    while read_button() == 2:
        time.sleep_ms(20)

    try:
        while True:
            active = [t for t in tracks if not t.finished]
            if not active:
                break

            next_track = min(active, key=lambda t: t.next_tick)
            delta_ticks = next_track.next_tick - current_tick

            if delta_ticks > 0:
                wait_us = int((delta_ticks * tempo_us) / division)
                target_us = time.ticks_add(last_time_us, wait_us)
                while time.ticks_diff(target_us, time.ticks_us()) > 0:
                    # Vérifie si l'utilisateur appuie sur BTN2 pour stopper
                    if read_button() == 2:
                        return
                last_time_us = target_us
                current_tick = next_track.next_tick

            event = next_track.read_next_event()
            if event:
                kind, data = event
                if kind == "midi":
                    uart_midi.write(data)
                    event_counter += 1
                    if event_counter % 16 == 0:
                        bar_w = ((event_counter // 16) % 14 + 1) * 15
                        tft.fill_rect(15, 160, 210, 12, DARKBG)
                        tft.fill_rect(15, 160, bar_w, 12, GREEN)
                elif kind == "tempo":
                    tempo_us = data
                    new_bpm = int(60_000_000 / tempo_us)
                    if new_bpm != bpm:
                        bpm = new_bpm
                        tft.text(f"Tempo: {bpm:3d} BPM", 8, 125, CYAN, BLACK, scale=2)
    finally:
        for t in tracks:
            t.close()
        all_notes_off()
        while read_button() != 0:
            time.sleep_ms(20)

# ==============================================================================
# 4. INTERFACE MENU SUR ÉCRAN ST7789
# ==============================================================================
def draw_menu(files, selected, scroll_offset):
    tft.fill(BLACK)
    tft.fill_rect(0, 0, 240, 32, BLUE)
    tft.text("MIDI JUKEBOX", 24, 8, WHITE, BLUE, scale=2)

    if not files:
        tft.text("Aucun fichier", 16, 100, YELLOW, BLACK, scale=2)
        tft.text(".mid sur /sd", 24, 130, YELLOW, BLACK, scale=2)
        return

    visible_rows = 6
    for i in range(visible_rows):
        idx = scroll_offset + i
        if idx >= len(files):
            break
        y = 42 + i * 28
        name = files[idx][:-4][:13]
        if idx == selected:
            tft.fill_rect(4, y - 3, 232, 24, HILITE)
            tft.text(">" + name, 8, y, YELLOW, HILITE, scale=2)
        else:
            tft.text(" " + name, 8, y, WHITE, BLACK, scale=2)

    tft.fill_rect(0, 216, 240, 24, DARKBG)
    tft.text("1:Haut 2:Play 3:Bas", 8, 220, CYAN, DARKBG, scale=1)

def main():
    files = sorted([f for f in os.listdir("/sd") if f.lower().endswith(".mid")])
    selected = 0
    scroll_offset = 0
    visible_rows = 6

    draw_menu(files, selected, scroll_offset)

    while True:
        btn = read_button()
        if btn != 0 and files:
            if btn == 1:    # Haut
                selected = (selected - 1) % len(files)
            elif btn == 2:  # Lancer la lecture
                filepath = "/sd/" + files[selected]
                play_midi_with_ui(filepath, files[selected])
            elif btn == 3:  # Bas
                selected = (selected + 1) % len(files)

            if selected < scroll_offset:
                scroll_offset = selected
            elif selected >= scroll_offset + visible_rows:
                scroll_offset = selected - visible_rows + 1

            draw_menu(files, selected, scroll_offset)

            while read_button() != 0:
                time.sleep_ms(20)
            time.sleep_ms(80)

        time.sleep_ms(20)

main()

