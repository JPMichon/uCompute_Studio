from machine import Pin, SPI, UART, ADC
from machine import I2S
import st7789 as st7789
import framebuf2
import struct, utime, time


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

# --- CONFIGURATION AUDIO I2S (PCM5102A) ---
BCK_PIN = 17
LCK_PIN = 18
DIN_PIN = 16
SAMPLE_RATE = 44100
VOLUME = 0.28



# --- Configuration des couleurs ---

Background = st7789.BLACK
TexteColor = st7789.GREEN
CursorColor = st7789.WHITE
MenuColor = st7789.WHITE
LineColor = st7789.YELLOW
ErrorColor = st7789.RED

# Liste des 6 types de bruits : (Nom affiché, ID interne, Couleur d'affichage)
NOISE_TYPES = [
    ("1. Blanc",     0, st7789.WHITE),
    ("2. Rose",      1, st7789.MAGENTA),
    ("3. Brun",      2, st7789.YELLOW),
    ("4. Bleu",      3, st7789.CYAN),
    ("5. Violet",    4, st7789.BLUE),
    ("6. Retro 8bit",5, st7789.GREEN)
]

# État interne des générateurs aléatoires (Gauche, Droite, Brown, Pink, Blue/Violet)
state = bytearray(32)
struct.pack_into('<IIIIIIII', state, 0, 0xACE1, 0x1337, 0, 0, 0, 0, 0, 0)


# --- INITIALISATION ---
BTN_Analogue = machine.ADC(_Boutons) #Diviseur de tension des boutons
#machine.freq(133000000) # overclock au besoins

# set landscape screen
screen_width = 240
screen_height = 240
screen_rotation = 1
spi0 = SPI(0,baudrate=40000000,polarity=1,phase=1,bits=8,firstbit=SPI.MSB,sck=Pin(_ST7789_SCK),mosi=Pin(_ST7789_MOSI))

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


# Pour faire cute, j'affiche un message pour les impatients 
fbuf = framebuf2.FrameBuffer(buffer, buffer_width, buffer_height, framebuf2.RGB565)
fbuf.fill(st7789.BLACK) # Efface l'écran (le framefuffer)
fbuf.large_text('Booting', 60, 100, 2, st7789.WHITE)
display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)
utime.sleep(1)
 

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

@micropython.viper
def generer_bruit_viper(buf_ptr: ptr16, nb_samples: int, mode: int, gain: int, st: ptr32):
    """Génère en temps réel en stéréo l'une des 6 couleurs de bruit"""
    lfsr_g: int = st[0]
    lfsr_d: int = st[1]
    brown_g: int = st[2]
    brown_d: int = st[3]
    pink_g: int = st[4]
    pink_d: int = st[5]
    prev_g: int = st[6]
    prev_d: int = st[7]

    if lfsr_g == 0:
        lfsr_g = 0xACE1
    if lfsr_d == 0:
        lfsr_d = 0x1337

    cnt_g: int = 0
    cnt_d: int = 0

    i: int = 0
    while i < nb_samples:
        if mode == 5:
            # L'intervalle de temps varie aléatoirement à chaque pas (entre 8 et 39 échantillons)
            if cnt_g <= 0:
                bit_g: int = ((lfsr_g >> 0) ^ (lfsr_g >> 1)) & 1
                lfsr_g = ((lfsr_g >> 1) | (bit_g << 6)) & 0x7F
                cnt_g = 8 + (lfsr_g & 0x1F)
            cnt_g -= 1

            if cnt_d <= 0:
                bit_d: int = ((lfsr_d >> 0) ^ (lfsr_d >> 2) ^ (lfsr_d >> 3) ^ (lfsr_d >> 5)) & 1
                lfsr_d = ((lfsr_d >> 1) | (bit_d << 15)) & 0xFFFF
                cnt_d = 8 + (lfsr_d & 0x1F)
            cnt_d -= 1

            w_g: int = 24000 if (lfsr_g & 1) else -24000
            w_d: int = 24000 if (lfsr_d & 1) else -24000
        else:
            bit_g: int = ((lfsr_g >> 0) ^ (lfsr_g >> 2) ^ (lfsr_g >> 3) ^ (lfsr_g >> 5)) & 1
            lfsr_g = ((lfsr_g >> 1) | (bit_g << 15)) & 0xFFFF
            bit_d: int = ((lfsr_d >> 0) ^ (lfsr_d >> 2) ^ (lfsr_d >> 3) ^ (lfsr_d >> 5)) & 1
            lfsr_d = ((lfsr_d >> 1) | (bit_d << 15)) & 0xFFFF
            w_g: int = lfsr_g - 32768
            w_d: int = lfsr_d - 32768

        out_g: int = 0
        out_d: int = 0

        if mode == 0 or mode == 5:      # Blanc ou Rétro 8-bit
            out_g = w_g
            out_d = w_d
        elif mode == 1:                 # Rose (-3dB/oct)
            pink_g = (pink_g * 7 + w_g) >> 3
            pink_d = (pink_d * 7 + w_d) >> 3
            out_g = pink_g << 1
            out_d = pink_d << 1
        elif mode == 2:                 # Brun (-6dB/oct) - Identique
            brown_g += (w_g >> 5)
            if brown_g > 32767:
                brown_g = 32767
            elif brown_g < -32768:
                brown_g = -32768
            brown_d += (w_d >> 5)
            if brown_d > 32767:
                brown_d = 32767
            elif brown_d < -32768:
                brown_d = -32768
            out_g = brown_g
            out_d = brown_d
        elif mode == 3:                 # Bleu (+3dB/oct)
            out_g = (w_g - prev_g) >> 1
            out_d = (w_d - prev_d) >> 1
            prev_g = w_g
            prev_d = w_d
        elif mode == 4:                 # Violet (+6dB/oct)
            diff_g: int = (w_g - prev_g) >> 1
            diff_d: int = (w_d - prev_d) >> 1
            out_g = (diff_g - brown_g) >> 1
            out_d = (diff_d - brown_d) >> 1
            brown_g = diff_g
            brown_d = diff_d
            prev_g = w_g
            prev_d = w_d

        idx: int = i << 1
        buf_ptr[idx] = (out_g * gain) >> 8
        buf_ptr[idx + 1] = (out_d * gain) >> 8
        i += 1

    st[0] = lfsr_g
    st[1] = lfsr_d
    st[2] = brown_g
    st[3] = brown_d
    st[4] = pink_g
    st[5] = pink_d
    st[6] = prev_g
    st[7] = prev_d


def play_noise_until_key(selected_idx):
    nom, mode, couleur = NOISE_TYPES[selected_idx]
    draw_menu(selected_idx, playing=True)

    chunk_samples = 1024
    audio_buf = bytearray(chunk_samples * 4)
    gain = int(256 * VOLUME)

    # Attend que le bouton Select soit complètement relâché tout en commençant à jouer
    while read_keys() != 'null':
        generer_bruit_viper(audio_buf, chunk_samples, mode, gain, state)
        audio_out.write(audio_buf)

    # Laisse 150 ms de stabilité analogique après relâchement
    for _ in range(7):
        generer_bruit_viper(audio_buf, chunk_samples, mode, gain, state)
        audio_out.write(audio_buf)

    try:
        while True:
            if read_keys() != 'null':
                utime.sleep_ms(20)
                if read_keys() != 'null':
                    break
            generer_bruit_viper(audio_buf, chunk_samples, mode, gain, state)
            audio_out.write(audio_buf)
    finally:
        audio_out.write(bytearray(512))
        while read_keys() != 'null':
            utime.sleep_ms(20)


# ==============================================================================
# INTERFACE MENU SUR ÉCRAN ST7789
# ==============================================================================
def draw_menu(selected, playing=False):
    fbuf.fill(Background)
    fbuf.large_text('NOISE GEN', 48, 10, 2, MenuColor, Background)
    fbuf.rect(1, 1, 239, 30, LineColor)

    for i, (nom, _, couleur) in enumerate(NOISE_TYPES):
        y = 42 + i * 28
        if i == selected:
            # Curseur vert si en lecture, blanc sinon
            cur_col = st7789.GREEN if playing else CursorColor
            fbuf.fill_rect(4, y - 3, 232, 24, cur_col)
            fbuf.large_text(">" + nom, 8, y, 2, st7789.BLACK)
        else:
            fbuf.large_text(" " + nom, 8, y, 2, couleur, Background)

    fbuf.rect(0, 216, 240, 24, LineColor)
    if playing:
        fbuf.fill_rect(1, 217, 238, 22, ErrorColor)
        fbuf.large_text("TOUCHE = STOP", 16, 220, 2, st7789.WHITE)
    else:
        fbuf.large_text("Bas  Play Haut", 8, 220, 2, MenuColor)

    display.blit_buffer(buffer, 0, 0, buffer_width, buffer_height)

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
#Initialisation du PCM
audio_out = I2S(0,sck=Pin(BCK_PIN),ws=Pin(LCK_PIN),sd=Pin(DIN_PIN),mode=I2S.TX,bits=16,format=I2S.STEREO,rate=SAMPLE_RATE,ibuf=4096)
selected = 0
draw_menu(selected, playing=False)

try:
    while True:
        btn = read_keys()
        if btn != 'null':
            utime.sleep_ms(30)  # Anti-rebond analogique
            btn = read_keys()
            
            if btn == 'up':
                selected = (selected - 1) % len(NOISE_TYPES)
                draw_menu(selected, playing=False)
            elif btn == 'down':
                selected = (selected + 1) % len(NOISE_TYPES)
                draw_menu(selected, playing=False)
            elif btn == 'select':
                play_noise_until_key(selected)
                draw_menu(selected, playing=False)
                
            # Attend que le bouton soit relâché avant la prochaine action
            while read_keys() != 'null':
                utime.sleep_ms(20)
                
        utime.sleep_ms(20)
finally:
    audio_out.deinit()
    