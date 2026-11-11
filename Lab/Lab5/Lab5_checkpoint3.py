import os
import json
import re
import gradio as gr
import whisper
from openai import OpenAI

# DeepSeek API configuration
API_KEY = os.environ.get("DS_API_KEY")
MODEL_NAME = "deepseek-chat"

# Initialize DeepSeek client
client = OpenAI(
    api_key=API_KEY or "NOT_CONFIGURED",
    base_url="https://api.deepseek.com"
)

# Load Whisper
whisper_model = whisper.load_model("tiny.en")

SYSTEM_PROMPT = """You are a voice-command interpreter for an ESP32 smartwatch.
Return exactly one JSON object, without markdown or explanation.
Use only this schema: {"name": "function_name", "args": [arguments]}.
Valid commands:
- {"name":"screen_on","args":[]}: turn OLED on
- {"name":"screen_off","args":[]}: turn OLED off
- {"name":"display_time","args":[]}: show updating clock
- {"name":"display_text","args":["short text"]}: show text on OLED
- {"name":"set_alarm","args":[hour,minute,second]}: set a 24h alarm for the requested clock time
- {"name":"display_location","args":[]}: show device approximate location
- {"name":"display_weather","args":[]}: show current weather
If the user asks a general question unrelated to these commands, respond with
{"name":"display_text","args":["brief answer"]}.
Keep display text within 48 ASCII characters to fit the small OLED.
Never invent a current time. If a relative alarm is requested and the current
clock time is not supplied, ask for an absolute time via display_text.
"""

ARG_COUNTS = {
    "screen_on": 0, "screen_off": 0, "display_time": 0,
    "display_text": 1, "set_alarm": 3,
    "display_location": 0, "display_weather": 0,
}


def validate_command(command):
    if not isinstance(command, dict):
        raise ValueError("DeepSeek did not return a JSON object")
    name = command.get("name")
    args = command.get("args")
    if name not in ARG_COUNTS or not isinstance(args, list):
        raise ValueError("Unknown function or invalid args")
    if len(args) != ARG_COUNTS[name]:
        raise ValueError("Incorrect number of args")
    if name == "display_text":
        if not isinstance(args[0], str):
            raise ValueError("Text must be a string")
        args[0] = args[0][:48]
    if name == "set_alarm":
        if not all(isinstance(a, int) and not isinstance(a, bool) for a in args):
            raise ValueError("Alarm arguments must be integers")
        h, m, s = args
        if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
            raise ValueError("Invalid alarm time")
    return {"name": name, "args": args}


def process_input(audio):
    if audio is None:
        return "Please record your voice first.", "", ""

    try:
        transcription = whisper_model.transcribe(
            audio, fp16=False
        )["text"].strip()
    except Exception as exc:
        return f"Speech recognition failed: {exc}", "", ""

    if not transcription:
        return "(No speech detected)", "", ""

    if not API_KEY:
        return transcription, "", "Set DS_API_KEY before launching."

    try:
        # DeepSeek API call
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": transcription
                }
            ],
            response_format={"type": "json_object"},
            temperature=0
        )

        raw = (
            response.choices[0].message.content or ""
        ).strip()

        command = validate_command(json.loads(raw))

        formatted = json.dumps(
            command,
            ensure_ascii=False,
            indent=2
        )

        return (
            transcription,
            formatted,
            "Valid JSON command (Checkpoint 3 complete)."
        )

    except Exception as exc:
        return transcription, "", f"DeepSeek/JSON error: {exc}"


ui = gr.Interface(
    fn=process_input,
    inputs=gr.Audio(
        sources=["microphone"],
        type="filepath",
        label="Voice Input"
    ),
    outputs=[
        gr.Textbox(label="Transcription / Input"),
        gr.Textbox(label="LLM Response (JSON)"),
        gr.Textbox(label="Status"),
    ],
    title="Lab 5 - Voice Smartwatch Assistant (Checkpoint 3)",
    description="Speak a command. Whisper transcribes it and DeepSeek converts it to smartwatch JSON.",
)

if __name__ == "__main__":
    ui.launch(share=True)
