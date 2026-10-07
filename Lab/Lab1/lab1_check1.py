from machine import Pin
import utime

led = Pin(13, Pin.OUT)

DOT = 200
DASH = 400

def dot():
    led.value(1)
    utime.sleep_ms(DOT)
    led.value(0)
    utime.sleep_ms(DOT)

def dash():
    led.value(1)
    utime.sleep_ms(DASH)
    led.value(0)
    utime.sleep_ms(DOT)

while True:

    dot()
    dot()
    dot()

    utime.sleep_ms(400)

    # O = ---
    dash()
    dash()
    dash()

    utime.sleep_ms(400)

    dot()
    dot()
    dot()

    utime.sleep_ms(1000)