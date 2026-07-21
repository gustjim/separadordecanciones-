import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from app.separator import separate_audio
from app.models import SeparationMode


class TestSeparateAudio:
    def test_raises_when_demucs_not_installed(self):
        with patch("app.separator.check_demucs", return_value=False):
            with pytest.raises(RuntimeError, match="Demucs no está instalado"):
                separate_audio(
                    Path("/fake/input.mp3"),
                    Path("/fake/output"),
                    SeparationMode.TWO_STEMS,
                )

    def test_raises_when_ffmpeg_not_installed(self):
        with patch("app.separator.check_demucs", return_value=True), \
             patch("app.separator.check_ffmpeg", return_value=False):
            with pytest.raises(RuntimeError, match="FFmpeg no está instalado"):
                separate_audio(
                    Path("/fake/input.mp3"),
                    Path("/fake/output"),
                    SeparationMode.TWO_STEMS,
                )

    def test_raises_when_demucs_fails(self):
        with patch("app.separator.check_demucs", return_value=True), \
             patch("app.separator.check_ffmpeg", return_value=True), \
             patch("app.separator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Model not found"
            )
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(RuntimeError, match="Demucs falló"):
                    separate_audio(
                        Path("/fake/input.mp3"),
                        Path(tmpdir) / "output",
                        SeparationMode.TWO_STEMS,
                    )

    def test_five_stems_routes_to_spleeter(self):
        with patch("app.spleeter_separator.separate_audio_spleeter") as mock_spleeter:
            mock_spleeter.return_value = {"vocals": Path("/fake/vocals.wav")}
            result = separate_audio(
                Path("/fake/input.mp3"),
                Path("/fake/output"),
                SeparationMode.FIVE_STEMS,
            )
            mock_spleeter.assert_called_once()
            assert "vocals" in result
