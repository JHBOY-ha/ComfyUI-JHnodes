import subprocess

import torch

import jhnodes.ffmpeg as ffmpeg


def test_get_audio_returns_empty_audio_when_video_has_no_audio_stream(monkeypatch):
    stderr = (
        "Output #0, f32le, to 'pipe:'\n"
        "[out#0/f32le @ 0xe38a6c0] Output file does not contain any stream\n"
        "Error opening output file -.\n"
        "Error opening output files: Invalid argument\n"
    )

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], output=b"", stderr=stderr.encode())

    monkeypatch.setattr(ffmpeg, "FFMPEG_PATH", "/tmp/ffmpeg")
    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)

    audio = ffmpeg.get_audio("input/test.mp4")

    assert audio["sample_rate"] == ffmpeg.EMPTY_AUDIO["sample_rate"]
    assert torch.equal(audio["waveform"], ffmpeg.EMPTY_AUDIO["waveform"])


def test_get_audio_still_raises_for_real_ffmpeg_failures(monkeypatch):
    stderr = "Permission denied"

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], output=b"", stderr=stderr.encode())

    monkeypatch.setattr(ffmpeg, "FFMPEG_PATH", "/tmp/ffmpeg")
    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)

    try:
        ffmpeg.get_audio("input/test.mp4")
    except RuntimeError as exc:
        assert "ffmpeg failed to extract audio" in str(exc)
        assert "Permission denied" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
