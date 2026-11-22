# 🧪 MicroPython Test Suite & Audio/MIDI Examples (`testCode`)

This directory contains a collection of **MicroPython** scripts designed to validate each hardware subsystem of the **uCompute-Studio** expansion board (and standalone **Raspberry Pi Pico / Pico 2** setups) step by step — from basic I2S DAC sine-wave checks to dual-core `@micropython.viper` real-time synthesis and SD-card MIDI playback.

---

## 📂 Required Libraries (`testCode/lib/`)

The **`lib/`** subfolder holds essential MicroPython drivers (such as the **ST7789** display driver, **MicroSD** SPI interface, and custom helpers) required for playback and display scripts. Copy the entire contents of `testCode/lib/` to the root `/lib` directory on your board's filesystem.

---

## 📋 Script Overview

### 1. 🔊 I2S Audio & DAC Verification (`PCM5102A`)
Use these scripts first after soldering your `PCM5102A` module (and bridging jumpers **H1L**, **H2L**, **H3L**, and **H4L**) to confirm clean stereo audio output.

| File | Description | Hardware Required |
| :--- | :--- | :--- |
| **`Test_440hz_PCM5102a.py`** | Generates a continuous **440 Hz (A4)** reference sine wave over I2S (`GP16`–`GP18`) to verify basic DAC communication and `XSMT` un-mute status. | `uCompute-Studio` + Pico |
| **`Test_Stereo_PCM5102a.py`** | Tests independent **LEFT** and **RIGHT** audio channels to validate stereo separation and `AUDIO` JST-XH pinout wiring. | `uCompute-Studio` + Pico |

---

### 2. 🎹 Hardware MIDI IN & MIDI OUT Diagnostics
Use these scripts to test the opto-isolated **MIDI-IN** (`TLP785GB` on `GP01`) and buffered **MIDI-OUT** (`74HCT14D` on `GP00`) interfaces at **31,250 baud**.

| File | Description | Hardware Required |
| :--- | :--- | :--- |
| **`test_midi_IN.py`** | Listens on `UART0 RX` (`GP01`) and prints incoming MIDI messages (Note On/Off, Control Change, Pitch Bend, etc.) to the REPL console. | `uCompute-Studio` + External MIDI Controller |
| **`PlayMelody_Midi_CH1.py`** | Sends a hardcoded test melody out via **MIDI-OUT** (`GP00`) on **MIDI Channel 1** to trigger an external synth or sound module. | `uCompute-Studio` + External MIDI Synth |
| **`PlayMelody_Midi_CH2.py`** | Sends a test melody out via **MIDI-OUT** (`GP00`) on **MIDI Channel 2** (useful for testing multi-timbral modules like MT-32 / General MIDI). | `uCompute-Studio` + External MIDI Synth |

---

### 3. 🎛️ Real-Time MicroPython Synthesizer Engines
Standalone monophonic synthesizer engines combining **MIDI-IN** reception with real-time I2S waveform generation on the `PCM5102A` DAC.

| File | Description | Key Features |
| :--- | :--- | :--- |
| **`test_SynthMono_MIDI_PCM5102a.py`** | Initial proof-of-concept monophonic MIDI synthesizer converting incoming MIDI notes into real-time I2S audio. | MIDI-to-I2S real-time synthesis |
| **`test_SynthMono_MIDI_PCM5102a_V2.py`** | Improved **V2** monophonic synth engine featuring optimized audio buffering, lower latency, and enhanced waveform/envelope handling (`@micropython.viper` / dual-core ready). | Low-latency audio buffer & refined synthesis |

---

### 4. 📻 MicroSD Card MIDI Players & Jukebox
Scripts for streaming `.mid` files stored on a MicroSD card out to external MIDI hardware (and displaying playback telemetry on the uCompute IPS screen).

| File | Description | Hardware Required |
| :--- | :--- | :--- |
| **`PlayMidi_SD.py`** | Core MicroSD `.mid` file parser and real-time MIDI event scheduler sending note/control data through **MIDI-OUT**. | `uCompute` (with SD) + External MIDI Synth |
| **`Midi_player_FromSD.py`** | Standalone SD-card MIDI file player routine for sequential track playback. | `uCompute` (with SD) + External MIDI Synth |
| **`st7789_Midi_SD_Jukebox_V2.py`** | Full-featured **Standalone MIDI Jukebox (V2)** with a **240×240 ST7789 IPS** graphical interface, track selection, real-time BPM/progress display, and MicroSD `.mid` streaming. | **RP2040 µCompute** / **RP2350 µCompute2** + `uCompute-Studio` |

---

## 🚀 Quick Start Guide

1. **Flash MicroPython:** Ensure your **Raspberry Pi Pico / Pico 2** or **uCompute** board is running an up-to-date build of [MicroPython for RP2040 / RP2350](https://micropython.org "Download MicroPython for Raspberry Pi Pico").
2. **Verify Pin Mapping:** All scripts use the standardized **uCompute-Studio** pinout:
   * **MIDI OUT (`UART0 TX`):** `GP00`
   * **MIDI IN (`UART0 RX`):** `GP01`
   * **I2S Data (`DIN`):** `GP16`
   * **I2S Bit Clock (`BCK`):** `GP17`
   * **I2S Word Select (`LCK`):** `GP18`
3. **Upload & Run:** Open any `.py` script in **Thonny** (or upload via `mpremote`) and run it directly on your board.
   > **Note for Jukebox / SD scripts:** Make sure your MicroSD card is formatted as **FAT32** and contains standard Type 0 or Type 1 `.mid` files in the expected folder path before running `st7789_Midi_SD_Jukebox_V2.py`.
