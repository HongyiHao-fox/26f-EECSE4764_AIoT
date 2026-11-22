from machine import Pin, PWM, ADC
import time

LED_PIN = 14

PIEZO_PIN = 12

light_sensor = ADC(0)
a

led = PWM(Pin(LED_PIN))
led.freq(1000)
led.duty(0)

piezo = PWM(Pin(PIEZO_PIN))
piezo.freq(500)
piezo.duty(0)

def map_value(x, in_min, in_max, out_min, out_max):

    x = max(in_min, min(x, in_max))

    return int(
        (x - in_min) *
        (out_max - out_min) /
        (in_max - in_min) +
        out_min
    )

while True:
    light_value = light_sensor.read()

    print("Light sensor:", light_value)

    led_duty = map_value(
        light_value,
        0, 1023,
        0, 1023
    )

    led.duty(led_duty)

    piezo_frequency = map_value(
        light_value,
        0, 1023,
        200, 2000
    )

    piezo.freq(piezo_frequency)

    piezo.duty(512)

    print(
        "LED duty:",
        led_duty,
        "Piezo frequency:",
        piezo_frequency,
        "Hz"
    )

    time.sleep(0.1)