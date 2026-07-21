import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from app.spleeter_separator import separate_audio_spleeter
from app.models import SeparationMode


class TestSeparateAudioSpleeter:
    def test_raises_when_spleeter_not_installed(self):
        with patch("app.spleeter_separator.check_spleeter", return_value=False):
            with pytest.raises(RuntimeError, match="Spleeter no esta instalado"):
                separate_audio_spleeter(
                    Path("/fake/input.mp3"),
                    Path("/fake/output"),
                    SeparationMode.FIVE_STEMS,
                )

    def test_raises_when_ffmpeg_not_installed(self):
        with patch("app.spleeter_separator.check_spleeter", return_value=True), \
             patch("app.spleeter_separator.check_ffmpeg", return_value=False):
            with pytest.raises(RuntimeError, match="FFmpeg no esta instalado"):
                separate_audio_spleeter(
                    Path("/fake/input.mp3"),
                    Path("/fake/output"),
                    SeparationMode.FIVE_STEMS,
                )

    def test_raises_when_spleeter_fails(self):
        with patch("app.spleeter_separator.check_spleeter", return_value=True), \
             patch("app.spleeter_separator.check_ffmpeg", return_value=True), \
             patch("app.spleeter_separator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Spleeter error"
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(RuntimeError, match="Spleeter fallo"):
                    separate_audio_spleeter(
                        Path("/fake/input.mp3"),
                        Path(tmpdir) / "output",
                        SeparationMode.FIVE_STEMS,
                    )

    def test_five_stems_uses_correct_preset(self):
        with patch("app.spleeter_separator.check_spleeter", return_value=True), \
             patch("app.spleeter_separator.check_ffmpeg", return_value=True), \
             patch("app.spleeter_separator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with tempfile.TemporaryDirectory() as tmpdir:
                separate_audio_spleeter(
                    Path("/fake/input.mp3"),
                    Path(tmpdir) / "output",
                    SeparationMode.FIVE_STEMS,
                )
                call_args = mock_run.call_args
                assert "spleeter:5stems" in call_args[0][0]

    def test_finds_stems_in_subdirectory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "output"
            subdir = out / "song"
            subdir.mkdir(parents=True)
            for stem in ["vocals", "drums", "bass", "piano", "other"]:
                (subdir / f"{stem}.wav").write_bytes(b"fake")

            with patch("app.spleeter_separator.check_spleeter", return_value=True), \
                 patch("app.spleeter_separator.check_ffmpeg", return_value=True), \
                 patch("app.spleeter_separator.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = separate_audio_spleeter(
                    Path("/fake/song.mp3"),
                    out,
                    SeparationMode.FIVE_STEMS,
                )
                assert len(result) == 5
                assert "vocals" in result
                assert "piano" in result
