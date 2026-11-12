from machine import Pin, I2C, RTC, ADC
import ssd1306
import framebuf
import time


SDA_PIN = 22
SCL_PIN = 20

BUTTON1_PIN = 32
BUTTON2_PIN = 33
BUTTON3_PIN = 27

LIGHT_SENSOR_PIN = 26

OLED_WIDTH = 128
OLED_HEIGHT = 32

i2c = I2C(
    0,
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN),
    freq=400000
)


oled = ssd1306.SSD1306_I2C(
    OLED_WIDTH,
    OLED_HEIGHT,
    i2c
)


rtc = RTC()

rtc.datetime(
    (2026, 10, 1, 3, 12, 0, 0, 0)
)

button1 = Pin(
    BUTTON1_PIN,
    Pin.IN,
    Pin.PULL_UP
)

button2 = Pin(
    BUTTON2_PIN,
    Pin.IN,
    Pin.PULL_UP
)

button3 = Pin(
    BUTTON3_PIN,
    Pin.IN,
    Pin.PULL_UP
)


light_sensor = ADC(
    Pin(LIGHT_SENSOR_PIN)
)

light_sensor.atten(
    ADC.ATTN_11DB
)


DEBOUNCE_TIME = 200

last_button1 = button1.value()
last_button2 = button2.value()
last_button3 = button3.value()

last_press1 = 0
last_press2 = 0
last_press3 = 0

MIN_CONTRAST = 10
MAX_CONTRAST = 255

ADC_MIN = 0
ADC_MAX = 4095

filtered_light = 0

def draw_big_text(text_string, x, y, scale=2):

    char_width = 8
    char_height = 8

    width = len(text_string) * char_width
    height = char_height

    buffer = bytearray(
        (width * height) // 8
    )

    fb = framebuf.FrameBuffer(
        buffer,
        width,
        height,
        framebuf.MONO_HLSB
    )

    fb.fill(0)

    fb.text(
        text_string,
        0,
        0,
        1
    )

    for py in range(height):

        for px in range(width):

            # Check whether this pixel is ON
            if fb.pixel(px, py):

                # Enlarge the pixel
                for dy in range(scale):

                    for dx in range(scale):

                        new_x = (
                            x
                            + px * scale
                            + dx
                        )

                        new_y = (
                            y
                            + py * scale
                            + dy
                        )

                        # Make sure we stay inside OLED
                        if (
                            0 <= new_x < OLED_WIDTH
                            and
                            0 <= new_y < OLED_HEIGHT
                        ):

                            oled.pixel(
                                new_x,
                                new_y,
                                1
                            )


# ============================================================
# 11. ADD ONE HOUR
# ============================================================

def add_hour():

    # Read RTC
    dt = list(rtc.datetime())

    # dt[4] = hour
    dt[4] = (dt[4] + 1) % 24

    # Write back to RTC
    rtc.datetime(tuple(dt))


# ============================================================
# 12. ADD ONE MINUTE
# ============================================================

def add_minute():

    # Read RTC
    dt = list(rtc.datetime())

    # Add one minute
    dt[5] = dt[5] + 1

    # If minute reaches 60
    if dt[5] >= 60:

        # Reset minute
        dt[5] = 0

        # Increase hour
        dt[4] = (dt[4] + 1) % 24

    # Write back to RTC
    rtc.datetime(tuple(dt))

def reset_second():

    # Read RTC
    dt = list(rtc.datetime())

    # dt[6] = second
    dt[6] = 0

    # Write back to RTC
    rtc.datetime(tuple(dt))

def read_light_sensor():

    # Read analog value from light sensor
    value = light_sensor.read()

    return value

def light_to_contrast(light_value):

    # Keep ADC value inside valid range
    if light_value < ADC_MIN:
        light_value = ADC_MIN

    if light_value > ADC_MAX:
        light_value = ADC_MAX

    # Linear mapping
    contrast = (
        MIN_CONTRAST
        +
        (
            (light_value - ADC_MIN)
            * (MAX_CONTRAST - MIN_CONTRAST)
            // (ADC_MAX - ADC_MIN)
        )
    )

    # Safety limits
    if contrast < MIN_CONTRAST:
        contrast = MIN_CONTRAST

    if contrast > MAX_CONTRAST:
        contrast = MAX_CONTRAST

    return contrast

def update_brightness():

    global filtered_light

    # Read current sensor value
    raw_light = read_light_sensor()

    if filtered_light == 0:

        filtered_light = raw_light

    else:

        filtered_light = (
            filtered_light * 3
            + raw_light
        ) // 4


    # Convert light level into OLED contrast
    contrast_value = light_to_contrast(
        filtered_light
    )


    # Set OLED brightness / contrast
    oled.contrast(
        contrast_value
    )

    print(
        "Light:",
        raw_light,
        "Filtered:",
        filtered_light,
        "Contrast:",
        contrast_value
    )


    return raw_light, contrast_value

def display_clock():

    # Read RTC
    dt = rtc.datetime()

    hour = dt[4]
    minute = dt[5]
    second = dt[6]


    clock_string = "{:02d}:{:02d}:{:02d}".format(
        hour,
        minute,
        second
    )

    oled.fill(0)

    oled.text(
        "DIGITAL CLOCK",
        12,
        0,
        1
    )

    draw_big_text(
        clock_string,
        0,
        13,
        2
    )


    # Send framebuffer to OLED
    oled.show()


oled.fill(0)

oled.text(
    "DIGITAL CLOCK",
    12,
    4,
    1
)

oled.text(
    "Starting...",
    24,
    18,
    1
)

oled.show()

time.sleep(1)

initial_light = read_light_sensor()

filtered_light = initial_light

initial_contrast = light_to_contrast(
    initial_light
)

oled.contrast(
    initial_contrast
)


display_clock()

last_light_update = time.ticks_ms()

LIGHT_UPDATE_INTERVAL = 200

while True:

    current_button1 = button1.value()
    current_button2 = button2.value()
    current_button3 = button3.value()

    now = time.ticks_ms()

    if (
        current_button1 == 0
        and
        last_button1 == 1
    ):

        if time.ticks_diff(
            now,
            last_press1
        ) > DEBOUNCE_TIME:

            add_hour()

            last_press1 = now

    if (
        current_button2 == 0
        and
        last_button2 == 1
    ):

        if time.ticks_diff(
            now,
            last_press2
        ) > DEBOUNCE_TIME:

            add_minute()

            last_press2 = now

    if (
        current_button3 == 0
        and
        last_button3 == 1
    ):

        if time.ticks_diff(
            now,
            last_press3
        ) > DEBOUNCE_TIME:

            reset_second()

            last_press3 = now

    last_button1 = current_button1
    last_button2 = current_button2
    last_button3 = current_button3

    if time.ticks_diff(
        now,
        last_light_update
    ) >= LIGHT_UPDATE_INTERVAL:

        update_brightness()

        last_light_update = now


    display_clock()

    time.sleep_ms(50)