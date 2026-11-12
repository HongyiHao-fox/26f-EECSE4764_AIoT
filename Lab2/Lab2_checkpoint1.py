from machine import Pin
import utime

LED_PIN = 14
PEIZO_PIN = 12
LIGHT_SENSOR_PIN = 36

led = PWM(Pin(LED_PIN), freq=1000)
piezo = PWM(Pin(PEIZO_PIN), freq=1000)
light_sensor = ADC(Pin(LIGHT_SENSOR_PIN))

while True:
    input = light_sensor.read()