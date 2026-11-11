"""Lab 5 Checkpoint 4 - PC application (Python 3.11).
Voice -> Whisper -> DeepSeek -> JSON -> ESP32 HTTP -> UI.

Install: python -m pip install gradio openai openai-whisper
Also install ffmpeg and set environment variable DS_API_KEY.
"""
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import gradio as gr
import whisper
from openai import OpenAI

# IMPORTANT: replace with the IP currently printed by the ESP32 server.
ESP32_IP = os.getenv("ESP32_IP", "YOUR_ESP32_IP")
ESP32_PORT = 8080
ESP32_URL = f"http://{ESP32_IP}:{ESP32_PORT}/"
HTTP_TIMEOUT = 12
MODEL_NAME = "deepseek-chat"
DS_API_KEY = os.getenv("DS_API_KEY", "")
NY_TZ = ZoneInfo("America/New_York")

whisper_model = whisper.load_model("tiny.en")
llm_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com") if DS_API_KEY else None

COMMAND_COUNTS = {
    "screen_on": 0,
    "screen_off": 0,
    "display_time": 0,
    "display_text": 1,
    "set_alarm": 3,
    "display_location": 0,
    "display_weather": 0,
}

SYSTEM_PROMPT = """You are a voice-command interpreter for an ESP32 smartwatch.
Return EXACTLY ONE JSON object, not markdown, no other text.
Required schema: {"name":"function_name","args":[...]}
Only these commands are allowed:
- {"name":"screen_on","args":[]} - turn OLED on
- {"name":"screen_off","args":[]} - turn OLED off
- {"name":"display_time","args":[]} - show a continuously updating clock
- {"name":"display_text","args":["short ASCII text"]} - show a message or factual answer
- {"name":"set_alarm","args":[hour,minute,second]} - set NEXT occurrence of a New York local 24-hour clock time; all three args MUST be integers
- {"name":"display_location","args":[]} - show approximate IP-based location
- {"name":"display_weather","args":[]} - show current weather

Interpret natural-language intent accurately. For general questions, answer briefly
using display_text. For unsupported requests, return display_text explaining
briefly. Keep display_text at MOST 48 printable ASCII characters (the OLED has
16 columns x 4 rows). Do not use non-ASCII symbols or emoji in display_text.
The current New York local datetime is provided in the user's message.
For relative alarms (e.g. 'in five minutes'), compute the target wall-clock
time from that supplied datetime, including crossing midnight. Do not
fabricate a time. Output only the JSON object.
"""


def validate_command(command):
    if not isinstance(command, dict):
        raise ValueError("LLM output must be a JSON object")
    name, args = command.get("name"), command.get("args")
    if name not in COMMAND_COUNTS or not isinstance(args, list):
        raise ValueError("Unknown command or args is not a list")
    if len(args) != COMMAND_COUNTS[name]:
        raise ValueError(f"{name} expects {COMMAND_COUNTS[name]} argument(s)")
    if name == "display_text":
        if not isinstance(args[0], str):
            raise ValueError("display_text argument must be a string")
        # The built-in SSD1306 font handles ASCII only.
        args[0] = "".join(c if 32 <= ord(c) <= 126 else " " for c in args[0])[:48]
    if name == "set_alarm":
        if any(isinstance(a, bool) or not isinstance(a, int) for a in args):
            raise ValueError("Alarm hour/minute/second must be integers")
        h, m, s = args
        if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
            raise ValueError("Invalid alarm clock time")
    return {"name": name, "args": args}


def interpret_command(transcription):
    if not llm_client:
        raise RuntimeError("DS_API_KEY is missing. Set it in PowerShell first.")
    now = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    response = llm_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Current New York datetime: {now}\nUser command: {transcription}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=30,
    )
    raw = (response.choices[0].message.content or "").strip()
    return validate_command(json.loads(raw))


def send_to_esp32(command):
    """Send a single HTTP POST. The ESP32 should return JSON with status/result."""
    payload = json.dumps(command, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        ESP32_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Connection": "close"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise ConnectionError(
            f"ESP32 communication failed at {ESP32_URL}: {exc}. "
            "Check its IP, Wi-Fi, and whether the server says 'Listening on port 8080'."
        ) from exc
    try:
        reply = json.loads(body)
    except ValueError as exc:
        raise ValueError(f"ESP32 returned non-JSON response: {body[:160]}") from exc
    if not isinstance(reply, dict):
        raise ValueError("ESP32 reply was not a JSON object")
    if reply.get("status") != "ok":
        raise RuntimeError(f"ESP32 error: {reply.get('message', reply)}")
    return reply.get("result", "Command completed")


def process_input(audio):
    if not audio:
        return "Please record your voice first.", "", ""
    try:
        transcription = whisper_model.transcribe(audio, fp16=False)["text"].strip()
    except Exception as exc:
        return f"Whisper error: {exc}", "", ""
    if not transcription:
        return "(No speech detected)", "", ""
    try:
        command = interpret_command(transcription)
    except Exception as exc:
        return transcription, "", f"DeepSeek / JSON error: {exc}"
    pretty_json = json.dumps(command, ensure_ascii=False, indent=2)
    try:
        result = send_to_esp32(command)
        return transcription, pretty_json, f"SUCCESS - ESP32: {result}"
    except Exception as exc:
        # Keep the successfully generated JSON visible for debugging.
        return transcription, pretty_json, f"Command created, but not executed: {exc}"


def test_connection():
    """Quick network test without requiring the microphone or API."""
    return send_to_esp32({"name": "screen_on", "args": []})


ui = gr.Interface(
    fn=process_input,
    inputs=gr.Audio(sources=["microphone"], type="filepath", label="Voice Input"),
    outputs=[
        gr.Textbox(label="Transcription / Input"),
        gr.Textbox(label="LLM Response (JSON)", lines=8),
        gr.Textbox(label="Smartwatch Response / Status", lines=4),
    ],
    title="Lab 5 - Voice Smartwatch Assistant (Checkpoint 4)",
    description=("Speak a smartwatch command. Whisper converts it to text, "
                 "DeepSeek returns JSON, and the ESP32 executes it via Wi-Fi. "
                 f"ESP32 server: {ESP32_URL}"),
)

if __name__ == "__main__":
    print("ESP32 URL:", ESP32_URL)
    print("DeepSeek API key configured:", bool(DS_API_KEY))
    ui.launch(share=True)  # Public Gradio link; share only for a trusted demo session.
