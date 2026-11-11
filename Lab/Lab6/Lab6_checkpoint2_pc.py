import os
import re
import json
import socket
import time
from pathlib import Path

import requests







ESP32_IP = "YOUR_ESP32_IP"
ESP32_PORT = 8765

GEMINI_MODEL = "gemini-3.5-flash-lite"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/"
    + GEMINI_MODEL
    + ":generateContent"
)

SAVE_DIR = (
    Path(__file__).resolve().parent
    / "results_checkpoint2"
)

ACTIVITIES = [
    "WALKING",
    "WALKING_UPSTAIRS",
    "WALKING_DOWNSTAIRS",
    "SITTING",
    "STANDING",
    "LAYING"
]






def send_json(sock, obj):
    data = json.dumps(obj) + "\n"
    sock.sendall(data.encode("utf-8"))


def receive_json(sock):
    data = bytearray()

    while True:
        chunk = sock.recv(1)

        if not chunk:
            raise ConnectionError(
                "ESP32 disconnected"
            )

        if chunk == b"\n":
            break

        data.extend(chunk)

        if len(data) > 100000:
            raise ValueError(
                "Received message too large"
            )

    return json.loads(
        data.decode("utf-8")
    )






def build_prompt(samples):

    if len(samples) != 128:
        raise ValueError(
            "Expected 128 samples"
        )

    x = [float(row[0]) for row in samples]
    y = [float(row[1]) for row in samples]
    z = [float(row[2]) for row in samples]

    def format_channel(values):
        return ", ".join(
            f"{v:.4f}" for v in values
        )

    prompt = f"""
You are performing Human Activity Recognition
using real-world accelerometer data.

Device: ESP32
Sensor: ADXL345
Sensor location: Waist
Environment: Columbia University campus

Sampling frequency: 50 Hz
Number of samples: 128
Duration: 2.56 seconds
Unit: g

Available channels:
Accelerometer X
Accelerometer Y
Accelerometer Z

No gyroscope is available.

Candidate activities:

WALKING
WALKING_UPSTAIRS
WALKING_DOWNSTAIRS
SITTING
STANDING
LAYING

Accelerometer X:
[{format_channel(x)}]

Accelerometer Y:
[{format_channel(y)}]

Accelerometer Z:
[{format_channel(z)}]

Question:
Which activity is being performed?

Use acceleration variation, periodicity,
gravity orientation and motion intensity.

Be careful not to confuse minor sensor noise
with walking.

Select exactly one candidate activity.

Do not explain your reasoning.
Do not provide analysis.
Do not provide numbered steps.

You must return exactly ONE line.

The response must begin with ACTIVITY:

Example:
ACTIVITY: STANDING

Choose one label from:
WALKING
WALKING_UPSTAIRS
WALKING_DOWNSTAIRS
SITTING
STANDING
LAYING

Output the classification now.
"""

    return prompt.strip()






def call_gemini(prompt):

    key = os.getenv("GEMINI_API_KEY")

    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing"
        )

    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1024
        }
    }

    last_error = None

    for attempt in range(2):

        try:
            print(
                "Calling Gemini:",
                GEMINI_MODEL,
                "attempt:",
                attempt + 1
            )

            response = requests.post(
                GEMINI_URL,
                headers=headers,
                json=payload,
                timeout=(10, 35)
            )

            if response.status_code in (
                429, 500, 502, 503, 504
            ):
                print(
                    "API temporary error:",
                    response.status_code
                )

                response.raise_for_status()

            response.raise_for_status()

            result = response.json()

            candidates = result.get(
                "candidates", []
            )

            if not candidates:
                raise RuntimeError(
                    "No Gemini candidates: "
                    + str(result)[:500]
                )

            parts = candidates[0].get(
                "content", {}
            ).get("parts", [])

            answer = "".join(
                p.get("text", "")
                for p in parts
            ).strip()

            if not answer:
                raise RuntimeError(
                    "Empty Gemini response"
                )

            return answer

        except requests.RequestException as e:
            last_error = e
            print("API error:", e)

            if attempt < 1:
                time.sleep(2)

    raise RuntimeError(
        "Gemini request failed: "
        + str(last_error)
    )






def parse_activity(text):

    options = "|".join(
        sorted(
            ACTIVITIES,
            key=len,
            reverse=True
        )
    )

    match = re.search(
        rf"ACTIVITY\s*:\s*({options})\b",
        text.upper()
    )

    if match:
        return match.group(1)

    cleaned = text.upper().strip(
        " \n\r\t.,:*`"
    )

    if cleaned in ACTIVITIES:
        return cleaned

    return "UNKNOWN"






def save_result(samples, prompt, response, activity):

    SAVE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    record = {
        "timestamp": timestamp,
        "device": "ESP32 ADXL345",
        "model": GEMINI_MODEL,
        "sampling_rate_hz": 50,
        "window_length": 128,
        "unit": "g",
        "samples": samples,
        "prompt": prompt,
        "response": response,
        "prediction": activity
    }

    filename = (
        SAVE_DIR / f"HAR_{timestamp}.json"
    )

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            record,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("Saved:", filename)






def classify_har():

    print("\n" + "=" * 55)
    print("Lab 6 Checkpoint 2")
    print("=" * 55)

    print(
        "Connecting to ESP32:",
        ESP32_IP,
        ESP32_PORT
    )

    with socket.create_connection(
        (ESP32_IP, ESP32_PORT),
        timeout=10
    ) as sock:

        sock.settimeout(110)


        send_json(
            sock,
            {"command": "classify_HAR"}
        )

        print("Collecting sensor data...")

        response = receive_json(sock)

        if response.get("status") != "ok":
            raise RuntimeError(
                str(response)
            )

        samples = response["samples"]

        print("Received:", len(samples))
        print("First sample:", samples[0])

        prompt = build_prompt(samples)


        try:
            answer = call_gemini(prompt)
            prediction = parse_activity(answer)

        except Exception as e:
            print("Gemini error:", e)

            answer = "ERROR: " + str(e)
            prediction = "UNKNOWN"

        print("\nGemini response:")
        print(answer)

        print("\nPrediction:", prediction)


        send_json(
            sock,
            {
                "command": "display_HAR",
                "activity": prediction
            }
        )

        print("Sent prediction to ESP32")

        save_result(
            samples,
            prompt,
            answer,
            prediction
        )

    print("Checkpoint 2 cycle finished")






def main():

    print("=" * 55)
    print("EECS E4764 Lab 6 - Checkpoint 2")
    print("Campus WiFi: Columbia University")
    print("Gemini model:", GEMINI_MODEL)
    print("=" * 55)

    print("\nAvailable commands:")
    print("classify_HAR")
    print("exit")

    while True:

        command = input(
            "\nEnter command: "
        ).strip().lower()

        if command == "exit":
            break

        elif command == "classify_har":

            try:
                classify_har()

            except Exception as e:
                print(
                    "[ERROR]",
                    type(e).__name__,
                    str(e)
                )

        else:
            print("Unknown command")


if __name__ == "__main__":
    main()
