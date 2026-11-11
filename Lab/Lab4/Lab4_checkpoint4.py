from machine import Pin, I2C, RTC, ADC, PWM, SPI
import ssd1306
import framebuf
import time
import network
import urequests
import gc

SDA_PIN = 22
SCL_PIN = 20

BUTTON1_PIN = 32
BUTTON2_PIN = 33
BUTTON3_PIN = 27

LIGHT_SENSOR_PIN = 26

PIEZO_PIN = 12

SPI_SCK_PIN = 5
SPI_MOSI_PIN = 19
SPI_MISO_PIN = 21
SPI_CS_PIN = 15

WIFI_SSID = "Columbia University"
NTFY_TOPIC = "columbia-aiot-lab4-change-this-82641"

OLED_WIDTH = 128
OLED_HEIGHT = 32

i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=400000)
oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)

rtc = RTC()
rtc.datetime((2026, 10, 8, 3, 12, 0, 0, 0))

button1 = Pin(BUTTON1_PIN, Pin.IN, Pin.PULL_UP)
button2 = Pin(BUTTON2_PIN, Pin.IN, Pin.PULL_UP)
button3 = Pin(BUTTON3_PIN, Pin.IN, Pin.PULL_UP)

light_sensor = ADC(Pin(LIGHT_SENSOR_PIN))
light_sensor.atten(ADC.ATTN_11DB)

piezo = PWM(Pin(PIEZO_PIN))
piezo.freq(1000)
piezo.duty(0)

spi = SPI(
    1,
    baudrate=5000000,
    polarity=1,
    phase=1,
    sck=Pin(SPI_SCK_PIN),
    mosi=Pin(SPI_MOSI_PIN),
    miso=Pin(SPI_MISO_PIN),
)
cs = Pin(SPI_CS_PIN, Pin.OUT)
cs.value(1)

SPI_READ = 0x80
SPI_MULTI_BYTE = 0x40

DEVID = 0x00

BW_RATE = 0x2C
POWER_CTL = 0x2D
INT_ENABLE = 0x2E
DATA_FORMAT = 0x31

DATAX0 = 0x32
FIFO_CTL = 0x38


def adxl_write_register(register, value):
    cs.value(0)
    spi.write(bytes([register & 0x3F, value]))
    cs.value(1)


def adxl_read_register(register):
    cs.value(0)
    command = register | SPI_READ
    spi.write(bytes([command]))
    data = bytearray(1)
    spi.readinto(data)
    cs.value(1)
    return data[0]


def initialize_adxl345():
    device_id = adxl_read_register(DEVID)
    print("ADXL345 Device ID:", hex(device_id))
    if device_id == 0xE5:
        print("ADXL345 detected successfully!")
    else:
        print("WARNING: ADXL345 not detected.")
    adxl_write_register(DATA_FORMAT, 0x08)
    adxl_write_register(BW_RATE, 0x0A)
    adxl_write_register(INT_ENABLE, 0x00)
    adxl_write_register(FIFO_CTL, 0x00)
    adxl_write_register(POWER_CTL, 0x08)
    print("ADXL345 initialized.")


def convert_signed(low_byte, high_byte):
    value = high_byte << 8 | low_byte
    if value > 32767:
        value -= 65536
    return value


def read_acceleration():
    command = DATAX0 | SPI_READ | SPI_MULTI_BYTE
    cs.value(0)
    spi.write(bytes([command]))
    data = bytearray(6)
    spi.readinto(data)
    cs.value(1)
    x = convert_signed(data[0], data[1])
    y = convert_signed(data[2], data[3])
    z = convert_signed(data[4], data[5])
    return (x, y, z)


def connect_wifi():
    print()
    print("============================")
    print("CHECKPOINT 2 - WIFI")
    print("============================")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)
    if wlan.isconnected():
        print("WiFi already connected!")
        print("IP:", wlan.ifconfig()[0])
        return wlan
    print("Connecting to:", WIFI_SSID)
    wlan.connect(WIFI_SSID)
    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        print("Connecting...", "status:", wlan.status())
        time.sleep(1)
        timeout -= 1
    if wlan.isconnected():
        print("WiFi connected!")
        print("Network configuration:")
        print(wlan.ifconfig())
    else:
        print("ERROR: WiFi connection failed.")
    return wlan


latitude = None
longitude = None


def get_location():
    global latitude
    global longitude
    print()
    print("============================")
    print("GETTING GEOLOCATION")
    print("============================")
    response = None
    try:
        response = urequests.get("http://ip-api.com/json/")
        data = response.json()
        print("API response:", data)
        if data.get("status") == "success":
            latitude = data.get("lat")
            longitude = data.get("lon")
            print("Latitude:", latitude)
            print("Longitude:", longitude)
            return True
        else:
            print("Geolocation API returned failure.")
            return False
    except Exception as e:
        print("Geolocation error:", e)
        return False
    finally:
        if response is not None:
            response.close()


def display_location():
    oled.fill(0)
    oled.text("LOCATION", 32, 0, 1)
    if latitude is not None and longitude is not None:
        lat_string = "Lat:{:.4f}".format(latitude)
        lon_string = "Lon:{:.4f}".format(longitude)
        oled.text(lat_string, 0, 12, 1)
        oled.text(lon_string, 0, 22, 1)
    else:
        oled.text("Location failed", 0, 16, 1)
    oled.show()


temperature = None
weather_description = None


def weather_code_to_text(code):
    if code == 0:
        return "Clear"
    elif code in (1, 2):
        return "Partly cloudy"
    elif code == 3:
        return "Overcast"
    elif code in (45, 48):
        return "Fog"
    elif code in (51, 53, 55, 56, 57):
        return "Drizzle"
    elif code in (61, 63, 65, 66, 67):
        return "Rain"
    elif code in (71, 73, 75, 77):
        return "Snow"
    elif code in (80, 81, 82):
        return "Rain showers"
    elif code in (85, 86):
        return "Snow showers"
    elif code in (95, 96, 99):
        return "Thunderstorm"
    else:
        return "Unknown"


def get_weather():
    global temperature
    global weather_description
    if latitude is None or longitude is None:
        print("Weather error: no coordinates")
        return False
    print()
    print("============================")
    print("GETTING WEATHER")
    print("============================")
    response = None
    try:
        url = (
            "http://api.open-meteo.com/v1/forecast"
            "?latitude={}&longitude={}"
            "&current=temperature_2m,weather_code"
            "&temperature_unit=fahrenheit"
        ).format(latitude, longitude)
        print("Weather URL:", url)
        gc.collect()
        print("Memory before weather:", gc.mem_free())
        response = urequests.get(url)
        data = response.json()
        print("Weather API response:", data)
        current = data.get("current")
        if current is None:
            print("Weather API returned no current data.")
            return False
        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code")
        if temperature is None or weather_code is None:
            print("Weather API missing temperature/weather code.")
            return False
        weather_description = weather_code_to_text(weather_code)
        print("Temperature:", temperature, "F")
        print("Weather:", weather_description)
        return True
    except Exception as e:
        print("Weather error:", repr(e))
        return False
    finally:
        if response is not None:
            response.close()


def display_weather():
    oled.fill(0)
    oled.text("WEATHER", 36, 0, 1)
    if temperature is not None and weather_description is not None:
        oled.text("Temp:{:.1f} F".format(temperature), 0, 11, 1)
        oled.text(weather_description[:16], 0, 22, 1)
    else:
        oled.text("Weather failed", 0, 16, 1)
    oled.show()


def send_notification():
    if not NTFY_TOPIC or NTFY_TOPIC == "columbia-aiot-lab4-change-this-82641":
        print("TIP: Change NTFY_TOPIC to a unique private-looking value.")
    if latitude is None or longitude is None:
        message = "Columbia AIoT Lab4: ESP32 online; location unavailable."
    else:
        message = "ESP32 location: {:.4f}, {:.4f}".format(latitude, longitude)
    if temperature is not None and weather_description is not None:
        message += " | Weather: {:.1f} F, {}".format(temperature, weather_description)
    else:
        message += " | Weather unavailable"
    print("Sending ntfy notification:", message)
    gc.collect()
    response = None
    try:
        gc.collect()
        print("Memory before ntfy:", gc.mem_free())
        response = urequests.post(
            "http://ntfy.sh/" + NTFY_TOPIC,
            data=message.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        status = response.status_code
        print("ntfy HTTP status:", status)
        return 200 <= status < 300
    except Exception as e:
        print("ntfy error:", repr(e))
        return False
    finally:
        if response is not None:
            response.close()
        gc.collect()


def display_wifi_error():
    oled.fill(0)
    oled.text("CHECKPOINT 2", 16, 4, 1)
    oled.text("WIFI FAILED", 20, 18, 1)
    oled.show()


DEBOUNCE_TIME = 200

last_button1 = button1.value()
last_button2 = button2.value()
last_button3 = button3.value()

last_press1 = 0
last_press2 = 0
last_press3 = 0

alarm_hour = 12
alarm_minute = 1
setting_alarm = False
alarm_enabled = True
alarm_ringing = False
alarm_triggered_this_minute = False

ADC_MIN = 0
ADC_MAX = 4095
MIN_CONTRAST = 10
MAX_CONTRAST = 255
filtered_light = 0
LIGHT_UPDATE_INTERVAL = 200
last_light_update = time.ticks_ms()

TILT_THRESHOLD = 80
scroll_x = 0
scroll_y = 0
SCROLL_SPEED = 2

ACCEL_UPDATE_INTERVAL = 100
last_accel_update = time.ticks_ms()

accel_x = 0
accel_y = 0
accel_z = 0


def draw_big_text(text_string, x, y, scale=2):
    char_width = 8
    char_height = 8
    width = len(text_string) * char_width
    height = char_height
    buffer = bytearray((width * height) // 8)
    fb = framebuf.FrameBuffer(buffer, width, height, framebuf.MONO_HLSB)
    fb.fill(0)
    fb.text(text_string, 0, 0, 1)
    for py in range(height):
        for px in range(width):
            if fb.pixel(px, py):
                for dy in range(scale):
                    for dx in range(scale):
                        new_x = x + px * scale + dx
                        new_y = y + py * scale + dy
                        if 0 <= new_x < OLED_WIDTH and 0 <= new_y < OLED_HEIGHT:
                            oled.pixel(new_x, new_y, 1)


def draw_clock_content(offset_x, offset_y):
    dt = rtc.datetime()
    hour = dt[4]
    minute = dt[5]
    second = dt[6]
    clock_string = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
    oled.text("DIGITAL CLOCK", 12 + offset_x, 0 + offset_y, 1)
    draw_big_text(clock_string, 0 + offset_x, 13 + offset_y, 2)


def display_clock():
    oled.fill(0)
    draw_clock_content(scroll_x, scroll_y)
    draw_clock_content(scroll_x - OLED_WIDTH, scroll_y)
    draw_clock_content(scroll_x + OLED_WIDTH, scroll_y)
    draw_clock_content(scroll_x, scroll_y - OLED_HEIGHT)
    draw_clock_content(scroll_x, scroll_y + OLED_HEIGHT)
    draw_clock_content(scroll_x - OLED_WIDTH, scroll_y - OLED_HEIGHT)
    draw_clock_content(scroll_x + OLED_WIDTH, scroll_y - OLED_HEIGHT)
    draw_clock_content(scroll_x - OLED_WIDTH, scroll_y + OLED_HEIGHT)
    draw_clock_content(scroll_x + OLED_WIDTH, scroll_y + OLED_HEIGHT)
    oled.show()


def update_scroll(x, y, z):
    global scroll_x
    global scroll_y
    direction = "CENTER"
    if abs(x) > abs(y) and abs(x) > TILT_THRESHOLD:
        if x > 0:
            scroll_x += SCROLL_SPEED
            direction = "RIGHT"
        else:
            scroll_x -= SCROLL_SPEED
            direction = "LEFT"
    elif abs(y) > TILT_THRESHOLD:
        if y > 0:
            scroll_y += SCROLL_SPEED
            direction = "DOWN"
        else:
            scroll_y -= SCROLL_SPEED
            direction = "UP"
    if scroll_x >= OLED_WIDTH:
        scroll_x -= OLED_WIDTH
    elif scroll_x <= -OLED_WIDTH:
        scroll_x += OLED_WIDTH
    if scroll_y >= OLED_HEIGHT:
        scroll_y -= OLED_HEIGHT
    elif scroll_y <= -OLED_HEIGHT:
        scroll_y += OLED_HEIGHT
    return direction


def add_hour():
    dt = list(rtc.datetime())
    dt[4] = (dt[4] + 1) % 24
    rtc.datetime(tuple(dt))


def add_minute():
    dt = list(rtc.datetime())
    dt[5] += 1
    if dt[5] >= 60:
        dt[5] = 0
        dt[4] = (dt[4] + 1) % 24
    rtc.datetime(tuple(dt))


def add_alarm_hour():
    global alarm_hour
    alarm_hour = (alarm_hour + 1) % 24


def add_alarm_minute():
    global alarm_minute
    global alarm_hour
    alarm_minute += 1
    if alarm_minute >= 60:
        alarm_minute = 0
        alarm_hour = (alarm_hour + 1) % 24


def read_light_sensor():
    return light_sensor.read()


def light_to_contrast(light_value):
    if light_value < ADC_MIN:
        light_value = ADC_MIN
    if light_value > ADC_MAX:
        light_value = ADC_MAX
    contrast = MIN_CONTRAST + (
        (light_value - ADC_MIN) * (MAX_CONTRAST - MIN_CONTRAST) // (ADC_MAX - ADC_MIN)
    )
    if contrast < MIN_CONTRAST:
        contrast = MIN_CONTRAST
    if contrast > MAX_CONTRAST:
        contrast = MAX_CONTRAST
    return contrast


def update_brightness():
    global filtered_light
    raw_light = read_light_sensor()
    if filtered_light == 0:
        filtered_light = raw_light
    else:
        filtered_light = (filtered_light * 3 + raw_light) // 4
    contrast_value = light_to_contrast(filtered_light)
    oled.contrast(contrast_value)


def display_alarm_setting():
    alarm_string = "{:02d}:{:02d}".format(alarm_hour, alarm_minute)
    oled.fill(0)
    oled.text("SET ALARM", 28, 0, 1)
    draw_big_text(alarm_string, 24, 13, 2)
    oled.show()


def display_alarm_ringing():
    oled.fill(0)
    oled.text("*** ALARM ***", 16, 2, 1)
    oled.text("PRESS ANY BUTTON", 0, 18, 1)
    oled.show()


def start_alarm():
    global alarm_ringing
    alarm_ringing = True
    piezo.freq(1000)
    piezo.duty(512)
    print("ALARM ON!")


def stop_alarm():
    global alarm_ringing
    alarm_ringing = False
    piezo.duty(0)
    print("ALARM OFF!")


def check_alarm():
    global alarm_triggered_this_minute
    dt = rtc.datetime()
    current_hour = dt[4]
    current_minute = dt[5]
    if alarm_enabled and current_hour == alarm_hour and current_minute == alarm_minute:
        if not alarm_triggered_this_minute:
            start_alarm()
            alarm_triggered_this_minute = True
    else:
        alarm_triggered_this_minute = False


oled.fill(0)
oled.text("LAB4 CHECKPOINT3", 0, 4, 1)
oled.text("Starting...", 24, 18, 1)
oled.show()
time.sleep(1)

initialize_adxl345()

filtered_light = read_light_sensor()
initial_contrast = light_to_contrast(filtered_light)
oled.contrast(initial_contrast)

oled.fill(0)
oled.text("CONNECTING WIFI", 0, 10, 1)
oled.show()
wlan = connect_wifi()

if wlan.isconnected():
    oled.fill(0)
    oled.text("WIFI CONNECTED", 4, 5, 1)
    oled.text("Getting location", 0, 18, 1)
    oled.show()
    time.sleep(1)
    location_success = get_location()
    if location_success:
        display_location()
        print()
        print("CHECKPOINT 2 SUCCESS!")
        print("Coordinates displayed on OLED.")
        oled.fill(0)
        oled.text("GETTING WEATHER", 4, 10, 1)
        oled.show()
        weather_success = get_weather()
        if weather_success:
            display_weather()
            print()
            print("CHECKPOINT 3 SUCCESS!")
            print("Weather displayed on OLED.")
            time.sleep(2)
        else:
            display_weather()
            time.sleep(3)
    else:
        display_location()
        time.sleep(5)
else:
    display_wifi_error()
    time.sleep(5)

if wlan.isconnected():
    oled.fill(0)
    oled.text("SENDING NTFY", 12, 10, 1)
    oled.show()
    notification_ok = send_notification()
    oled.fill(0)
    oled.text("CHECKPOINT 4", 12, 2, 1)
    oled.text("NOTIFY SENT" if notification_ok else "NOTIFY FAILED", 8, 18, 1)
    oled.show()
    time.sleep(3)


while True:
    now = time.ticks_ms()

    if time.ticks_diff(now, last_accel_update) >= ACCEL_UPDATE_INTERVAL:
        accel_x, accel_y, accel_z = read_acceleration()
        direction = update_scroll(accel_x, accel_y, accel_z)
        print("X:", accel_x, "Y:", accel_y, "Z:", accel_z, "Direction:", direction)
        last_accel_update = now

    current_button1 = button1.value()
    current_button2 = button2.value()
    current_button3 = button3.value()

    if current_button1 == 0 and last_button1 == 1:
        if time.ticks_diff(now, last_press1) > DEBOUNCE_TIME:
            if alarm_ringing:
                stop_alarm()
            elif setting_alarm:
                add_alarm_hour()
            else:
                add_hour()
            last_press1 = now

    if current_button2 == 0 and last_button2 == 1:
        if time.ticks_diff(now, last_press2) > DEBOUNCE_TIME:
            if alarm_ringing:
                stop_alarm()
            elif setting_alarm:
                add_alarm_minute()
            else:
                add_minute()
            last_press2 = now

    if current_button3 == 0 and last_button3 == 1:
        if time.ticks_diff(now, last_press3) > DEBOUNCE_TIME:
            if alarm_ringing:
                stop_alarm()
            else:
                setting_alarm = not setting_alarm
                if setting_alarm:
                    print("ENTER ALARM SETTING")
                else:
                    print(
                        "ALARM SET:", "{:02d}:{:02d}".format(alarm_hour, alarm_minute)
                    )
            last_press3 = now

    last_button1 = current_button1
    last_button2 = current_button2
    last_button3 = current_button3

    if time.ticks_diff(now, last_light_update) >= LIGHT_UPDATE_INTERVAL:
        update_brightness()
        last_light_update = now

    if not setting_alarm:
        check_alarm()

    if alarm_ringing:
        display_alarm_ringing()
    elif setting_alarm:
        display_alarm_setting()
    elif temperature is not None and weather_description is not None:
        display_weather()
    elif latitude is not None and longitude is not None:
        display_location()
    else:
        display_clock()

    time.sleep_ms(30)
