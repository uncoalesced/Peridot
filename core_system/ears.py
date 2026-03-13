# core_system/ears.py
# Engineered by uncoalesced.

import whisper
import speech_recognition as sr
import threading
import logging
import os

logger = logging.getLogger("iCould-Ears")


class PeridotEars:  # Renamed class to match core.py expectation if needed, or keep iCouldEars
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    def load_model_async(self, callback=None):
        """Loads Whisper on CPU to save GPU for the Brain."""

        def _load():
            try:
                # FORCE CPU DEVICE
                logger.info("Loading Whisper (Small) on CPU...")
                self.model = whisper.load_model("small", device="cpu")

                self.is_loaded = True
                logger.info("Whisper Audio Model Loaded Successfully.")
                if callback:
                    callback(True)
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")
                if callback:
                    callback(False)

        threading.Thread(target=_load, daemon=True).start()

    def listen(self, duration=5):
        """Records audio for a fixed duration and returns text."""
        if not self.is_loaded:
            return "[ERROR] Audio systems initializing... please wait."

        try:
            with self.microphone as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Listening...")
                audio = self.recognizer.listen(
                    source, timeout=duration, phrase_time_limit=duration
                )

            # Save temp file for Whisper
            with open("temp.wav", "wb") as f:
                f.write(audio.get_wav_data())

            # Transcribe (fp16=False is REQUIRED for CPU)
            result = self.model.transcribe("temp.wav", fp16=False)
            text = result["text"].strip()

            try:
                os.remove("temp.wav")
            except:
                pass

            return text

        except sr.WaitTimeoutError:
            return "[SILENCE]"
        except Exception as e:
            return f"[ERROR] Audio capture failed: {e}"
