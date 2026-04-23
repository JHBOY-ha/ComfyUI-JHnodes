import os
import re
import shutil
import subprocess
from collections.abc import Mapping

import torch


def _resolve_ffmpeg_path():
    p = os.environ.get("JHNODES_FFMPEG_PATH") or os.environ.get("VHS_FORCE_FFMPEG_PATH")
    if p:
        return p
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


FFMPEG_PATH = _resolve_ffmpeg_path()

EMPTY_AUDIO = {
    "waveform": torch.zeros(1, 2, 1, dtype=torch.float32),
    "sample_rate": 44100,
}


def get_audio(file, start_time=0, duration=0):
    if FFMPEG_PATH is None:
        raise RuntimeError(
            "ffmpeg not found. Install `imageio-ffmpeg` or set JHNODES_FFMPEG_PATH."
        )
    args = [FFMPEG_PATH, "-i", file]
    if start_time > 0:
        args += ["-ss", str(start_time)]
    if duration > 0:
        args += ["-t", str(duration)]
    try:
        res = subprocess.run(
            args + ["-f", "f32le", "-"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg failed to extract audio from {file}:\n"
            + e.stderr.decode("utf-8", errors="replace")
        )
    waveform = torch.frombuffer(bytearray(res.stdout), dtype=torch.float32)
    m = re.search(r", (\d+) Hz, (\w+), ", res.stderr.decode("utf-8", errors="replace"))
    if m:
        sample_rate = int(m.group(1))
        channels = {"mono": 1, "stereo": 2}.get(m.group(2), 2)
    else:
        sample_rate = 44100
        channels = 2
    if waveform.numel() == 0:
        return {"waveform": torch.zeros(1, channels, 1, dtype=torch.float32),
                "sample_rate": sample_rate}
    waveform = waveform.reshape((-1, channels)).transpose(0, 1).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


class LazyAudioMap(Mapping):
    def __init__(self, file, start_time=0, duration=0):
        self.file = file
        self.start_time = start_time
        self.duration = duration
        self._dict = None

    def _ensure(self):
        if self._dict is None:
            self._dict = get_audio(self.file, self.start_time, self.duration)

    def __getitem__(self, key):
        self._ensure()
        return self._dict[key]

    def __iter__(self):
        self._ensure()
        return iter(self._dict)

    def __len__(self):
        self._ensure()
        return len(self._dict)


def lazy_get_audio(file, start_time=0, duration=0):
    return LazyAudioMap(file, start_time, duration)
