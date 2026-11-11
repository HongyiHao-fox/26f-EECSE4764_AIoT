import network
import socket
import time
import json
import struct
import gc

from machine import Pin, SoftI2C
import ssd1306

WIFI_SSID = "Columbia University"

PORT = 8765

SCL_PIN = 20
SDA_PIN = 22

ADXL_ADDR = 0x53
OLED_ADDR = 0x3C

SAMPLE_RATE = 50
SAMPLE_COUNT = 128
INTERVAL_US = 20000


print("Initializing SoftI2C...")

i2c = SoftI2C(
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN),
    freq=100000
)

devices = i2c.scan()

print("I2C:", [hex(x) for x in devices])

if ADXL_ADDR not in devices:
    raise RuntimeError("ADXL345 not found")

if OLED_ADDR not in devices:
    raise RuntimeError("OLED not found")


oled = ssd1306.SSD1306_I2C(
    128,
    32,
    i2c,
    addr=OLED_ADDR
)

def display(a="", b="", c=""):
    oled.fill(0)
    oled.text(str(a)[:16], 0, 0)
    oled.text(str(b)[:16], 0, 11)
    oled.text(str(c)[:16], 0, 22)
    oled.show()


display("Lab 6", "Checkpoint 2")

def write_reg(reg, value):
    i2c.writeto_mem(
        ADXL_ADDR,
        reg,
        bytes([value])
    )
def initialize_adxl():
    devid = i2c.readfrom_mem(
        ADXL_ADDR, 0x00, 1
    )[0]

    print("ADXL345 ID:", hex(devid))

    if devid != 0xE5:
        raise RuntimeError("Invalid ADXL345")

    write_reg(0x2D, 0x00)
    write_reg(0x31, 0x08)
    write_reg(0x2C, 0x09)
    write_reg(0x2D, 0x08)

    time.sleep_ms(100)

def read_acceleration():
    data = i2c.readfrom_mem(
        ADXL_ADDR,
        0x32,
        6
    )

    x, y, z = struct.unpack("<hhh", data)

    scale = 0.00390625

    return [
        round(x * scale, 4),
        round(y * scale, 4),
        round(z * scale, 4)
    ]


initialize_adxl()

print("ADXL345 initialized")






def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Already connected:", wlan.ifconfig())
        return wlan

    display("Connecting WiFi", "Columbia Univ")

    print("Scanning Columbia WiFi...")

    try:
        networks = wlan.scan()

        found = False

        for net in networks:
            ssid = net[0].decode()
            channel = net[2]
            security = net[4]

            if ssid == WIFI_SSID:
                found = True
                print(
                    "Found:",
                    ssid,
                    "channel:",
                    channel,
                    "security:",
                    security
                )

        if not found:
            print(
                "Columbia University not found "
                "in ESP32 scan"
            )

    except Exception as e:
        print("Scan error:", e)

    print("Connecting:", WIFI_SSID)


    wlan.connect(WIFI_SSID)

    start = time.ticks_ms()

    while not wlan.isconnected():

        if time.ticks_diff(
            time.ticks_ms(), start
        ) > 20000:

            print("WiFi failed")
            print("Status:", wlan.status())

            display(
                "WiFi Failed",
                "Check 2.4GHz"
            )

            raise RuntimeError(
                "Cannot connect to Columbia University"
            )

        time.sleep_ms(500)

    print("WiFi connected")
    print("IP:", wlan.ifconfig()[0])
    print("Network:", wlan.ifconfig())

    display(
        "WiFi Connected",
        wlan.ifconfig()[0]
    )

    return wlan






def collect_samples():

    display(
        "HAR Recording",
        "128 samples",
        "50 Hz"
    )

    print("Collecting 128 samples...")

    samples = []

    start = time.ticks_us()

    for i in range(SAMPLE_COUNT):

        target = time.ticks_add(
            start,
            i * INTERVAL_US
        )

        while time.ticks_diff(
            target,
            time.ticks_us()
        ) > 0:
            time.sleep_us(100)

        samples.append(
            read_acceleration()
        )

    print("Collection completed")
    print("Samples:", len(samples))
    print("First:", samples[0])

    return samples






def send_json(conn, obj):
    data = json.dumps(obj) + "\n"
    conn.write(data.encode())


def receive_json(conn, limit=4096):
    data = bytearray()

    while True:
        ch = conn.recv(1)

        if not ch:
            raise OSError("Connection closed")

        if ch == b"\n":
            break

        data.extend(ch)

        if len(data) > limit:
            raise ValueError("Message too large")

    return json.loads(data.decode())






def show_prediction(activity):

    print("Prediction:", activity)

    if activity == "WALKING_UPSTAIRS":
        display(
            "HAR Prediction",
            "WALKING",
            "UPSTAIRS"
        )

    elif activity == "WALKING_DOWNSTAIRS":
        display(
            "HAR Prediction",
            "WALKING",
            "DOWNSTAIRS"
        )

    else:
        display(
            "HAR Prediction",
            activity
        )






def start_server():

    wlan = connect_wifi()

    server = socket.socket()

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind(("0.0.0.0", PORT))
    server.listen(1)

    server.settimeout(5)

    print("=" * 40)
    print("ESP32 HAR SERVER")
    print("IP:", wlan.ifconfig()[0])
    print("PORT:", PORT)
    print("=" * 40)

    display(
        "HAR Ready",
        wlan.ifconfig()[0],
        "Port 8765"
    )

    while True:

        conn = None

        try:
            gc.collect()

            if not wlan.isconnected():
                print("WiFi disconnected")
                connect_wifi()

            try:
                conn, addr = server.accept()
            except OSError:
                continue

            print("PC connected:", addr)

            conn.settimeout(120)

            command = receive_json(conn)

            if command.get("command") == "classify_HAR":

                samples = collect_samples()

                display(
                    "Sending Data",
                    "Please wait"
                )

                send_json(
                    conn,
                    {
                        "status": "ok",
                        "sample_rate": 50,
                        "samples": samples
                    }
                )

                del samples
                gc.collect()

                display(
                    "Gemini",
                    "Processing..."
                )

                print("Waiting for prediction...")

                result = receive_json(conn)

                activity = result.get(
                    "activity",
                    "UNKNOWN"
                )

                show_prediction(activity)

            else:
                send_json(
                    conn,
                    {
                        "status": "error",
                        "message": "Unknown command"
                    }
                )

        except Exception as e:
            print("Error:", e)
            display("Error", str(e)[:16])

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass






if __name__ == "__main__":
    start_server()
