# Lab 5 - Checkpoint 2 (ESP32 / MicroPython)
import network
import socket
import json
import time
from machine import Pin, I2C, PWM, RTC
import ssd1306

SSID = "Columbia University"
PASSWORD = ""
UTC_OFFSET = -4  

SDA_PIN = 22
SCL_PIN = 20
PIEZO_PIN = 12
BUTTON1_PIN = 32
BUTTON2_PIN = 33
BUTTON3_PIN = 27
LIGHT_SENSOR_PIN = 26
SPI_SCK_PIN = 5
SPI_MOSI_PIN = 19
SPI_MISO_PIN = 21
SPI_CS_PIN = 15

# ----- Initialize OLED and piezo -----
i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
piezo = PWM(Pin(PIEZO_PIN))
piezo.freq(1000)
piezo.duty(0)  # Same MicroPython PWM API as Lab 4
rtc = RTC()
screen_enabled = True
screen_mode = 'message'
alarm_target = None  # local timestamp, one-shot
alarm_last_day = None
lat = None
lon = None


def show_lines(lines):
    if not screen_enabled:
        return
    oled.fill(0)
    for i, line in enumerate(lines[:4]):
        oled.text(str(line)[:16], 0, i * 8, 1)
    oled.show()


def screen_on():
    global screen_enabled
    screen_enabled = True
    oled.poweron()
    show_lines(['Screen ON'])
    return 'Screen ON'


def screen_off():
    global screen_enabled
    oled.fill(0)
    oled.show()
    oled.poweroff()
    screen_enabled = False
    return 'Screen OFF'


def local_now():
    return time.localtime(time.time() + UTC_OFFSET * 3600)


def current_clock_string():
    t = local_now()
    return '%02d:%02d:%02d' % (t[3], t[4], t[5])


def display_time():
    global screen_mode
    screen_mode = 'clock'
    show_lines(['DIGITAL CLOCK', current_clock_string()])
    return 'Clock displayed'


def display_text(message):
    global screen_mode
    screen_mode = 'message'
    # ASCII fits the built-in OLED font; split at newlines and 16 columns.
    lines = []
    for paragraph in str(message).split('\n'):
        if paragraph == '':
            lines.append('')
        while paragraph:
            lines.append(paragraph[:16])
            paragraph = paragraph[16:]
    show_lines(lines[:4])
    return 'Text displayed'


def set_alarm(hour, minute, second):
    global alarm_target
    h, m, s = int(hour), int(minute), int(second)
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError('Invalid alarm time')
    # Using epoch seconds, schedule next occurrence of the specified local wall time.
    t = local_now()
    now_sec = t[3] * 3600 + t[4] * 60 + t[5]
    target_sec = h * 3600 + m * 60 + s
    delay = (target_sec - now_sec) % 86400
    if delay == 0:
        delay = 86400
    alarm_target = time.time() + delay
    return 'Alarm set %02d:%02d:%02d' % (h, m, s)


def check_alarm():
    global alarm_target, screen_mode
    if alarm_target is not None and time.time() >= alarm_target:
        alarm_target = None
        screen_mode = 'message'
        show_lines(['*** ALARM ***'])
        piezo.freq(1000)
        piezo.duty(512)
        time.sleep_ms(1000)
        piezo.duty(0)
        print('ALARM triggered')


def get_location():
    global lat, lon
    if lat is None or lon is None:
        import urequests
        r = urequests.get('http://ip-api.com/json/')
        try:
            result = r.json()
        finally:
            r.close()
        if result.get('status') != 'success':
            raise ValueError('Location lookup failed')
        lat, lon = result['lat'], result['lon']
    return lat, lon


def display_location():
    a, b = get_location()
    display_text('LAT: %.4f\nLON: %.4f' % (a, b))
    return 'Location displayed (approximate IP location)'


def display_weather():
    import urequests
    a, b = get_location()
    url = ('https://api.open-meteo.com/v1/forecast'
           '?latitude=%s&longitude=%s'
           '&current=temperature_2m,weather_code') % (a, b)
    r = urequests.get(url)
    try:
        d = r.json()['current']
    finally:
        r.close()
    display_text('WEATHER\nTemp: %s C\nCode: %s' %
                 (d['temperature_2m'], d['weather_code']))
    return 'Weather displayed'


def execute(command):
    if not isinstance(command, dict):
        raise ValueError('JSON must be an object')
    name = command.get('name')
    args = command.get('args', [])
    if not isinstance(args, list):
        raise ValueError('args must be a list')
    functions = {
        'screen_on': (screen_on, 0),
        'screen_off': (screen_off, 0),
        'display_time': (display_time, 0),
        'display_text': (display_text, 1),
        'display_message': (display_text, 1),
        'set_alarm': (set_alarm, 3),
        'display_location': (display_location, 0),
        'display_weather': (display_weather, 0),
    }
    if name not in functions:
        raise ValueError('Unknown command: %s' % name)
    fn, required_args = functions[name]
    if len(args) != required_args:
        raise ValueError('%s requires %d arguments' % (name, required_args))
    return fn(*args)


# ----- Connect Wi-Fi -----
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)
print('Connecting Wi-Fi...')
for i in range(30):
    if wlan.isconnected():
        break
    time.sleep(1)
if not wlan.isconnected():
    raise RuntimeError('Wi-Fi failed. Check SSID/password/network.')
print('ESP32 IP:', wlan.ifconfig()[0])

try:
    import ntptime
    ntptime.settime()
    print('Clock synchronized by NTP')
except Exception as e:
    print('NTP warning:', e)

show_lines(['Lab 5 CP2', 'Server ready', wlan.ifconfig()[0]])

# ----- HTTP Server (LAN only; no authentication) -----
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 8080))
server.listen(1)
server.settimeout(0.25)
print('Listening on port 8080')

last_second = -1
while True:
    check_alarm()
    if screen_mode == 'clock' and screen_enabled:
        t = local_now()
        if t[5] != last_second:
            show_lines(['DIGITAL CLOCK', current_clock_string()])
            last_second = t[5]

    try:
        client, addr = server.accept()
    except OSError:
        continue

    try:
        client.settimeout(4)
        incoming = b''
        while b'\r\n\r\n' not in incoming:
            part = client.recv(512)
            if not part:
                raise ValueError('Missing headers')
            incoming += part
            if len(incoming) > 4096:
                raise ValueError('Request header too long')
        header, _, body = incoming.partition(b'\r\n\r\n')
        lines = header.decode().split('\r\n')
        if not lines[0].startswith('POST '):
            raise ValueError('POST required')
        content_length = None
        for line in lines[1:]:
            if line.lower().startswith('content-length:'):
                content_length = int(line.split(':', 1)[1].strip())
        if content_length is None or content_length < 1 or content_length > 2048:
            raise ValueError('Invalid Content-Length')
        while len(body) < content_length:
            part = client.recv(min(512, content_length - len(body)))
            if not part:
                raise ValueError('Incomplete request body')
            body += part
        command = json.loads(body[:content_length].decode())
        response = {'status': 'ok', 'result': execute(command)}
        print('Received:', command.get('name'))
    except Exception as e:
        response = {'status': 'error', 'message': str(e)}
        print('Request error:', e)

    try:
        payload = json.dumps(response).encode()
        client.sendall(b'HTTP/1.1 200 OK\r\n'
                       b'Content-Type: application/json\r\n'
                       b'Connection: close\r\n'
                       b'Content-Length: ' + str(len(payload)).encode() +
                       b'\r\n\r\n' + payload)
    except Exception as e:
        print('Send error:', e)
    finally:
        client.close()
