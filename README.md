# 🎹 uCompute-Studio

**uCompute-Studio** is an open-architecture I2S audio and MIDI expansion board designed to enrich the **uCompute Ecosystem**. Thanks to its open, standardized pinout, it can also be used directly as a standalone synthesizer and MIDI interface with a **vanilla Raspberry Pi Pico (RP2040 / RP2350)** — no carrier board required.

Based on the hardware design of [MidiSynth-HAT](https://github.com/JPMichon/MidiSynth-HAT), **uCompute-Studio** brings high-fidelity 32-bit I2S stereo audio and hardware MIDI IN/OUT to compact microcontroller projects.

---

## 🔗 Universal Ecosystem & Standalone Compatibility

Because the entire **uCompute** hardware lineage shares a common front expansion header (`5V`, `GND`, `3V3`, `GP16`–`GP18`, `GP00`–`GP01`), **uCompute-Studio** requires zero wiring changes across platforms:

- **💻 RP2040 µCompute & 🚀 RP2350 µCompute2:** Plugs directly into the bottom expansion port of the flagship SMD boards. On the **RP2350 µCompute2** (running at 150 MHz with extended flash), the extra processing headroom enables even richer wavetable synthesis alongside the onboard 240×240 IPS display and MicroSD storage.
- **🎓 µCompute Junior:** Designed as the accessible, beginner-friendly "little brother" of the flagship boards using a *Bring Your Own Pico* approach and easy-to-solder 0805 components. Paired with **uCompute-Studio**, it forms an approachable, full-featured DIY synthesizer with screen and controls — without requiring fine-pitch QFN soldering expertise.
- **🍓 Vanilla Raspberry Pi Pico / Pico 2:** Built on an open architecture, **uCompute-Studio** can be wired or socketed directly to a standard Raspberry Pi Pico for ultra-compact, standalone MIDI-to-Audio synthesis.

---

## ✨ Key Features

- **Dual Compatibility:** Plug-and-play integration with the **uCompute Ecosystem** or direct standalone operation with a standard **Raspberry Pi Pico**.
- **High-Quality Stereo Audio:** Uses the **PCM5102A** I2S DAC module (up to 32-bit / 384 kHz) with dedicated `LEFT`, `AGND`, and `RIGHT` analog outputs.
- **Opto-Isolated MIDI Interface:**
  - Standard 5-pin DIN **MIDI-IN** isolated via a high-gain **TLP785GB** optocoupler with calibrated pull-up resistors (`R3`/`R4`) for crisp 31,250 baud signal edges.
  - Buffered **MIDI-OUT** (`GP00`) and dedicated activity LEDs (`IN` / `OUT`) driven through a **74HCT14D** Schmitt-trigger inverter so indicator loads never affect the UART RX line.
- **Real-Time MicroPython Sound Engine:** Includes dual-core (`_thread`) and native ARM assembly (`@micropython.viper`) firmware turning the board into an expressive, low-latency standalone MIDI synthesizer.

---

## 📸 Hardware Prototype & Validation

Before committing to the final 2-layer PCB fabrication, the circuit was fully prototyped and validated on perfboard. This development board was used to tune the **TLP785GB** optocoupler biasing resistors (`R3`/`R4`), verify power rail decoupling (`100 µF`) on the **PCM5102A** DAC, and benchmark the dual-core `@micropython.viper` audio engine in real time.

<img width="833" height="492" alt="image" src="https://github.com/user-attachments/assets/53d46fe3-39ef-4993-a8fe-07815b479253" />



---

## 📌 GPIO Pinout & Hardware Mapping

| Function | Pico GPIO | uCompute / Module Pin | Notes |
| :--- | :---: | :---: | :--- |
| **MIDI OUT (TX)** | `GP00` | `MIDI-OUT` | 31,250 baud UART0 TX (buffered) |
| **MIDI IN (RX)** | `GP01` | `MIDI-IN` | 31,250 baud UART0 RX (via `TLP785GB`) |
| **I2S Data (DIN)** | `GP16` | `PCM5102A DIN` | Serial Audio Data |
| **I2S Bit Clock (BCK)** | `GP17` | `PCM5102A BCK` | Bit Clock |
| **I2S Word Select (LCK)** | `GP18` | `PCM5102A LCK` | Left/Right Clock (`BCK + 1` required by MicroPython) |
| **Power (DAC)** | `VBUS` | `PCM5102A VIN` | 5V supply (internal 3.3V LDO on DAC module) |
| **Logic & MIDI Supply** | `3V3` | `3.3V` | Powers `74HCT14D`, pull-ups, and MIDI loop |

---

## ⚠️ Mandatory PCM5102A Solder Jumpers

Most GY-PCM5102 DAC breakout boards ship with their configuration pads open on the underside. Before soldering the module onto **uCompute-Studio**, you **must bridge the 4 solder jumpers** on the back of the PCM5102A PCB as follows:

| Pad | Pin Name | Setting | Function |
| :---: | :---: | :---: | :--- |
| **H1L** | `FLT` | **L** (GND) | Normal latency digital filter |
| **H2L** | `DEMP` | **L** (GND) | De-emphasis filter disabled |
| **H3L** | `XSMT` | **H** (3.3V) | **Soft Un-Mute** (board stays silent if left open or at L) |
| **H4L** | `FMT` | **L** (GND) | Standard I2S audio format |

> **Note:** On the **uCompute-Studio** PCB, the `SCK` pin of the PCM5102A is tied directly to `GND`, allowing the DAC to generate its internal system clock from `BCK`.

---

## 🛠️ Hardware & Assembly Notes

- **Protection Diode (`D1`):** A fast-switching **1N4148** signal diode is recommended across the optocoupler input for reverse-polarity protection with minimal parasitic capacitance (~4 pF) and near-zero reverse leakage on the 5 mA MIDI current loop.
- **Mounting Tip:** Using female pin headers for the **PCM5102A** module is recommended so it can be easily inspected or swapped if needed.
- **PCB Stackup:** 2-layer PCB with dedicated ground planes (`GND`) on both Top and Bottom layers for clean analog audio separation.

---

## 💻 Firmware & Test Scripts (`firmware/`)

1. **`firmware/main.py` — Expressive Real-Time MIDI Synthesizer:**
   - Runs the audio engine on **Core 1** using `@micropython.viper` native ARM code (`32 kHz` stereo, 4 ms buffer latency) while **Core 0** handles incoming MIDI events on `GP01`.
   - **Velocity-to-Volume & Timbre:** Dynamically morphs between a pure sine wavetable (`WAVE_SOFT`) and a harmonic-rich wavetable (`WAVE_BRIGHT`) depending on key velocity.
   - **Performance Controls:** Full support for **Pitch Bend** (±2 semitones) and **Modulation Wheel** (`CC #1` LFO vibrato).
   - *Standalone Boot:* Save this file as `main.py` on your Raspberry Pi Pico to boot straight into synth mode on USB power.

2. **`firmware/tests/test_dac_stereo_mario.py` — I2S Audio & Polyphony Diagnostic:**
   - Verifies Left/Right stereo channel separation (`440 Hz` sine wave), plays a pure sine scale, and runs a 3-voice `@micropython.viper` polyphonic chiptune test.

3. **`firmware/tests/test_midi_monitor.py` — Hardware MIDI Diagnostic:**
   - Monitors incoming Note On/Off, Control Change, and Pitch Bend messages on `GP01` and echoes data to `MIDI-OUT` (`GP00`) to validate optocoupler timing and status LEDs.

---

## 📂 Repository Contents

```text
uCompute-Studio/
├── Gerber_PCB_uCompute-Studio.zip   # Ready-to-manufacture Gerber files
├── Schematic_uCompute-Studio.pdf    # Full electronic schematic (EasyEDA)
├── images/
│   └── prototype_perfboard.jpg      # Hand-wired perfboard hardware prototype
├── firmware/
│   ├── main.py                      # Real-time Viper MIDI synthesizer
│   └── tests/
│       ├── test_dac_stereo_mario.py # Stereo & polyphonic DAC test
│       └── test_midi_monitor.py     # MIDI IN/OUT hardware diagnostic
├── LICENSE                          # CC BY-NC-SA 4.0 License
└── README.md
```

---

## 📜 License & Ecosystem

This project is part of the **[uCompute Ecosystem](https://github.com)** and is released under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license. Commercial manufacturing or distribution of bare PCBs, kits, or derivatives is prohibited without prior authorization.
