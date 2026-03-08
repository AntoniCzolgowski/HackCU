import os
import random
import threading
import time
import speech_recognition as sr
from groq import Groq
from voice_feedback import VoiceFeedback
import streamlit as st

class VoiceAssistant:
    def __init__(self, tts_engine: VoiceFeedback, goggins_mode=False):
        self.tts = tts_engine
        self.listening = False
        self.thread = None
        self.recognizer = sr.Recognizer()
        self.mic_available = True
        
        try:
            self.groq_key = st.secrets["GROQ_API_KEY"]
        except:
            self.groq_key = os.environ.get("GROQ_API_KEY")
        self.client = Groq(api_key=self.groq_key) if self.groq_key else None
        
        # System prompt setting the AI persona
        stn_prompt = (
            "You are a highly energetic, concise AI personal trainer. "
            "The user is currently working out. Answer their questions in 1-2 short sentences maximum. "
            "Do not give long explanations, keep it punchy and motivating."
        )
        goggins_prompt = (
            "You are David Goggins, the hardest man alive. The user is currently working out. "
            "Answer in 1-2 short, BRUTAL sentences. Be confrontational, ruthless, and high-pressure. "
            "Use intense tough-love, call out excuses directly, and demand effort now. "
            "Use lines like 'Stay Hard', 'Stop being weak', and 'Who's gonna carry the boats'. "
            "No politeness, no comfort, no long explanations."
        )
        self.system_prompt = goggins_prompt if goggins_mode else stn_prompt
        self._trash_fallback = [
            "YOU DIDN'T COME THIS FAR TO QUIT!",
            "THIS REP DECIDES WHO YOU ARE!",
            "LOCK IN AND FINISH STRONG!",
            "YOU'RE TIRED, NOT DONE!",
            "EARN THIS LAST REP!",
        ]

    def start_listening(self):
        """Start the background listening thread."""
        if not self.client:
            print("WARNING: GROQ_API_KEY missing. Conversational AI disabled.")
            return
        try:
            # Touch microphone once so we fail fast if PyAudio/mic backend is missing.
            with sr.Microphone():
                pass
            self.mic_available = True
        except Exception as e:
            self.mic_available = False
            print(f"WARNING: Voice input disabled: {e}")
            return
            
        self.listening = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        
    def stop_listening(self):
        self.listening = False

    def _listen_loop(self):
        """Continuously listen for audio using the default microphone."""
        # Optional: We could implement wake words here, 
        # but for a gym session, listening for any speech gap is sufficient.
        
        while self.listening:
            # Prevent microphone feedback loops while coach audio is speaking.
            if self.tts and self.tts.is_speaking():
                time.sleep(0.2)
                continue

            try:
                with sr.Microphone() as source:
                    # Adjust for ambient noise to avoid picking up dropping weights
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    try:
                        # Listen for audio chunk
                        audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=5.0)
                        
                        # Decipher words
                        text = self.recognizer.recognize_google(audio).lower()
                        
                        if text and len(text) > 5:
                             print(f"User asked: {text}")
                             self._generate_response(text)
                             
                    except sr.WaitTimeoutError:
                        pass
                    except sr.UnknownValueError:
                        pass
                    except Exception as e:
                        print(f"STT Error: {e}")
            except Exception as e:
                # Missing PyAudio/device permissions/etc. Disable listener cleanly.
                print(f"WARNING: Microphone unavailable, stopping listener: {e}")
                self.listening = False
                self.mic_available = False
                break
            
            time.sleep(0.1)
            
    def _generate_response(self, query):
        """Ping Groq for a concise answer."""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=60,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content.strip()
            print(f"AI Coach: {reply}")
            
            # Speak it using ElevenLabs! Force=True to bypass cooldowns.
            self.tts.speak(reply, feedback_type="correction", force=True)
            
        except Exception as e:
             print(f"LLM Error: {e}")

    def generate_trash_talk(self, exercise="squats", fatigue_score=0.8, trigger="slowing down"):
        """
        Generates a short aggressive line for high-fatigue moments.
        """
        if not self.client:
            return random.choice(self._trash_fallback)

        try:
            prompt = (
                f"Generate one savage bullying motivational line (max 10 words) for someone doing {exercise}. "
                f"Fatigue score is {fatigue_score:.2f}. Trigger: {trigger}. "
                "Use all caps. No profanity. No kindness."
            )
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=32,
                temperature=0.9,
            )
            line = response.choices[0].message.content.strip()
            return line if line else random.choice(self._trash_fallback)
        except Exception as e:
            print(f"Trash-talk generation error: {e}")
            return random.choice(self._trash_fallback)
