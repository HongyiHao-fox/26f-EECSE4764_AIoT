from machine import Pin, PWM, ADC
import time

# Pin configuration
LED_PIN = 14
PIEZO_PIN = 12
BUTTON_PIN = 13

light_sensor = ADC(0)

# Btn
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

led = PWM(Pin(LED_PIN))
led.freq(1000)
led.duty(0)

piezo = PWM(Pin(PIEZO_PIN))
piezo.freq(500)
piezo.duty(0)

system_on = False
interrupt_flag = False
last_state = button.value()


def button_interrupt(pin):
    global interrupt_flag
    interrupt_flag = True


button.irq(
    trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
    handler=button_interrupt
)

def map_value(x, in_min, in_max, out_min, out_max):

    x = max(in_min, min(x, in_max))

    return int(
        (x - in_min)
        * (out_max - out_min)
        / (in_max - in_min)
        + out_min
    )


print("Checkpoint 3 ready")

while True:

    if interrupt_flag:

        interrupt_flag = False

        time.sleep_ms(50)

        current_state = button.value()

        if current_state != last_state:

            if current_state == 0:

                system_on = True
                print("System ON")

            else:

                system_on = False

                led.duty(0)
                piezo.duty(0)

                print("System OFF")

            last_state = current_state

    if system_on:

        light_value = light_sensor.read()
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
            "Light:", light_value,
            "LED:", led_duty,
            "Piezo:", piezo_frequency
        )

        time.sleep_ms(100)

    else:

        time.sleep_ms(10)