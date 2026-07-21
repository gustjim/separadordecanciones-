import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from app.audio_utils import (
    check_ffmpeg,
    check_demucs,
    get_audio_duration,
    get_audio_info,
    convert_wav_to_mp3,
)


class TestCheckFfmpeg:
    def test_returns_true_when_installed(self):
        with patch("app.audio_utils.shutil.which", return_value="/usr/bin/ffmpeg"):
            assert check_ffmpeg() is True

    def test_returns_false_when_not_installed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.audio_utils.shutil.which", return_value=None), \
             patch("app.audio_utils.sys.prefix", tmpdir):
            assert check_ffmpeg() is False


class TestCheckDemucs:
    def test_returns_true_when_installed(self):
        with patch("app.audio_utils.shutil.which", return_value="/usr/bin/demucs"):
            assert check_demucs() is True

    def test_returns_false_when_not_installed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.audio_utils.shutil.which", return_value=None), \
             patch("app.audio_utils.sys.prefix", tmpdir):
            assert check_demucs() is False


class TestGetAudioDuration:
    def test_returns_zero_when_ffmpeg_missing(self):
        with patch("app.audio_utils.check_ffmpeg", return_value=False):
            assert get_audio_duration(Path("/fake/file.wav")) == 0.0

    def test_returns_duration_from_ffprobe(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"format": {"duration": "180.5"}}'
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", return_value=mock_result):
            result = get_audio_duration(Path("/fake/file.wav"))
            assert result == 180.5

    def test_returns_zero_on_invalid_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", return_value=mock_result):
            assert get_audio_duration(Path("/fake/file.wav")) == 0.0

    def test_returns_zero_on_timeout(self):
        import subprocess as _subprocess
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", side_effect=_subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)):
            assert get_audio_duration(Path("/fake/file.wav")) == 0.0


class TestGetAudioInfo:
    def test_returns_defaults_when_ffmpeg_missing(self):
        with patch("app.audio_utils.check_ffmpeg", return_value=False):
            info = get_audio_info(Path("/fake/file.wav"))
            assert info["duration"] == 0.0
            assert info["sample_rate"] == 0
            assert info["channels"] == 0

    def test_returns_info_from_ffprobe(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''{
            "format": {"duration": "240.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "sample_rate": "44100", "channels": 2}]
        }'''
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", return_value=mock_result):
            info = get_audio_info(Path("/fake/file.mp3"))
            assert info["duration"] == 240.0
            assert info["sample_rate"] == 44100
            assert info["channels"] == 2
            assert info["format"] == "mp3"

    def test_returns_zero_on_error(self):
        import subprocess as _subprocess
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", side_effect=_subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)):
            info = get_audio_info(Path("/fake/file.wav"))
            assert info["duration"] == 0.0


class TestConvertWavToMp3:
    def test_returns_false_when_ffmpeg_missing(self):
        with patch("app.audio_utils.check_ffmpeg", return_value=False):
            assert convert_wav_to_mp3(Path("/fake/in.wav"), Path("/fake/out.mp3")) is False

    def test_returns_true_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", return_value=mock_result), \
             patch("app.audio_utils.Path.exists", return_value=True):
            assert convert_wav_to_mp3(Path("/fake/in.wav"), Path("/fake/out.mp3")) is True

    def test_returns_false_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("app.audio_utils.check_ffmpeg", return_value=True), \
             patch("app.audio_utils.subprocess.run", return_value=mock_result):
            assert convert_wav_to_mp3(Path("/fake/in.wav"), Path("/fake/out.mp3")) is False
