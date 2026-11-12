import gradio as gr
import whisper

# Load Whisper speech recognition model
model = whisper.load_model("tiny.en")

# Process microphone audio
def process_input(audio):
    if audio is None:
        return "Please record your voice first."

    try:
        result = model.transcribe(audio)
        return result["text"].strip()
    except Exception as e:
        return f"Error: {e}"

# Create Gradio web interface
ui = gr.Interface(
    fn=process_input,
    inputs=gr.Audio(
        sources=["microphone"],
        type="filepath",
        label="Voice Input"
    ),
    outputs=gr.Textbox(
        label="Transcription"
    ),
    title="Voice Assistant",
    description="Record your voice and convert it to text using Whisper."
)

# Launch web app
if __name__ == "__main__":
    ui.launch(debug=False, share=True)
