"""Lab 5 Checkpoint 4 - ESP32 MicroPython HTTP JSON command server.
Upload as Lab5_checkpoint4_server.py and execute once from REPL.
Do NOT start a second copy while the first is listening on port 8080.
"""
import network
import socket
import json
import time
from machine import Pin, I2C, PWM, RTC
import ssd1306

SSID = "Columbia University"
PASSWORD = ""
UTC_OFFSET = -4  # New York currently EDT (-4); change to -5 in EST.
PORT = 8080

SDA_PIN = 22
SCL_PIN = 20
PIEZO_PIN = 12

i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
piezo = PWM(Pin(PIEZO_PIN))
piezo.freq(1000)
piezo.duty(0)
rtc = RTC()
screen_enabled = True
screen_mode = "message"
alarm_target = None
lat = None
lon = None


def show_lines(lines):
    if not screen_enabled:
        return
    oled.fill(0)
    for idx, line in enumerate(lines[:4]):
        oled.text(str(line)[:16], 0, idx * 8, 1)
    oled.show()


def screen_on():
    global screen_enabled
    screen_enabled = True
    oled.poweron()
    show_lines(["Screen ON"])
    return "Screen ON"


def screen_off():
    global screen_enabled
    oled.fill(0)
    oled.show()
    oled.poweroff()
    screen_enabled = False
    return "Screen OFF"


def local_now():
    return time.localtime(time.time() + UTC_OFFSET * 3600)


def clock_string():
    t = local_now()
    return "%02d:%02d:%02d" % (t[3], t[4], t[5])


def display_time():
    global screen_mode
    screen_on_if_needed()
    screen_mode = "clock"
    show_lines(["DIGITAL CLOCK", clock_string()])
    return "Clock displayed"


def screen_on_if_needed():
    global screen_enabled
    if not screen_enabled:
        oled.poweron()
        screen_enabled = True


def display_text(message):
    global screen_mode
    screen_on_if_needed()
    screen_mode = "message"
    # SSD1306 128x32 built-in font = 16 chars per line x 4 rows.
    message = str(message)
    lines = []
    for paragraph in message.split("\n"):
        if not paragraph:
            lines.append("")
        else:
            while paragraph:
                lines.append(paragraph[:16])
                paragraph = paragraph[16:]
    show_lines(lines[:4])
    return "Text displayed"


def set_alarm(hour, minute, second):
    global alarm_target
    h, m, s = int(hour), int(minute), int(second)
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError("Invalid alarm time")
    t = local_now()
    now_sec = t[3] * 3600 + t[4] * 60 + t[5]
    target_sec = h * 3600 + m * 60 + s
    delay = (target_sec - now_sec) % 86400
    if delay == 0:
        delay = 86400
    alarm_target = time.time() + delay
    display_text("Alarm %02d:%02d:%02d" % (h, m, s))
    return "Alarm set %02d:%02d:%02d" % (h, m, s)


def check_alarm():
    global alarm_target, screen_mode
    if alarm_target is not None and time.time() >= alarm_target:
        alarm_target = None
        screen_on_if_needed()
        screen_mode = "message"
        show_lines(["*** ALARM ***"])
        piezo.freq(1000)
        piezo.duty(512)
        time.sleep_ms(800)
        piezo.duty(0)
        print("Alarm triggered")


def get_location():
    global lat, lon
    if lat is None or lon is None:
        import urequests
        response = urequests.get("http://ip-api.com/json/")
        try:
            data = response.json()
        finally:
            response.close()
        if data.get("status") != "success":
            raise ValueError("IP location lookup failed")
        lat, lon = data["lat"], data["lon"]
    return lat, lon


def display_location():
    a, b = get_location()
    display_text("LAT: %.4f\nLON: %.4f" % (a, b))
    return "Approximate IP location displayed"


def display_weather():
    import urequests
    a, b = get_location()
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=%s&longitude=%s"
           "&current=temperature_2m,weather_code") % (a, b)
    response = urequests.get(url)
    try:
        current = response.json()["current"]
    finally:
        response.close()
    display_text("WEATHER\nTemp: %s C\nCode: %s" %
                 (current["temperature_2m"], current["weather_code"]))
    return "Weather displayed"


COMMANDS = {
    "screen_on": (screen_on, 0),
    "screen_off": (screen_off, 0),
    "display_time": (display_time, 0),
    "display_text": (display_text, 1),
    "set_alarm": (set_alarm, 3),
    "display_location": (display_location, 0),
    "display_weather": (display_weather, 0),
}


def execute(command):
    if not isinstance(command, dict):
        raise ValueError("JSON command must be an object")
    name = command.get("name")
    args = command.get("args")
    if name not in COMMANDS:
        raise ValueError("Unknown function: %s" % name)
    if not isinstance(args, list):
        raise ValueError("args must be a list")
    fn, count = COMMANDS[name]
    if len(args) != count:
        raise ValueError("Wrong number of args for %s" % name)
    if name == "set_alarm":
        if any(type(a) is not int for a in args):
            raise ValueError("Alarm args must be integers")
    if name == "display_text" and not isinstance(args[0], str):
        raise ValueError("display_text expects a string")
    return fn(*args)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        for _ in range(30):
            if wlan.isconnected():
                break
            time.sleep(1)
    if not wlan.isconnected():
        raise RuntimeError("Wi-Fi connection failed")
    print("ESP32 IP:", wlan.ifconfig()[0])
    try:
        import ntptime
        ntptime.settime()
        print("NTP time synchronized")
    except Exception as exc:
        print("NTP warning:", exc)
    return wlan


def read_http_command(client):
    """Read exactly one HTTP POST request, including its Content-Length body."""
    client.settimeout(5)
    raw = b""
    while b"\r\n\r\n" not in raw:
        part = client.recv(512)
        if not part:
            raise ValueError("Connection closed before HTTP headers")
        raw += part
        if len(raw) > 4096:
            raise ValueError("HTTP headers too large")
    headers, _delimiter, body = raw.partition(b"\r\n\r\n")
    lines = headers.decode("utf-8").split("\r\n")
    if not lines[0].startswith("POST "):
        raise ValueError("HTTP POST required")
    content_length = None
    for line in lines[1:]:
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break
    if content_length is None or not (1 <= content_length <= 2048):
        raise ValueError("Invalid Content-Length")
    while len(body) < content_length:
        part = client.recv(min(512, content_length - len(body)))
        if not part:
            raise ValueError("Connection closed during request body")
        body += part
    return json.loads(body[:content_length].decode("utf-8"))


def send_http_json(client, response):
    payload = json.dumps(response).encode("utf-8")
    header = (b"HTTP/1.1 200 OK\r\n"
              b"Content-Type: application/json\r\n"
              b"Connection: close\r\n"
              b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n")
    # sendall may not exist in every MicroPython build; send small chunks.
    data = header + payload
    while data:
        sent = client.send(data)
        if not sent:
            raise OSError("HTTP response send failed")
        data = data[sent:]


def serve_forever():
    connect_wifi()
    show_lines(["Lab 5 CP4", "Server ready"])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", PORT))
        server.listen(2)
        server.settimeout(0.25)
        print("Listening on port", PORT)
        last_second = -1
        while True:
            check_alarm()
            if screen_mode == "clock" and screen_enabled:
                t = local_now()
                if t[5] != last_second:
                    show_lines(["DIGITAL CLOCK", clock_string()])
                    last_second = t[5]
            try:
                client, addr = server.accept()
            except OSError:
                continue  # normal accept timeout
            print("TCP connection from", addr)
            try:
                try:
                    command = read_http_command(client)
                    print("Received command:", command)
                    result = execute(command)
                    reply = {"status": "ok", "result": result}
                except Exception as exc:
                    print("Command error:", exc)
                    reply = {"status": "error", "message": str(exc)}
                send_http_json(client, reply)
                print("HTTP response sent:", reply)
            except Exception as exc:
                print("Connection/response error:", exc)
            finally:
                client.close()
    finally:
        server.close()
        piezo.duty(0)
        print("Server socket closed")


if __name__ == "__main__":
    serve_forever()
