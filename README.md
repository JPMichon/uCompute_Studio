# 🎹 uCompute-Studio

**uCompute-Studio** is an open-architecture I2S audio and MIDI expansion board designed to enrich the **uCompute Ecosystem**. Thanks to its open, standardized pinout, it can also be used directly as a standalone synthesizer and MIDI interface with a **vanilla Raspberry Pi Pico (RP2040 / RP2350)** — no carrier board required.

<img width="1003" height="451" alt="image" src="https://github.com/user-attachments/assets/59799987-61ee-4314-898c-2d1ac9b2d84a" />


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

<img width="1727" height="1108" alt="image" src="https://github.com/user-attachments/assets/76f9e6f0-e4ea-412d-8429-b20c8c6e6f71" />
<br>

*As shown in the photo above, bridge **H1L**, **H2L**, and **H4L** to the **L** side (bottom pads), and bridge **H3L (`XSMT`)** to the **H** side (top pad, indicated by the arrow) to enable audio output.*


| Pad | Pin Name | Setting | Function |
| :---: | :---: | :---: | :--- |
| **H1L** | `FLT` | **L** (GND) | Normal latency digital filter |
| **H2L** | `DEMP` | **L** (GND) | De-emphasis filter disabled |
| **H3L** | `XSMT` | **H** (3.3V) | **Soft Un-Mute** (board stays silent if left open or at L) |
| **H4L** | `FMT` | **L** (GND) | Standard I2S audio format |
<br>

> **Note:** On the **uCompute-Studio** PCB, the `SCK` pin of the PCM5102A is tied directly to `GND`, allowing the DAC to generate its internal system clock from `BCK`.

---

## 🛠️ Hardware & Assembly Notes

- **Protection Diode (`D1`):** A fast-switching **1N4148** signal diode is recommended across the optocoupler input for reverse-polarity protection with minimal parasitic capacitance (~4 pF) and near-zero reverse leakage on the 5 mA MIDI current loop.
- **Mounting Tip:** Using female pin headers for the **PCM5102A** module is recommended so it can be easily inspected or swapped if needed.
- **PCB Stackup:** 2-layer PCB with dedicated ground planes (`GND`) on both Top and Bottom layers for clean analog audio separation.

---

## 📋 Bill of Materials (BOM)

### PCB Components

| Qty | Designator | Component / Value | Package / Footprint | Notes |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `AUDIO` | JST XH 2.54mm 3-Pin Header | `CONN-TH_XH2.54_3PIN` | Stereo analog audio output (`LEFT`, `AGND`, `RIGHT`) |
| **2** | `MIDI-IN`, `MIDI-OUT` | JST XH-5A 2.50mm 5-Pin Header | `CONN-TH_5P-P2.50_XH-5A` | Modular MIDI interface connectors |
| **2** | `IN`, `OUT` | Green LED 0805 | `LED0805-RD_GREEN` | MIDI IN / OUT activity indicators |
| **1** | `5V` | Blue LED 0805 | `LED0805-RD_BLUE` | Power indicator |
| **2** | `C3`, `C5` | 10 nF Capacitor | `C0805` | Decoupling / filtering |
| **1** | `C4` | 100 µF Electrolytic Capacitor | `CAP-SMD_BD5.0-L5.3-W5.3-LS6.3-FD` | 5V power rail decoupling for DAC |
| **1** | `D9` | 1N4148W Switching Diode | `SOD-123FL_L2.8-W1.8-LS3.7-RD` | Reverse-polarity protection (`1N5819` also compatible) |
| **1** | `H1` | Pin Header 14-Pin (2.54 mm) | `HDR-TH_14P-P2.54-V-M` | Main expansion bus connector |
| **1** | `R2` | 2 kΩ Resistor | `R0805` | — |
| **1** | `R3` | 390 Ω Resistor | `R0805` | Calibrated MIDI optocoupler biasing |
| **1** | `R4` | 470 Ω Resistor | `R0805` | Calibrated MIDI optocoupler pull-up |
| **2** | `R5`, `R6` | 220 Ω Resistor | `R0805` | MIDI current-loop limiting |
| **2** | `R7`, `R8` | 1 kΩ Resistor | `R0805` | LED current limiting |
| **1** | `U2` | TLP785GB Optocoupler | `SOP-4_L6.5-W4.6-P2.54-LS10.0` | High-CTR MIDI-IN optical isolation |
| **1** | `U3` | 74HCT14D Hex Schmitt Inverter | `SOP-14_L8.7-W3.9-P1.27-LS6.0-BL` | Activity LED buffer & MIDI-OUT driver |
| **1** | `U4` | PCM5102A DAC Module | `GY-PCM5102` | Stereo I2S DAC *(bridge jumpers before soldering)* |

### MIDI Adapter Cable Accessories

| Qty | Item | Description |
| :---: | :--- | :--- |
| **2** | DIN-5 Female Socket | Standard 5-pin 180° MIDI panel-mount connectors *(or 1/8" / 1/4" TRS plugs)* |
| **2** | JST XH-5A Female Housing | 5-pin crimp connector housings (with crimp terminals) |
| **6** | Hookup Wires | 3 wires per adapter cable (`GND`, `SOURCE`, `SINK`) |
| — | Heat-Shrink Tubing | For insulating soldered DIN-5 / TRS pins |

---

## 🔌 MIDI Connector & Adapter Cable Wiring (JST XH-5A)

**uCompute-Studio** uses compact 5-pin **JST XH-5A (2.54 mm)** headers for `MIDI-IN` and `MIDI-OUT`. Beyond keeping the PCB footprint compact and providing generous pin spacing, this modular connector approach allows you to easily build interchangeable adapter cables for **any standard MIDI physical format** — whether classic **5-pin DIN**, **1/8" (3.5 mm) TRS** (Type A or Type B), or **1/4" (6.35 mm) TRS** — saving you from having to buy bulky commercial MIDI adapters or stack dongles.

<img width="458" height="236" alt="image" src="https://github.com/user-attachments/assets/9a3e6bb0-89b5-4878-bc61-794e5fab1791" /><br>
<img width="1022" height="206" alt="image" src="https://github.com/user-attachments/assets/cd95eaa6-82cb-49d7-8074-0b840c8683f4" />

### Pinout Mapping (JST XH-5A to DIN-5 & TRS)

Following the MIDI 1.0 electrical specification (only 3 conductors are required: `SINK`, `GND`, and `SOURCE`). *Note: Any wire colors can be used as long as the pin-to-pin mapping below is respected.*

| PCB Header (`JST XH-5A`) | DIN-5 Pin |  MIDI Signal Function |
| :---: | :---: |  :--- |
| **Pin 1 (`NC`)** | — | Unused (spacing / isolation) |
| **Pin 2 (`GND`)** | **Pin 2** | Shield / Ground *(connected on MIDI-OUT; optional/isolated on MIDI-IN)* |
| **Pin 3 (`NC`)** | — | Unused (spacing / isolation) |
| **Pin 4 (`SOURCE`)** |  **Pin 4** | Current Source ( +5V via resistor)  |
| **Pin 5 (`SINK`)** | **Pin 5** | Current Sink (Data Signal) |

> **⚠️ Soldering Tip:** Always verify the pin numbers molded into your DIN-5 housing (**Pin 4** to XH-5A **Pin 4 `SOURCE`**, **Pin 5** to XH-5A **Pin 5 `SINK`**, and **Pin 2** to XH-5A **Pin 2 `GND`**; outer pins 1 and 3 remain unconnected). For **TRS Type B** adapters, simply swap `SOURCE` (Tip) and `SINK` (Ring).

---


## 📜 License & Ecosystem

This project is part of the **[uCompute Ecosystem](https://github.com)** and is released under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license. Commercial manufacturing or distribution of bare PCBs, kits, or derivatives is prohibited without prior authorization.

---

## ☕ Support the Project

If you appreciate my work and would like to buy me a coffee to support my future soldering and coding projects on a voluntary basis, you can leave me a [**tip on Ko-fi** ](https://ko-fi.com/jpmichon). It is entirely optional and greatly appreciated!

