# Lab 5 - Checkpoint 2 client
import json
import urllib.request

ESP32_IP = 'YOUR_ESP32_IP'  # Replace with the IP printed in Thonny
URL = 'http://%s:8080/' % ESP32_IP


def send_command(name, args=None):
    command = {'name': name, 'args': [] if args is None else args}
    data = json.dumps(command).encode('utf-8')
    request = urllib.request.Request(
        URL, data=data, method='POST',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as result:
            print('ESP32:', result.read().decode('utf-8'))
    except Exception as e:
        print('Connection error:', e)


while True:
    print('\n1. Screen ON\n2. Screen OFF\n3. Display time')
    print('4. Display text\n5. Set alarm\n6. Location')
    print('7. Weather\n0. Exit')
    choice = input('Select: ').strip()
    if choice == '1':
        send_command('screen_on')
    elif choice == '2':
        send_command('screen_off')
    elif choice == '3':
        send_command('display_time')
    elif choice == '4':
        send_command('display_text', [input('Text: ')])
    elif choice == '5':
        send_command('set_alarm', [int(input('Hour (0-23): ')),
                                   int(input('Minute: ')),
                                   int(input('Second: '))])
    elif choice == '6':
        send_command('display_location')
    elif choice == '7':
        send_command('display_weather')
    elif choice == '0':
        break
    else:
        print('Unknown choice')
