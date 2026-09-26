# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

# core_system/ears.py

# whisper (and torch under it) is imported in _load_model, on first use: at
# module level it put torch + a ~460MB model load on every UI startup, voice
# used or not.
import speech_recognition as sr
import threading
import logging
import os

logger = logging.getLogger("Peridot-Ears")


class PeridotEars:
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self._load_lock = threading.Lock()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    def _load_model(self) -> bool:
        """Loads Whisper on CPU to save GPU for the Brain. Idempotent."""
        with self._load_lock:
            if self.is_loaded:
                return True
            try:
                import whisper
                # FORCE CPU DEVICE
                logger.info("Loading Whisper (Small) on CPU...")
                self.model = whisper.load_model("small", device="cpu")
                self.is_loaded = True
                logger.info("Whisper Audio Model Loaded Successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")
                return False

    def load_model_async(self, callback=None):
        """Preload Whisper in the background (optional; listen() loads on demand)."""

        def _load():
            ok = self._load_model()
            if callback:
                callback(ok)

        threading.Thread(target=_load, daemon=True).start()

    def listen(self, duration=5):
        """Records audio for a fixed duration and returns text."""
        # First use pays the load here; callers run listen() off the UI thread.
        if not self.is_loaded and not self._load_model():
            return "[ERROR] Audio model failed to load. Check the console log."

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
            except Exception:
                pass

            return text

        except sr.WaitTimeoutError:
            return "[SILENCE]"
        except Exception as e:
            return f"[ERROR] Audio capture failed: {e}"
