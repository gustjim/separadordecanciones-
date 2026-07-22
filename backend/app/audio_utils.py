from __future__ import annotations

import json
import os
import subprocess
import shutil
import sys
from pathlib import Path


def _venv_bin_dir() -> Path | None:
    prefix = Path(sys.prefix).resolve()
    bin_dir = prefix / "bin"
    if bin_dir.exists():
        return bin_dir
    return None


def check_ffmpeg() -> bool:
    if shutil.which("ffmpeg"):
        return True
    venv_bin = _venv_bin_dir()
    if venv_bin and (venv_bin / "ffmpeg").exists():
        return True
    return False


def check_demucs() -> bool:
    if shutil.which("demucs"):
        return True
    venv_bin = _venv_bin_dir()
    if venv_bin and (venv_bin / "demucs").exists():
        return True
    for path in [Path("/usr/local/bin/demucs"), Path(sys.prefix) / "bin" / "demucs"]:
        if path.exists():
            return True
    return False


def check_spleeter() -> bool:
    try:
        from spleeter.separator import Separator
        return True
    except ImportError:
        return False


def get_audio_duration(file_path: Path) -> float:
    if not check_ffmpeg():
        return 0.0
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0.0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
    return 0.0


def get_audio_info(file_path: Path) -> dict:
    info = {"duration": 0.0, "format": "", "sample_rate": 0, "channels": 0}
    if not check_ffmpeg():
        return info
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(file_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            info["duration"] = float(fmt.get("duration", 0.0))
            info["format"] = fmt.get("format_name", "")
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    info["sample_rate"] = int(stream.get("sample_rate", 0))
                    info["channels"] = stream.get("channels", 0)
                    break
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
    return info


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "320k") -> bool:
    if not check_ffmpeg():
        return False
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-b:a", bitrate,
                "-q:a", "0",
                str(mp3_path),
            ],
            capture_output=True, text=True, timeout=300,
        )
        return result.returncode == 0 and mp3_path.exists()
    except subprocess.TimeoutExpired:
        return False
