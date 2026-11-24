# TEST PCM5102a with ST7789 support
#
#
#
#--------------------------------------------------------------
from machine import Pin, SPI, UART, ADC, I2S
import machine
import math
import struct
import utime, time
import st7789py as st7789
import vga2_bold_16x16 as font


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
# -------------------------------------------------------------------------------------------
# Configuration Specifique pour l'add-on le uCompute Studio
#machine.freq(133000000) # OverClock le Pico

BCK_PIN = 17
LCK_PIN = 18
DIN_PIN = 16

SAMPLE_RATE = 44100
VOLUME = 0.28



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

    (["Mi3", "Sol4", "Do5"], T*1.5, T*1.5),
    (["Do3", "Mi4", "Sol4"], T*1.5, T*1.5),
    (["Sol3", "Do4", "Mi4"], T*1.5, T*1.5),
    (["Fa3", "Do4", "La4"], T, T),
    (["Sol3", "Ré4", "Si4"], T, T),
    (["Fa#3", "Do#4", "Sib4"], T, 0.02),
    (["Fa3", "Do4", "La4"], T, T),

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

    (["Mi3", "Sol4", "Do5"], T*1.5, T*1.5),
    (["Do3", "Mi4", "Sol4"], T*1.5, T*1.5),
    (["Sol3", "Do4", "Mi4"], T*1.5, T*1.5),
    (["Fa3", "Do4", "La4"], T, T),
    (["Sol3", "Ré4", "Si4"], T, T),
    (["Fa#3", "Do#4", "Sib4"], T, 0.02),
    (["Fa3", "Do4", "La4"], T, T),

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



# --- Configuration des couleurs ---

Background = st7789.BLACK
TexteColor = st7789.WHITE
CursorColor = st7789.WHITE
MenuColor = st7789.BLUE
TexteMenuColor = st7789.WHITE
LineColor = st7789.WHITE
ErrorColor = st7789.RED


# --- INITIALISATION ---
BTN_Analogue = machine.ADC(_Boutons) #Diviseur de tension des boutons
# set landscape screen
screen_width = 240
screen_height = 240
screen_rotation = 1
spi0 = SPI(0,baudrate=40000000,polarity=1,phase=1,bits=8,firstbit=SPI.MSB,sck=Pin(_ST7789_SCK),mosi=Pin(_ST7789_MOSI))

if IS_Junior == True:
    display = st7789.ST7789(spi0, screen_width, screen_height, reset=Pin(_ST7789_RESET, Pin.OUT), dc=Pin(_ST7789_DC, Pin.OUT), rotation=screen_rotation)
else:
    display = st7789.ST7789(spi0, screen_width, screen_height, reset=Pin(_ST7789_RESET, Pin.OUT), dc=Pin(_ST7789_DC, Pin.OUT), backlight=Pin(_ST7789_BL, Pin.OUT), rotation=screen_rotation)



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
    display.fill(Background) # Efface l'écran (le framefuffer)
    display.fill_rect( 0, 0, screen_width, 30, MenuColor)
    display.rect( 0, 0, screen_width, 30, LineColor)
    display.text(font,'Test PCM5102a', 25, 10, TexteMenuColor, MenuColor)
    display.text(font,'A) Test STEREO', 0, 50, TexteColor, Background)
    display.text(font,'B) Test SineWave', 0, 70, TexteColor, Background)
    display.text(font,'C) Test Poly', 0, 90, TexteColor, Background)
    display.line(0, 210, screen_width, 210, LineColor)
    display.text(font,' A     B     C', 0, 220, TexteColor, Background)
 
#-----------------------------------------------------------------------------------
# Main



# Pour faire cute, j'affiche un message pour les impatients 
display.fill(st7789.BLACK) # Efface l'écran (le framefuffer)
display.text(font, 'Booting', 60, 100, TexteColor)
utime.sleep(1)

splash_screen()

# Initialise l'I2S APRÈS l'écran
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

# --- BOUCLE PRINCIPALE DE LECTURE ---
dernier_bouton = 'null'

while True:
    touche = read_keys()
    
    # Vérifie si un nouveau bouton vient d'être pressé (front montant)
    if touche != 'null' and dernier_bouton == 'null':
        utime.sleep_ms(30)  # Petit délai anti-rebond pour stabiliser la lecture analogique
        touche = read_keys() # Re-vérifie la valeur stable
        
        if touche == 'down':
                silence(0.2)
                print("1. Test canal DROIT (Sine 440 Hz - 1s)")
                jouer_sine(440, 1.0, canal="RIGHT")
                silence(0.2)
                print("2. Test canal GAUCHE (Sine 440 Hz - 1s)")
                jouer_sine(440, 1.0, canal="LEFT")
                print("Test terminé !")
                
        elif touche == 'up':
                silence(0.3)
                print("4. Thème Super Mario Polyphonique (Vitesse réelle Viper) !")
                for accord, duree, pause in mario_poly:
                    freqs = [N[note] for note in accord]
                    jouer_mario_poly(freqs, duree)
                    if pause > 0:
                        silence(pause)
                print("Test terminé !")
            
        elif touche == 'select':
                silence(0.2)
                print("3. Gamme montante et descendante (Sine wave)")
                for nom in gamme_montante:
                    jouer_sine(N[nom], 0.1, canal="BOTH")
                    silence(0.02)
                for nom in reversed(gamme_montante):
                    jouer_sine(N[nom], 0.1, canal="BOTH")
                    silence(0.02)
                print("Test terminé !")
            
    dernier_bouton = touche
    utime.sleep_ms(20)  # Pause courte pour ne pas saturer le processeur
    
    
    
    