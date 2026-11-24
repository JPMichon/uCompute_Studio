from machine import Pin, SPI, UART, ADC
import os, struct, utime, time
import gc
import sdcard
import st7789 as st7789
import framebuf2
import sys

IS_Junior = True
# ---------------------------------------------------------------
# uCompute standard pins
_SSD1306_ADDR = 0x3C
_Buzzer = 11 # définition du  buzzer (GP11)
_MicroSD_Select = 13 # définition de la pin Select du SDCARD (GP13)
_SPI1_SCK = 14 # SPI1_shared Clock
_SPI1_MOSI = 15 # SPI1_shared MOSI
_SPI1_MISO = 12 # SPI1_shared MISO
_Led_System = 25 # définition du port  del systeme (GP25)
_I2C_SDA = 20 # définition de Data du I2C(0) (GP20)
_I2C_SCL = 21 # définition de SCL du I2C(0) (GP21)
_Boutons = 26 # définition du port analogue des boutons (GP26)
_ST7789_SCK = 2 # définition de la pin Clock du ST7789 (GP2) SPI0
_ST7789_MOSI = 3 # définition de la pin MOSI du ST7789 (GP3) SPI0
_ST7789_RESET = 4 # définition de la pin Reset du ST7789 (GP4)
_ST7789_DC = 5 # définition de la pinSelect du ST7789 (GP5)
# Definition des Pins pour le module ESP12f du addon-on modile
_Comm_TX = 8 # definition de la pin TX du add-on module
_Comm_RX = 9 # definition de la pin RX du add-on module
_Comm_EN = 12 # definition de la pin ENABLE du add-on module
_Comm_RST = 10 # definition de la pin RESET du add-on module
_TX_pin = 0 # definition de la pin TX
_RX_Pin = 1 # definition de la pin RX
_UART_Buffer = 1024 # taille du tampon de memoire pour le UART (512 ou 1024)

# --- CONFIGURATION MATÉRIELLE ---
if IS_Junior == True:
    _Neopixel = 6 # Gpio pour le connecteur neopixel
else:
    _ST7789_BL = 6 # définition de la pinBacklit du ST7789 (GP6)
    _MicroSD_Detect = 7 # détection de la présence d'une carte MicroSD (GP7)
    _Neopixel = 23 # Gpio pour le connecteur neopixel
  
# --- Configuration des couleurs ---

Background = st7789.BLACK
TexteColor = st7789.GREEN
CursorColor = st7789.WHITE
MenuColor = st7789.WHITE
LineColor = st7789.YELLOW
ErrorColor = st7789.RED


# --- INITIALISATION ---
BTN_Analogue = machine.ADC(_Boutons) #Diviseur de tension des boutons

# utilise la led systeme comme inducateur de lecture de la carte SD
try:
    led_sd = Pin("LED", Pin.OUT)
except TypeError:
    led_sd = Pin(_Led_System, Pin.OUT) # Repli sur GP25 si firmware très ancien
led_sd.value(0) # Éteinte par défaut

# set landscape screen
screen_width = 240
screen_height = 240
screen_rotation = 1
spi0 = SPI(0,baudrate=60000000,polarity=1,phase=1,bits=8,firstbit=SPI.MSB,sck=Pin(_ST7789_SCK),mosi=Pin(_ST7789_MOSI))

if IS_Junior == True:
    display = st7789.ST7789(spi0, screen_width, screen_height, reset=Pin(_ST7789_RESET, Pin.OUT), dc=Pin(_ST7789_DC, Pin.OUT), rotation=screen_rotation)
else:
    display = st7789.ST7789(spi0, screen_width, screen_height, reset=Pin(_ST7789_RESET, Pin.OUT), dc=Pin(_ST7789_DC, Pin.OUT), backlight=Pin(_ST7789_BL, Pin.OUT), rotation=screen_rotation)

# Initialisation du FrameBuffer
# Allocation de la mémoire pour le FrameBuffer 240x240 en RGB565 (16 bits / pixel)
# Consommation en RAM : 240 * 240 * 2 octets = 115 200 octets (LARGEMENT disponible sur RP2040/RP2350)
# FrameBuffer needs 2 bytes for every RGB565 pixel
buffer_width = 240
buffer_height = 240
buffer = bytearray(buffer_width * buffer_height * 2)

# Initialisation de l'objet FrameBuffer. 
# Si les couleurs apparaissent inversées, changez framebuf.RGB565 par sa variante d'inversion d'octets de votre carte
fbuf = framebuf2.FrameBuffer(buffer, 240, 240, framebuf2.RGB565)
# Bande de Y=120 à Y=175 (hauteur = 55 px) couvrant le BPM (125) et la barre (160)
ui_zone = memoryview(buffer)[120 * 240 * 2 : 175 * 240 * 2]
#--------------------------------------------------------------------------
# Initialisation du lecteur MicroSD

# Carte MicroSD sur SPI(1) : SCK=GP14, MOSI=GP15, MISO=GP12, CS=GP13
spi_sd = SPI(1, baudrate=10_000_000, polarity=0, phase=0, sck=Pin(_SPI1_SCK), mosi=Pin(_SPI1_MOSI), miso=Pin(_SPI1_MISO))



# Pour faire cute, j'affiche un message pour les impatients 
fbuf = framebuf2.FrameBuffer(buffer, buffer_width, buffer_height, framebuf2.RGB565)
fbuf.fill(st7789.BLACK) # Efface l'écran (le framefuffer)
fbuf.large_text('Booting', 60, 100, 2, st7789.WHITE)
display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)
utime.sleep(1)
 

# MIDI UART0
uart_midi = UART(0, baudrate=31250, bits=8, parity=None, stop=1, tx=Pin(_TX_pin), txbuf=_UART_Buffer)

# --- FONCTIONS ---

def read_keys():
    _read = BTN_Analogue.read_u16()
    _KeyPress='null'
    if _read < 7000: #Down
        _KeyPress='up'
    elif _read < 12000: #Select
        _KeyPress='select'
    elif _read < 16000: # Up
        _KeyPress='down'
    #print(str(_read))
    return _KeyPress   

def splash_screen():
    info = os.statvfs('/')
    # Extraction des valeurs numériques du tuple (AJOUTER LES CORCHETS [])
    taille_bloc = info[0]   # Taille du bloc (ex: 4096)
    blocs_totaux = info[2]  # Nombre total de blocs
    blocs_libres = info[3]  # Nombre de blocs libres
    Flashtotal = (blocs_totaux * taille_bloc) / 1024
    Flashlibre = (blocs_libres * taille_bloc) / 1024
    
    # --- Calcul de la mémoire RAM ---
    gc.collect() # Nettoie la mémoire inutilisée avant la mesure
    ram_libre = gc.mem_free() / 1024
    ram_totale = (gc.mem_free() + gc.mem_alloc()) / 1024
    
    
    fbuf.fill(Background) # Efface l'écran (le framefuffer)
    fbuf.large_text('uComputeStudio', 10, 10, 2,MenuColor)
    fbuf.rect(1, 1, 239, 30, LineColor) # boite Vide
    fbuf.large_text(f"{os.uname().machine}", 0, 40, 1, TexteColor)
    fbuf.large_text("Firmware:", 4, 60, 1, TexteColor)
    fbuf.large_text((str(os.uname().release)[:30]), 20, 70, 1, TexteColor)
    fbuf.large_text((str(os.uname().version)[:30]), 20, 80, 1, TexteColor)
    fbuf.large_text("Flash:", 4, 100, 1, TexteColor,Background)
    fbuf.large_text(f"Free:{Flashlibre:.0f}/{Flashtotal:.0f} KB", 20, 110, 1, TexteColor)
    fbuf.large_text("RAM:", 4, 130, 1, TexteColor)
    fbuf.large_text(f"Free:{ram_libre:.0f}/{ram_totale:.0f} KB", 20, 140, 1, TexteColor,)
    fbuf.large_text('Press AnyKey',20, 190, 2, MenuColor)
    display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)
    utime.sleep(1)
    
# ==============================================================================
# Fonction du Steam MIDI
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
    fbuf.fill(Background) # Efface l'écran (le framefuffer)
    fbuf.large_text('MIDI JUKEBOX', 25, 10, 2,MenuColor,Background)
    fbuf.rect(1, 1, 239, 30, LineColor) # boite Vide
    fbuf.large_text("Now Playing", 16, 48, 2, st7789.GREEN)
    
    # Affichage du nom du fichier qui joue
    display_name = filename[:-4][:14]
    fbuf.large_text(display_name, 8, 85, 2, st7789.YELLOW)
    tempo_us = 500_000
    bpm = 120
    fbuf.large_text("Tempo: 120 BPM", 8, 125, 2, st7789.CYAN, Background)
    fbuf.rect(0, 216, 240, 24, LineColor)
    fbuf.large_text("STOP", 100, 220, 2, st7789.WHITE)
    display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height) # Rafraichie l'ecran pour afficher les erreurs
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
    last_ui_update_us = last_time_us
    event_counter = 0
    ui_dirty = False # Indique si l'écran a besoin d'être rafraîchi

    while read_keys() == 'select':
        time.sleep_ms(20)

    try:
        while True:
            # Recherche de la prochaine piste sans allouer de liste ni appeler de lambda
            next_track = None
            min_tick = 0x7FFFFFFF
            for t in tracks:
                if not t.finished and t.next_tick < min_tick:
                    min_tick = t.next_tick
                    next_track = t
            
            if next_track is None:
                break

            delta_ticks = min_tick - current_tick
            if delta_ticks > 0:
                wait_us = int((delta_ticks * tempo_us) / division)
                target_us = time.ticks_add(last_time_us, wait_us)
                
                # Si l'écran a changé ET qu'on a au moins 15 ms de pause devant nous
                if ui_dirty and time.ticks_diff(target_us, time.ticks_us()) > 30_000:
                    display.blit_buffer(ui_zone, 0, 120, 240, 55)
                    ui_dirty = False
                    last_ui_update_us = time.ticks_us()

                while time.ticks_diff(target_us, time.ticks_us()) > 0:
                    if read_keys() == 'select':
                        return
                last_time_us = target_us
                current_tick = next_track.next_tick

            event = next_track.read_next_event()
            if event:
                kind, data = event
                if kind == "midi":
                    uart_midi.write(data)
                    event_counter += 1
                    # On prépare la barre en RAM (très rapide, < 0.2 ms), sans bloquer le SPI
                    if event_counter % 16 == 0 and time.ticks_diff(time.ticks_us(), last_ui_update_us) > 200_000:
                        bar_w = ((event_counter // 16) % 14 + 1) * 15
                        fbuf.fill_rect(15, 160, 210, 12, Background)
                        fbuf.fill_rect(15, 160, bar_w, 12, st7789.GREEN)
                        ui_dirty = True
                elif kind == "tempo":
                    tempo_us = data
                    new_bpm = int(60_000_000 / tempo_us)
                    if new_bpm != bpm:
                        bpm = new_bpm
                        # efface proprement l'ancien texte en RAM (x=8, y=125, largeur=224, hauteur=16)
                        fbuf.fill_rect(8, 125, 224, 16, Background)
                        fbuf.large_text(f"Tempo: {bpm:3d} BPM", 8, 125, 2, st7789.CYAN)
                        ui_dirty = True
    finally:
        for t in tracks:
            t.close()
        all_notes_off()
        gc.collect() # Nettoie la RAM après la chanson

# ==============================================================================
# 4. INTERFACE MENU SUR ÉCRAN ST7789
# ==============================================================================
def draw_menu(files, selected, scroll_offset):
    fbuf.fill(Background) # Efface l'écran (le framefuffer)
    fbuf.large_text('MIDI JUKEBOX', 25, 10, 2,MenuColor,Background)
    fbuf.rect(1, 1, 239, 30, LineColor) # boite Vide

    if not files:
        fbuf.large_text("Aucun fichier", 16, 100, 2, ErrorColor,Background)
        fbuf.large_text(".mid sur /sd", 24, 130, 2, ErrorColor,Background)
        
        return

    visible_rows = 6
    for i in range(visible_rows):
        idx = scroll_offset + i
        if idx >= len(files):
            break
        y = 42 + i * 28
        name = files[idx][:-4][:13]
        if idx == selected:
            fbuf.fill_rect(4, y - 3, 232, 24, CursorColor)
            fbuf.large_text(">" + name, 8, y, 2, LineColor)
        else:
            fbuf.large_text(" " + name, 8, y, 2, TexteColor, Background)

    fbuf.rect(0, 216, 240, 24, LineColor)
    fbuf.large_text("Bas  Play Haut", 8, 220, 2, MenuColor)
    display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height) # Rafraichie l'ecran pour afficher les erreurs

#-----------------------------------------------------------------------------------
# Main
    
splash_screen()

while read_keys() =='null':
    utime.sleep(.1)
 
fbuf.fill(Background) # Efface l'écran (le framefuffer)
display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)
try:
    sd = sdcard.SDCard(spi_sd, Pin(_MicroSD_Select, Pin.OUT))
    
    # Allume la LED uniquement lors d'une vraie lecture matérielle (bloc de 512 octets)
    _orig_readblocks = sd.readblocks
    def _led_readblocks(block_num, buf):
        led_sd.value(1)
        try:
            return _orig_readblocks(block_num, buf)
        finally:
            led_sd.value(0)
    sd.readblocks = _led_readblocks

    os.mount(sd, '/sd') # Indispensable pour accéder aux fichiers via '/sd/musique.mid'
    print("SD Card mounted successfully")
except Exception as e:
    sd = None
    led_sd.value(0)
    fbuf.fill(ErrorColor) # Efface l'écran (le framefuffer)
    fbuf.large_text("No SD Card", 40, 90, 2, st7789.WHITE)
    fbuf.large_text("Detected", 50, 120, 2, st7789.WHITE)
    print("No SD Card detected:", e)
    display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)
    sys.exit()# Arrête net le programme ici
finally:
    led_sd.value(0)  
   
files = sorted([f for f in os.listdir("/sd") if f.lower().endswith(".mid")])
selected = 0
scroll_offset = 0
visible_rows = 6

draw_menu(files, selected, scroll_offset)

while True:
    btn = read_keys()
    if btn != 'null' and files:
        if btn == 'up':    # Haut
            selected = (selected - 1) % len(files)
        elif btn == 'select':  # Lancer la lecture
            filepath = "/sd/" + files[selected]
            play_midi_with_ui(filepath, files[selected])
        elif btn == 'down':  # Bas
            selected = (selected + 1) % len(files)

        if selected < scroll_offset:
            scroll_offset = selected
        elif selected >= scroll_offset + visible_rows:
            scroll_offset = selected - visible_rows + 1

    draw_menu(files, selected, scroll_offset)


