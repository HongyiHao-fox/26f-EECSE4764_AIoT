from machine import Pin
import time

BUTTON_PIN = 13

button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

last_state = button.value()

interrupt_flag = False


def button_interrupt(pin):
    global interrupt_flag

    interrupt_flag = True

button.irq(
    trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
    handler=button_interrupt
)

print("Checkpoint 2 ready")


while True:

    if interrupt_flag:

        interrupt_flag = False

        time.sleep_ms(50)

        current_state = button.value()

        if current_state != last_state:

            if current_state == 0:
                print("Button PRESSED")

            else:
                print("Button RELEASED")

            last_state = current_state

    time.sleep_ms(5)