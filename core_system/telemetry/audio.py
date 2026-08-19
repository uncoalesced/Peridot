# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | ZAT-SCS ACOUSTIC ENVELOPE SENSOR
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import logging

import numpy as np

logger = logging.getLogger("Peridot-ZAT")


class AudioTracker:
    """
    Microphone RMS sensor feeding the g_a term of P(I_t).

    `available` is False when PortAudio or an input device is missing, in which
    case the caller must zero the audio weight rather than read the flat 0.0
    envelope as genuine silence.
    """

    def __init__(self, samplerate=16000, blocksize=1024):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.audio_envelope = 0.0
        self.stream = None
        self.available = True
        self.degradation_reason = None

    def start(self):
        # sounddevice binds PortAudio at import time and raises OSError -- not
        # ImportError -- when libportaudio is absent (stock Debian 12 / Arch
        # without portaudio19-dev). Importing lazily here keeps that failure
        # local to the sensor instead of taking the whole ZAT-SCS stack, and
        # the server process, down at import.
        try:
            import sounddevice as sd
        except Exception as e:
            self.available = False
            self.degradation_reason = f"PortAudio unavailable ({e})"
            logger.warning(
                "[ZAT-SCS] Audio telemetry DEGRADED: %s. "
                "P(I_t) loses its acoustic term (audio weight = 0).",
                self.degradation_reason,
            )
            return False

        def _callback(indata, frames, time_info, status):
            rms = np.sqrt(np.mean(indata**2))
            self.audio_envelope = 0.9 * self.audio_envelope + 0.1 * rms

        try:
            self.stream = sd.InputStream(
                samplerate=self.samplerate, channels=1,
                blocksize=self.blocksize, callback=_callback,
            )
            self.stream.start()
        except Exception as e:
            self.available = False
            self.degradation_reason = f"no usable input device ({e})"
            logger.warning(
                "[ZAT-SCS] Audio telemetry DEGRADED: %s. "
                "P(I_t) loses its acoustic term (audio weight = 0).",
                self.degradation_reason,
            )
            return False

        logger.info("[ZAT-SCS] Audio telemetry online.")
        return True

    def get_envelope(self) -> float:
        if not self.available:
            return 0.0
        return min(1.0, self.audio_envelope * 10.0)
