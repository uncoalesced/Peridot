import numpy as np
import sounddevice as sd

class AudioTracker:
    def __init__(self, samplerate=16000, blocksize=1024):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.audio_envelope = 0.0

    def start(self):
        def _callback(indata, frames, time_info, status):
            rms = np.sqrt(np.mean(indata**2))
            self.audio_envelope = 0.9 * self.audio_envelope + 0.1 * rms
        self.stream = sd.InputStream(samplerate=self.samplerate, channels=1,
                                     blocksize=self.blocksize, callback=_callback)
        self.stream.start()

    def get_envelope(self) -> float:
        return min(1.0, self.audio_envelope * 10.0)
