import network
import time
import json
import struct
import gc
from machine import Pin, SoftI2C
import ssd1306

try:
    import requests
except ImportError:
    import urequests as requests

WIFI_SSID = "Columbia University"


CLOUD_URL = "https://YOUR_SERVER_HOST:PORT/predict"

UPLOAD_TOKEN = "YOUR_CURRENT_UPLOAD_TOKEN"

SCL_PIN = 20
SDA_PIN = 22
ADXL_ADDR = 0x53
OLED_ADDR = 0x3C

SAMPLE_RATE = 50
SAMPLE_COUNT = 128
SAMPLE_INTERVAL_US = 20000

print("Initializing SoftI2C...")
i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=100000)
devices = i2c.scan()
print("I2C devices:", [hex(x) for x in devices])

if OLED_ADDR not in devices:
    raise RuntimeError("OLED not detected")
if ADXL_ADDR not in devices:
    raise RuntimeError("ADXL345 not detected")

oled = ssd1306.SSD1306_I2C(128, 32, i2c, addr=OLED_ADDR)

def display(line1="", line2="", line3=""):
    oled.fill(0)
    oled.text(str(line1)[:16], 0, 0)
    oled.text(str(line2)[:16], 0, 11)
    oled.text(str(line3)[:16], 0, 22)
    oled.show()


display("Lab 6 - CP4", "Initializing")

def write_register(reg, value):
    i2c.writeto_mem(ADXL_ADDR, reg, bytes([value]))
def initialize_adxl():
    device_id = i2c.readfrom_mem(ADXL_ADDR, 0x00, 1)[0]
    print("ADXL345 ID:", hex(device_id))
    if device_id != 0xE5:
        raise RuntimeError("Invalid ADXL345 device ID")

    write_register(0x2D, 0x00)  
    write_register(0x31, 0x08)  
    write_register(0x2C, 0x09)  
    write_register(0x2D, 0x08)  
    time.sleep_ms(100)
    print("ADXL345 initialized successfully")

def read_acceleration():
    data = i2c.readfrom_mem(ADXL_ADDR, 0x32, 6)
    x_raw, y_raw, z_raw = struct.unpack("<hhh", data)
    scale = 0.00390625  
    return [
        round(x_raw * scale, 4),
        round(y_raw * scale, 4),
        round(z_raw * scale, 4),
    ]

initialize_adxl()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Wi-Fi already connected:", wlan.ifconfig()[0])
        return wlan

    print("Connecting to Columbia University...")
    display("Connecting", "Columbia WiFi")
    wlan.connect(WIFI_SSID)
    start = time.ticks_ms()

    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 20000:
            print("Wi-Fi status:", wlan.status())
            display("WiFi Failed", "Check Network")
            raise RuntimeError("Wi-Fi timeout")
        time.sleep_ms(300)

    print("Wi-Fi connected! IP:", wlan.ifconfig()[0])
    display("WiFi Connected", wlan.ifconfig()[0])
    return wlan


def collect_samples():
    display("Recording HAR", "128 samples", "50 Hz")
    print("\nCollecting sensor data...")

    samples = []
    start_us = time.ticks_us()
    for i in range(SAMPLE_COUNT):
        target = time.ticks_add(start_us, i * SAMPLE_INTERVAL_US)
        while time.ticks_diff(target, time.ticks_us()) > 0:
            time.sleep_us(100)
        samples.append(read_acceleration())

    duration = time.ticks_diff(time.ticks_us(), start_us) / 1000000.0
    print("Samples collected:", len(samples))
    print("Duration:", duration, "seconds")
    print("First sample:", samples[0])
    print("Last sample:", samples[-1])
    return samples

OLED_LABELS = {
    "WALKING": "WALKING",
    "WALKING_UPSTAIRS": "UPSTAIRS",
    "WALKING_DOWNSTAIRS": "DOWNSTAIRS",
    "SITTING": "SITTING",
    "STANDING": "STANDING",
    "LAYING": "LAYING",
}

def predict_in_cloud(samples):
    if len(samples) != SAMPLE_COUNT:
        raise ValueError("Expected 128 samples")
    if not UPLOAD_TOKEN or UPLOAD_TOKEN == "YOUR_CURRENT_UPLOAD_TOKEN":
        raise RuntimeError("Configure UPLOAD_TOKEN")

    payload = {
        "device": "ESP32_ADXL345",
        "sample_rate_hz": SAMPLE_RATE,
        "unit": "g",
        "samples": samples,
    }

    body = json.dumps(payload).encode("utf-8")
    del payload
    gc.collect()

    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
        "X-Upload-Token": UPLOAD_TOKEN,
    }

    print("\nSending to NormWear cloud...")
    print("URL:", CLOUD_URL)
    print("JSON size:", len(body), "bytes")
    display("NormWear AI", "Predicting...", "Please wait")

    response = None
    try:
        response = requests.post(CLOUD_URL, data=body, headers=headers)
        status_code = response.status_code

        result = response.json()
        print("HTTP Status:", status_code)
        print("Server response:", result)

        if status_code != 200:
            raise RuntimeError("HTTP error: {}".format(status_code))
        if result.get("status") != "success":
            raise RuntimeError("Prediction failed")
        if result.get("samples_received") != SAMPLE_COUNT:
            raise RuntimeError("Wrong sample count")

        label = result.get("label")
        confidence = result.get("confidence")
        if not isinstance(label, str) or not isinstance(confidence, (int, float)):
            raise RuntimeError("Invalid prediction response")

        print("\n===== HAR PREDICTION =====")
        print("Activity:", label)
        print("Model score:", round(confidence * 100, 1), "%")

        oled_label = OLED_LABELS.get(label, label[:16])
        display("HAR Prediction", oled_label, "Score: {:.1f}%".format(confidence * 100))
        return result

    except Exception as exc:
        print("Prediction ERROR:", repr(exc))
        display("Prediction Fail", str(exc)[:16])
        raise
    finally:
        if response is not None:
            response.close()
        del body
        gc.collect()

def main():
    print("=" * 55)
    print("EECS E4764 - Lab 6 - Checkpoint 4")
    print("ESP32 -> AutoDL NormWear -> OLED")
    print("=" * 55)
    wlan = connect_wifi()
    display("Checkpoint 4", "Ready", "Press ENTER")

    while True:
        try:
            input("\nPress ENTER to collect and predict...")
            if not wlan.isconnected():
                wlan = connect_wifi()
            gc.collect()
            samples = collect_samples()
            result = predict_in_cloud(samples)
            del samples
            gc.collect()
            print("\nCloud prediction received:", result["label"])
            print("Ready for next sample")

        except KeyboardInterrupt:
            print("Program stopped")
            break
        except Exception as exc:
            print("\nCheckpoint 4 error:", repr(exc))
            display("CP4 Error", str(exc)[:16])
            gc.collect()


if __name__ == "__main__":
    main()
