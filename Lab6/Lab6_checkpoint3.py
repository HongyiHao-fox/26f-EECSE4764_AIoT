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
    try:
        import urequests as requests
    except ImportError:
        raise ImportError(
            "Install requests on ESP32 using mip"
        )
WIFI_SSID = "Columbia University"

CLOUD_URL = "https://YOUR_SERVER_HOST:PORT/upload"

UPLOAD_TOKEN = "YOUR_CURRENT_UPLOAD_TOKEN"

SCL_PIN = 20
SDA_PIN = 22

ADXL_ADDR = 0x53
OLED_ADDR = 0x3C

SAMPLE_RATE = 50
SAMPLE_COUNT = 128

SAMPLE_INTERVAL_US = 20000

print("Initializing SoftI2C...")

i2c = SoftI2C(
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN),
    freq=100000
)

devices = i2c.scan()

print("I2C devices:", [hex(x) for x in devices])

if OLED_ADDR not in devices:
    raise RuntimeError("OLED not detected")

if ADXL_ADDR not in devices:
    raise RuntimeError("ADXL345 not detected")

print("I2C initialization successful")

oled = ssd1306.SSD1306_I2C(
    128,
    32,
    i2c,
    addr=OLED_ADDR
)

def display(line1="", line2="", line3=""):

    oled.fill(0)

    oled.text(str(line1)[:16], 0, 0)
    oled.text(str(line2)[:16], 0, 11)
    oled.text(str(line3)[:16], 0, 22)

    oled.show()


display(
    "Lab 6 - CP3",
    "Initializing"
)

def write_register(reg, value):

    i2c.writeto_mem(
        ADXL_ADDR,
        reg,
        bytes([value])
    )


def initialize_adxl():

    device_id = i2c.readfrom_mem(
        ADXL_ADDR,
        0x00,
        1
    )[0]

    print("ADXL345 ID:", hex(device_id))

    if device_id != 0xE5:
        raise RuntimeError(
            "Invalid ADXL345 device ID"
        )


    write_register(0x2D, 0x00)


    write_register(0x31, 0x08)


    write_register(0x2C, 0x09)


    write_register(0x2D, 0x08)

    time.sleep_ms(100)

    print("ADXL345 initialized successfully")


def read_acceleration():

    data = i2c.readfrom_mem(
        ADXL_ADDR,
        0x32,
        6
    )

    x_raw, y_raw, z_raw = struct.unpack(
        "<hhh",
        data
    )

    scale = 0.00390625

    x = x_raw * scale
    y = y_raw * scale
    z = z_raw * scale

    return [
        round(x, 4),
        round(y, 4),
        round(z, 4)
    ]


initialize_adxl()






def connect_wifi():

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    if wlan.isconnected():

        print("WiFi already connected")
        print("IP:", wlan.ifconfig()[0])

        return wlan

    display(
        "Connecting",
        "Columbia WiFi"
    )

    print("Connecting to Columbia University...")


    wlan.connect(WIFI_SSID)

    start_time = time.ticks_ms()

    while not wlan.isconnected():

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start_time
        )

        if elapsed > 20000:

            print("WiFi timeout")
            print("WiFi status:", wlan.status())

            display(
                "WiFi Failed",
                "Check Network"
            )

            raise RuntimeError(
                "Cannot connect to Columbia WiFi"
            )

        time.sleep_ms(300)

    print("WiFi connected!")
    print("IP address:", wlan.ifconfig()[0])

    display(
        "WiFi Connected",
        wlan.ifconfig()[0]
    )

    return wlan

def collect_samples():

    display(
        "Recording HAR",
        "128 samples",
        "50 Hz"
    )

    print("\nCollecting sensor data...")

    samples = []

    start_us = time.ticks_us()

    for i in range(SAMPLE_COUNT):

        target = time.ticks_add(
            start_us,
            i * SAMPLE_INTERVAL_US
        )

        while time.ticks_diff(
            target,
            time.ticks_us()
        ) > 0:

            time.sleep_us(100)

        acceleration = read_acceleration()

        samples.append(acceleration)

    end_us = time.ticks_us()

    duration = time.ticks_diff(
        end_us,
        start_us
    ) / 1000000.0

    print("Samples collected:", len(samples))
    print("Duration:", duration, "seconds")
    print("First sample:", samples[0])
    print("Last sample:", samples[-1])

    return samples

def upload_to_cloud(samples):

    if len(samples) != 128:
        raise ValueError(
            "Expected 128 samples"
        )

    if UPLOAD_TOKEN == "YOUR_CURRENT_UPLOAD_TOKEN":
        raise RuntimeError(
            "Please configure UPLOAD_TOKEN"
        )

    print("\nPreparing JSON payload...")

    payload = {
        "device": "ESP32_ADXL345",
        "sample_rate_hz": SAMPLE_RATE,
        "unit": "g",
        "samples": samples
    }

    json_data = json.dumps(payload)

    print("JSON size:", len(json_data), "characters")

    headers = {
        "Content-Type": "application/json",
        "X-Upload-Token": UPLOAD_TOKEN
    }

    print("\nUploading to AutoDL...")
    print("URL:", CLOUD_URL)

    display(
        "Cloud Upload",
        "Sending Data",
        "Please wait"
    )

    response = None

    try:

        gc.collect()

        response = requests.post(
            CLOUD_URL,
            data=json_data,
            headers=headers
        )

        status_code = response.status_code

        response_text = response.text

        print("HTTP Status:", status_code)
        print("Server Response:", response_text)

        if status_code != 200:
            raise RuntimeError(
                "HTTP upload failed: "
                + str(status_code)
            )

        result = json.loads(response_text)

        if result.get("status") != "success":
            raise RuntimeError(
                "Server did not report success"
            )

        if result.get("saved") is not True:
            raise RuntimeError(
                "Data was not saved"
            )

        if result.get("samples_received") != 128:
            raise RuntimeError(
                "Incorrect sample count"
            )

        print("\nUPLOAD SUCCESS!")
        print("128 samples stored on AutoDL")

        display(
            "CP3 SUCCESS",
            "128 Saved",
            "AutoDL Cloud"
        )

        return result

    except Exception as e:

        print("\nUPLOAD ERROR:")
        print(type(e).__name__, e)

        display(
            "Upload Failed",
            str(e)[:16]
        )

        raise

    finally:

        if response is not None:
            response.close()

        gc.collect()

def main():

    print("=" * 55)
    print("EECS E4764 - Lab 6")
    print("Checkpoint 3")
    print("ESP32 -> Columbia WiFi -> AutoDL")
    print("=" * 55)

    wlan = connect_wifi()

    print("\nReady for HAR collection")

    display(
        "Checkpoint 3",
        "Ready",
        "Press ENTER"
    )

    while True:

        try:

            input(
                "\nPress ENTER to collect and upload..."
            )

            if not wlan.isconnected():
                wlan = connect_wifi()

            gc.collect()


            samples = collect_samples()


            result = upload_to_cloud(samples)


            print("\nCloud storage confirmed")
            print(result)

            del samples
            gc.collect()

            print("\nReady for next sample")

        except KeyboardInterrupt:

            print("Program stopped")
            break

        except Exception as e:

            print("\nCheckpoint 3 Error:")
            print(type(e).__name__, e)

            display(
                "CP3 Error",
                str(e)[:16]
            )


if __name__ == "__main__":
    main()
