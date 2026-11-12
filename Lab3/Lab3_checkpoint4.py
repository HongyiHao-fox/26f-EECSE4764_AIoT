from machine import Pin, I2C, RTC, ADC, PWM
import ssd1306
import framebuf
import time


SDA_PIN = 22
SCL_PIN = 20

BUTTON1_PIN = 32
BUTTON2_PIN = 33
BUTTON3_PIN = 27

LIGHT_SENSOR_PIN = 26

# Piezo
PIEZO_PIN = 12

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


piezo = PWM(
    Pin(PIEZO_PIN)
)

piezo.freq(1000)

# Piezo initially OFF
piezo.duty(0)

DEBOUNCE_TIME = 200

last_button1 = button1.value()
last_button2 = button2.value()
last_button3 = button3.value()

last_press1 = 0
last_press2 = 0
last_press3 = 0

# Default alarm time
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

            if fb.pixel(px, py):

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

def add_hour():

    dt = list(
        rtc.datetime()
    )

    dt[4] = (
        dt[4] + 1
    ) % 24

    rtc.datetime(
        tuple(dt)
    )


def add_minute():

    dt = list(
        rtc.datetime()
    )

    dt[5] += 1

    if dt[5] >= 60:

        dt[5] = 0

        dt[4] = (
            dt[4] + 1
        ) % 24

    rtc.datetime(
        tuple(dt)
    )

def add_alarm_hour():

    global alarm_hour

    alarm_hour = (
        alarm_hour + 1
    ) % 24


def add_alarm_minute():

    global alarm_minute
    global alarm_hour

    alarm_minute += 1

    if alarm_minute >= 60:

        alarm_minute = 0

        alarm_hour = (
            alarm_hour + 1
        ) % 24

def read_light_sensor():

    value = light_sensor.read()

    return value


def light_to_contrast(light_value):

    if light_value < ADC_MIN:

        light_value = ADC_MIN

    if light_value > ADC_MAX:

        light_value = ADC_MAX


    contrast = (
        MIN_CONTRAST
        +
        (
            (light_value - ADC_MIN)
            *
            (MAX_CONTRAST - MIN_CONTRAST)
            //
            (ADC_MAX - ADC_MIN)
        )
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

        filtered_light = (
            filtered_light * 3
            + raw_light
        ) // 4

    contrast_value = light_to_contrast(
        filtered_light
    )


    # Change OLED brightness

    oled.contrast(
        contrast_value
    )


    # Serial output for Checkpoint 2 demonstration

    print(
        "Light:",
        raw_light,
        "Filtered:",
        filtered_light,
        "Contrast:",
        contrast_value
    )

def display_clock():

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


    # Title

    oled.text(
        "DIGITAL CLOCK",
        12,
        0,
        1
    )


    # Large clock

    draw_big_text(
        clock_string,
        0,
        13,
        2
    )


    oled.show()


def display_alarm_setting():

    alarm_string = "{:02d}:{:02d}".format(
        alarm_hour,
        alarm_minute
    )


    oled.fill(0)


    oled.text(
        "SET ALARM",
        28,
        0,
        1
    )

    draw_big_text(
        alarm_string,
        24,
        13,
        2
    )


    oled.show()

def display_alarm_ringing():

    oled.fill(0)


    oled.text(
        "*** ALARM ***",
        16,
        2,
        1
    )


    oled.text(
        "PRESS ANY BUTTON",
        0,
        18,
        1
    )


    oled.show()


def start_alarm():

    global alarm_ringing

    alarm_ringing = True


    piezo.freq(
        1000
    )

    piezo.duty(
        512
    )


    print(
        "ALARM ON!"
    )

def stop_alarm():

    global alarm_ringing

    alarm_ringing = False


    # Stop piezo

    piezo.duty(
        0
    )


    print(
        "ALARM OFF!"
    )

def check_alarm():

    global alarm_triggered_this_minute


    dt = rtc.datetime()


    current_hour = dt[4]

    current_minute = dt[5]

    if (
        alarm_enabled
        and
        current_hour == alarm_hour
        and
        current_minute == alarm_minute
    ):



        if not alarm_triggered_this_minute:

            start_alarm()

            alarm_triggered_this_minute = True


    else:

        # Once the alarm minute has passed,
        # allow alarm to trigger in the future.

        alarm_triggered_this_minute = False

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

filtered_light = read_light_sensor()


initial_contrast = light_to_contrast(
    filtered_light
)


oled.contrast(
    initial_contrast
)


display_clock()


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


            if alarm_ringing:

                stop_alarm()


            elif setting_alarm:

                add_alarm_hour()


            else:

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


            if alarm_ringing:

                stop_alarm()


            elif setting_alarm:

                add_alarm_minute()


            else:

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


            if alarm_ringing:

                stop_alarm()


            else:


                setting_alarm = not setting_alarm


                if setting_alarm:

                    print(
                        "ENTER ALARM SETTING"
                    )


                else:

                    print(
                        "ALARM SET:",
                        "{:02d}:{:02d}".format(
                            alarm_hour,
                            alarm_minute
                        )
                    )


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


    if not setting_alarm:

        check_alarm()


    if alarm_ringing:

        display_alarm_ringing()


    elif setting_alarm:
        display_alarm_setting()


    else:

        display_clock()

    time.sleep_ms(
        50
    )