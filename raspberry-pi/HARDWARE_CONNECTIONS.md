# Smart AI Bin – Hardware Connections (BCM)

All pin numbers below use **BCM** (Broadcom) numbering. Use a Pi pinout diagram (e.g. [pinout.xyz](https://pinout.xyz)) to find physical pins.

---

## 1. Servos (4× – one per bin door)

| Bin            | Servo wire      | Raspberry Pi        |
|----------------|-----------------|---------------------|
| **Dry**        | Signal (Orange) | **GPIO 5**          |
| **Wet**        | Signal (Orange) | **GPIO 6**          |
| **Electronic** | Signal (Orange) | **GPIO 12**         |
| **Unknown**    | Signal (Orange) | **GPIO 13**         |

**All servos (common):**
- **VCC (Red)**   → 5V (e.g. Pin 2 or 4)
- **GND (Brown/Black)** → GND (e.g. Pin 6, 9, 14, 20, 25, 30, 34, 39)

Use a **5V supply** that can handle 4 servos; share **GND** with the Pi.

---

## 2. IR proximity sensor (object detection)

| Sensor wire | Raspberry Pi |
|-------------|--------------|
| **OUT**     | **GPIO 17**  |
| **VCC**     | 3.3V or 5V (check module) |
| **GND**     | GND          |

---

## 3. Ultrasonic sensors (HC-SR04) – 4× bin level

**Important:** Echo output is **5V**. Pi GPIO is **3.3V**. Use a **voltage divider** (e.g. 1kΩ + 2kΩ) or level shifter on each **Echo** line.

| Bin            | Trigger (GPIO) | Echo (GPIO) | VCC | GND |
|----------------|----------------|-------------|-----|-----|
| **Dry**        | **23**         | **24**      | 5V  | GND |
| **Wet**        | **25**         | **8**       | 5V  | GND |
| **Electronic** | **7**          | **1** *     | 5V  | GND |
| **Processing** | **20**         | **21**      | 5V  | GND |

\* GPIO 1 is often used for I2C (SDA). If you have I2C devices, use another free GPIO (e.g. 16) for this Echo and update `gpio_setup.py` → `ULTRASONIC_ELECTRONIC`.

**Per sensor:**
- **VCC**    → 5V
- **GND**    → GND
- **Trigger** → GPIO (as above)
- **Echo**   → GPIO (as above), **via voltage divider** (Echo → 1kΩ → GPIO, 2kΩ from that junction to GND)

---

## 4. LEDs (optional)

| LED    | Connection                          |
|--------|-------------------------------------|
| **Status (e.g. green)** | Anode → **GPIO 26** (via ~220Ω) → LED → GND |
| **Error (e.g. red)**    | Anode → **GPIO 19** (via ~220Ω) → LED → GND |

---

## 5. Camera

- **USB webcam:** plug into any USB port; set `CAMERA_ID` in config (often `0`).
- **Pi Camera (rpicam):** connect to CSI; enable in `raspi-config` → Interface → Camera. Code can use Picamera2 fallback.

---

## Quick reference table (BCM GPIO only)

| Component        | GPIO / note        |
|------------------|--------------------|
| Servo Dry        | 5                  |
| Servo Wet        | 6                  |
| Servo Electronic | 12                 |
| Servo Unknown    | 13                 |
| IR sensor        | 17                 |
| Ultrasonic Dry   | Trig 23, Echo 24   |
| Ultrasonic Wet   | Trig 25, Echo 8    |
| Ultrasonic Electronic | Trig 7, Echo 1 |
| Ultrasonic Processing | Trig 20, Echo 21 |
| LED Status       | 26                 |
| LED Error        | 19                 |

---

## Power

- **Pi:** 5V 3A USB-C.
- **Servos:** 5V capable of ~1–2A total (or external 5V with common GND).
- **Sensors:** 3.3V or 5V as per module; share GND with Pi.

---

## Why "No valid distance measurements"?

The code only accepts distances **between 2 cm and 400 cm**. You get "No valid distance" when **every** reading is outside that range or when the Pi never sees a proper echo pulse.

| What you see in the log | Meaning | Fix |
|-------------------------|--------|-----|
| **Last: pulse=0.0000s dist=0.0cm** | Echo pin never went HIGH. Pi never saw the echo. | Wrong Echo pin, Echo not connected, or **Echo is 5V and Pi needs 3.3V** → use a voltage divider on Echo. |
| **Last: pulse=0.1000s dist=1715.0cm** (or very large) | Echo stayed HIGH until timeout (0.1 s). Pi thinks the pulse is huge. | Echo pin stuck HIGH: 5V on 3.3V pin, or Echo shorted to VCC. Use a **voltage divider** on Echo (5V → 3.3V). |
| **Last: dist=0.5cm** or **dist=450cm** | Pulse was read but distance outside 2–400 cm. | Normal if nothing in range or sensor pointed at sky. For a bin, aim sensor at bottom; check Trigger/Echo not swapped. |
| **Last: pulse=0.0012s dist=20.6cm** (in range) but still "No valid" | Rare: only some samples valid; code needs 2–400 cm. | Check wiring is solid; try reducing noise (short wires, one sensor at a time). |

**Most common cause:** HC-SR04 **Echo outputs 5V**, Raspberry Pi GPIO is **3.3V max**. If Echo is wired **directly** to the Pi:

- The Pi may never see a clean 0→1→0 pulse, or
- You risk damaging the GPIO.

**Fix:** Put a **voltage divider** on the Echo line: e.g. 1kΩ from Echo to GPIO, 2kΩ from that GPIO junction to GND, so the Pi sees about 3.3V when Echo is 5V.

---

## Matching the code

Pin definitions are in **`raspberry-pi/hardware/gpio_setup.py`**. If you change wiring, update that file so the code matches your connections.
