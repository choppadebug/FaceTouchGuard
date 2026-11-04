"""Low-amplitude audio cues on Windows using the standard winsound module.

Only asynchronous playback is used so the video/Qt loop is never blocked.
"""
import math
import struct
import tempfile
import wave
from pathlib import Path

import winsound


class AlertAudio:
    RATE = 22050

    def __init__(self, volume=0.08):
        self.volume = max(0.0, min(float(volume), 0.20))
        self.muted = False
        self._temp = tempfile.TemporaryDirectory(prefix="face_touch_alerts_")
        self.files = {}
        self._write_files()

    def _tone(self, freq_hz, duration_s):
        n = int(self.RATE * duration_s)
        ramp = max(1, int(self.RATE * 0.012))
        values = []
        for i in range(n):
            envelope = min(1.0, i / ramp, (n - 1 - i) / ramp)
            amplitude = int(32767 * self.volume * max(0.0, envelope))
            values.append(int(amplitude * math.sin(2.0 * math.pi * freq_hz * i / self.RATE)))
        return values

    def _silence(self, duration_s):
        return [0] * int(self.RATE * duration_s)

    def _save(self, name, samples):
        path = Path(self._temp.name) / f"{name}.wav"
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(self.RATE)
            f.writeframes(struct.pack("<" + "h" * len(samples), *samples))
        self.files[name] = str(path)

    def _write_files(self):
        self._save("initial", self._tone(650, 0.13))
        self._save("double", self._tone(690, 0.13) + self._silence(0.13) + self._tone(790, 0.15))
        self._save("repeat", self._tone(780, 0.16) + self._silence(0.60))

    def play_stage(self, stage):
        if self.muted:
            return
        name = {1: "initial", 2: "double", 3: "repeat"}.get(stage)
        if name:
            flags = winsound.SND_FILENAME | winsound.SND_ASYNC
            if stage == 3:
                flags |= winsound.SND_LOOP
            try:
                winsound.PlaySound(self.files[name], flags)
            except RuntimeError as exc:
                print(f"Audio unavailable: {exc}")

    def stop(self):
        # Stop our asynchronously playing WAV (including the repeating buzzer).
        try:
            winsound.PlaySound(None, 0)
        except RuntimeError:
            pass

    def set_muted(self, muted):
        self.muted = bool(muted)
        if self.muted:
            self.stop()

    def close(self):
        self.stop()
        self._temp.cleanup()
