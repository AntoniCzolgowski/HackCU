import os
import random
import threading
import time
import subprocess
from elevenlabs import ElevenLabs, play
import streamlit as st

motivational_phrases = [
    "Good rep.",
    "Excellent.",
    "Keep it up.",
    "Nice work.",
    "Solid form.",
    "Great job.",
    "Looking strong."
]

goggins_phrases = [
    "STAY HARD!",
    "Who's gonna carry the boats?!",
    "Don't be weak!",
    "They don't know you, son!",
    "Get back to work!",
    "Take their soul!"
]

class VoiceFeedback:
    def __init__(self, cooldown=3.0, custom_api_key=None, goggins_mode=False):
        self.cooldown = cooldown
        self.last_speech_time = 0
        self.goggins_mode = goggins_mode
        self._state_lock = threading.Lock()
        self._playback_lock = threading.Lock()
        self._is_speaking = False
        self._current_process = None
        
        try:
            api_key = custom_api_key or st.secrets["ELEVENLABS_API_KEY"]
        except:
            api_key = custom_api_key or os.environ.get("ELEVENLABS_API_KEY")
        
        if not api_key:
             print("WARNING: ELEVENLABS_API_KEY missing! Voice feedback disabled.")
             self.client = None
        else:
             self.client = ElevenLabs(api_key=api_key)

    def is_speaking(self):
        with self._state_lock:
            return self._is_speaking

    def stop(self):
        """Stop active playback (used only for urgent forced messages)."""
        with self._state_lock:
            proc = self._current_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def _say_worker(self, text):
        if not self.client:
             return
             
        temp_file = None
        try:
            # Serialize playback so prompts never overlap.
            with self._playback_lock:
                with self._state_lock:
                    self._is_speaking = True

                audio_generator = self.client.text_to_speech.convert(
                    voice_id="JBFqnCBsd6RMkjVDRZzb",
                    output_format="mp3_44100_128",
                    text=text,
                    model_id="eleven_multilingual_v2",
                )

                # Primary path: ElevenLabs playback helper (cross-platform).
                # It can consume the streaming generator directly.
                try:
                    play(audio_generator)
                except Exception:
                    # Fallback path: write MP3 and use afplay (macOS).
                    audio_bytes = b"".join(
                        self.client.text_to_speech.convert(
                            voice_id="JBFqnCBsd6RMkjVDRZzb",
                            output_format="mp3_44100_128",
                            text=text,
                            model_id="eleven_multilingual_v2",
                        )
                    )
                    temp_file = f"/tmp/ttstemp_{int(time.time() * 1000)}.mp3"
                    with open(temp_file, "wb") as f:
                        f.write(audio_bytes)

                    proc = subprocess.Popen(["afplay", temp_file])
                    with self._state_lock:
                        self._current_process = proc
                    proc.wait()
            
        except Exception as e:
            print(f"ElevenLabs TTS Error: {e}")
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            with self._state_lock:
                self._is_speaking = False
                self._current_process = None

    def speak(self, text, feedback_type="correction", force=False):
        """
        Speak text using ElevenLabs API in a background thread to prevent blocking OpenCV feed.
        """
        if not self.client:
            return False

        current_time = time.time()
        
        if feedback_type == "motivation":
            phrases = goggins_phrases if self.goggins_mode else motivational_phrases
            prefix = random.choice(phrases)
            text = f"{prefix} That's {text}."
            
        if not force and (current_time - self.last_speech_time) < self.cooldown:
            return False

        # Never overlap playback. Skip non-urgent prompts while speaking.
        if self.is_speaking():
            if force:
                self.stop()
            else:
                return False
            
        self.last_speech_time = current_time
        threading.Thread(target=self._say_worker, args=(text,), daemon=True).start()
        return True
