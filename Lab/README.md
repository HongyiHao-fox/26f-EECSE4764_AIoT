# EECS E4764 AIoT Labs

Lab code for Columbia EECS E4764 (AIoT), Fall 2026. The labs run on an ESP32 Feather board with MicroPython and build up from blinking an LED to a smartwatch that recognizes human activity with an LLM.

## Hardware

- ESP32 Feather (MicroPython v1.26)
- SSD1306 128x32 OLED (I2C: SDA 22, SCL 20)
- ADXL345 accelerometer (SPI in Lab 4, I2C at `0x53` in Lab 6)
- 3 push buttons (pins 32, 33, 27), piezo buzzer (pin 12), light sensor (pin 26)
- Built-in LED (pin 13) and NeoPixel (pin 0, power-enable pin 2)

## Repository layout

| Lab | File | Runs on | What it does |
|---|---|---|---|
| 0 | `main.py` | ESP32 | Starter: blink the built-in LED and NeoPixel |
| 1 | `Lab1_checkpoint1.py` | ESP32 | Morse code on the built-in LED |
| 1 | `Lab1_checkpoint2.py` | ESP32 | Blink two LEDs at different rates without blocking (`ticks_ms`) |
| 2 | `Lab2_checkpoint1.py` | ESP32 | Light sensor driving LED/piezo through PWM *(incomplete)* |
| 3 | `Lab3_checkpoint1.py` | ESP32 | OLED clock using the RTC, set with buttons |
| 3 | `Lab3_checkpoint2.py` | ESP32 | Adds automatic OLED brightness from the light sensor |
| 3 | `Lab3_checkpoint3.py` | ESP32 | Adds an alarm with a piezo tone and an on-screen alert |
| 3 | `Lab3_checkpoint4.py` | ESP32 | Complete clock with alarm and brightness control |
| 4 | `Lab4_checkpoint1.py` | ESP32 | Reads the ADXL345 over SPI; tilting scrolls the clock display |
| 4 | `Lab4_checkpoint2.py` | ESP32 | Joins WiFi and shows location from ip-api.com |
| 4 | `Lab4_checkpoint3.py` | ESP32 | Adds current weather from Open-Meteo |
| 4 | `Lab4_checkpoint4.py` | ESP32 | Sends push notifications through ntfy.sh |
| 5 | `Lab5_checkpoint1.py` | PC | Gradio app that transcribes speech with Whisper |
| 5 | `Lab5_checkpoint2_server.py` | ESP32 | HTTP JSON command server (time, alarm, text, location, weather) |
| 5 | `Lab5_checkpoint2_client.py` | PC | Sends test commands to the ESP32 server |
| 5 | `Lab5_checkpoint3.py` | PC | Whisper + DeepSeek: turns speech into a JSON command |
| 5 | `Lab5_checkpoint4_app.py` | PC | Full voice pipeline: Whisper → DeepSeek → ESP32 over HTTP |
| 5 | `Lab5_checkpoint4_server.py` | ESP32 | Command server for checkpoint 4 |
| 6 | `Lab6_checkpoint1.py` | PC | Gemini classifies activities in the UCI HAR dataset (direct vs. chain-of-thought prompts) |
| 6 | `Lab6_checkpoint2_esp32.py` | ESP32 | Records 128 accelerometer samples at 50 Hz and serves them over TCP (port 8765) |
| 6 | `Lab6_checkpoint2_pc.py` | PC | Fetches samples from the ESP32, classifies them with Gemini, sends the result back |
| 6 | `Lab6_checkpoint3.py` | ESP32 | Uploads samples to a cloud server over HTTPS |
| 6 | `Lab6_checkpoint4.py` | ESP32 | Gets an activity prediction from the cloud server and shows it on the OLED |

When you run the Lab 6 scripts, they save their output to `Lab6/results_gemini/` (checkpoint 1) and `Lab6/results_checkpoint2/` (checkpoint 2). Git ignores both folders.

## Running the ESP32 code

1. Flash MicroPython onto the ESP32 (the firmware is available at [micropython.org](https://micropython.org/download/ESP32_GENERIC/)).
2. Copy `ssd1306.py` to the board (needed from Lab 3 onward).
3. Open the script in Thonny and run it, or save it to the board as `main.py` so it runs at boot.

## Running the PC code

Use Python 3.11. Install what each lab needs:

```bash
# Lab 5 (also requires ffmpeg)
pip install gradio openai openai-whisper

# Lab 6
pip install numpy torch google-genai requests
```

Put API keys in environment variables, not in the code:

```bash
export DS_API_KEY="..."        # Lab 5 (DeepSeek)
export GEMINI_API_KEY="..."    # Lab 6 (Gemini)
export ESP32_IP="..."          # Lab5_checkpoint4_app.py (optional)
```

Windows PowerShell: `$env:GEMINI_API_KEY="..."`

## Placeholders to fill in

Secrets and addresses have been replaced with placeholders. Set them before you run the code:

| Placeholder | File(s) | Set it to |
|---|---|---|
| `YOUR_ESP32_IP` | `Lab5_checkpoint2_client.py`, `Lab6_checkpoint2_pc.py` | The IP address the ESP32 prints after it joins WiFi |
| `YOUR_SERVER_HOST:PORT` | `Lab6_checkpoint3.py`, `Lab6_checkpoint4.py` | Your cloud server's address |
| `YOUR_CURRENT_UPLOAD_TOKEN` | `Lab6_checkpoint3.py`, `Lab6_checkpoint4.py` | The upload token your server checks |
| `NTFY_TOPIC` | `Lab4_checkpoint4.py` | A unique topic name you choose |

The WiFi code connects to the open `Columbia University` network. To use a different network, change `WIFI_SSID`/`SSID` (and `PASSWORD` where the script has it).

## Lab 6 dataset

`Lab6_checkpoint1.py` uses the [UCI Human Activity Recognition Using Smartphones](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones) dataset. It is too large for git and is listed in `.gitignore`. Download it and unzip it so the folders look like this:

```
Lab6/human+activity+recognition+using+smartphones/UCI HAR Dataset/UCI HAR Dataset/{train,test}/
```

Then run:

```bash
cd Lab6
python Lab6_checkpoint1.py --num-samples 10 --seed 42
```

The server code for Lab 6 checkpoints 3 and 4 is not included in this repository.
