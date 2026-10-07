from machine import Pin
import neopixel
import utime

led1 = Pin(13, Pin.OUT)

pwr = Pin(2, Pin.OUT)
pwr.value(1)

led2 = neopixel.NeoPixel(Pin(0, Pin.OUT), 1)

led1.value(0)
led2[0] = (0, 0, 0)
led2.write()

last_led1 = utime.ticks_ms()
last_led2 = utime.ticks_ms()

state1 = 0
state2 = 0

while True:

    now = utime.ticks_ms()

    if utime.ticks_diff(now, last_led1) >= 100:
        state1 = not state1
        led1.value(state1)
        last_led1 = now

    if utime.ticks_diff(now, last_led2) >= 500:
        state2 = not state2

        if state2:
            led2[0] = (255, 255, 255)
        else:
            led2[0] = (0, 0, 0)

        led2.write()
        last_led2 = now