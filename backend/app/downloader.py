from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_YT_DLP_PATH: str | None = None


def _find_ytdlp() -> str:
    global _YT_DLP_PATH
    if _YT_DLP_PATH:
        return _YT_DLP_PATH

    import shutil
    path = shutil.which("yt-dlp")
    if path:
        _YT_DLP_PATH = path
        return path

    venv_bin = Path(sys.prefix).resolve() / "bin" / "yt-dlp"
    if venv_bin.exists():
        _YT_DLP_PATH = str(venv_bin)
        return str(venv_bin)

    raise RuntimeError(
        "yt-dlp no está instalado. Instale con: pip install yt-dlp"
    )


def check_ytdlp() -> bool:
    try:
        _find_ytdlp()
        return True
    except RuntimeError:
        return False


def _sanitize_filename_from_title(title: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)
    clean = re.sub(r'_+', '_', clean).strip('_. ')
    if not clean:
        clean = "audio"
    return clean[:200]


def download_audio_from_url(
    url: str,
    output_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    if progress_callback:
        progress_callback("Obteniendo información del video...")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd_info = [
        _find_ytdlp(),
        "--no-download",
        "--print", "%(title)s",
        "--print", "%(duration)s",
        url,
    ]

    try:
        result = subprocess.run(
            cmd_info,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            error = result.stderr.strip() if result.stderr else "Error obteniendo info del video"
            raise RuntimeError(f"No se pudo obtener info del video: {error}")

        lines = result.stdout.strip().split("\n")
        title = lines[0] if lines else "audio"
        duration_str = lines[1] if len(lines) > 1 else "0"
    except subprocess.TimeoutExpired:
        title = "audio"
        duration_str = "0"

    safe_title = _sanitize_filename_from_title(title)

    if progress_callback:
        progress_callback(f"Descargando audio de: {title}")

    output_template = str(output_dir / f"{safe_title}.%(ext)s")

    cmd_download = [
        _find_ytdlp(),
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--no-playlist",
        "--output", output_template,
        url,
    ]

    result = subprocess.run(
        cmd_download,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        error = result.stderr.strip() if result.stderr else "Error desconocido de yt-dlp"
        raise RuntimeError(f"Error al descargar: {error}")

    wav_files = list(output_dir.glob("*.wav"))
    if not wav_files:
        all_files = list(output_dir.glob("*"))
        for f in all_files:
            if f.suffix in (".webm", ".m4a", ".ogg", ".opus", ".mp3"):
                wav_cmd = [
                    "ffmpeg", "-y", "-i", str(f),
                    "-acodec", "pcm_s16le", "-ar", "44100",
                    str(output_dir / f"{safe_title}.wav"),
                ]
                subprocess.run(wav_cmd, capture_output=True, timeout=120)
                wav_files = list(output_dir.glob("*.wav"))
                if wav_files:
                    f.unlink(missing_ok=True)
                break

    if not wav_files:
        raise RuntimeError("No se pudo obtener el archivo de audio del video.")

    audio_path = wav_files[0]
    final_path = output_dir / f"{safe_title}.wav"
    if audio_path != final_path:
        audio_path.rename(final_path)
        audio_path = final_path

    if progress_callback:
        progress_callback("Descarga completada.")

    return audio_path, safe_title
