import os
import streamlit as st

from elevenlabs import ElevenLabs, play
try:
    api_key = st.secrets["ELEVENLABS_API_KEY"]
except:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=api_key)
audio = client.text_to_speech.convert(
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    output_format="mp3_44100_128",
    text="Testing audio output",
    model_id="eleven_multilingual_v2",
)
try:
    play(audio)
    print("PLAY SUCCESS")
except Exception as e:
    print(f"PLAY ERROR: {e}")
