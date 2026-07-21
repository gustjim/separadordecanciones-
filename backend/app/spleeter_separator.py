from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .models import SeparationMode
from .audio_utils import check_spleeter, check_ffmpeg


def _resolve_spleeter_cmd() -> str:
    path = shutil.which("spleeter")
    if path:
        return path
    prefix = Path(sys.prefix).resolve()
    candidate = prefix / "bin" / "spleeter"
    if candidate.exists():
        return str(candidate)
    return "spleeter"


SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_2 = ["vocals", "accompaniment"]


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    if not check_spleeter():
        raise RuntimeError(
            "Spleeter no esta instalado. Instale Spleeter con: pip install spleeter"
        )
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg no esta instalado. Instale FFmpeg con: brew install ffmpeg"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == SeparationMode.FIVE_STEMS:
        preset = "spleeter:5stems"
        expected_stems = SPLATTER_STEMS_5
    elif mode == SeparationMode.FOUR_STEMS:
        preset = "spleeter:4stems"
        expected_stems = SPLATTER_STEMS_4
    else:
        preset = "spleeter:2stems"
        expected_stems = SPLATTER_STEMS_2

    if progress_callback:
        progress_callback("Iniciando separacion con Spleeter...")

    cmd = [
        _resolve_spleeter_cmd(),
        "separate",
        "-p", preset,
        "-o", str(output_dir),
        str(input_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Error desconocido de Spleeter"
        raise RuntimeError(f"Spleeter fallo: {error_msg}")

    if progress_callback:
        progress_callback("Separacion completada, buscando archivos de resultado...")

    stem_files = {}
    track_name = input_path.stem

    for stem in expected_stems:
        wav_file = output_dir / track_name / f"{stem}.wav"
        if wav_file.exists():
            stem_files[stem] = wav_file
        else:
            wav_file2 = output_dir / f"{stem}.wav"
            if wav_file2.exists():
                stem_files[stem] = wav_file2
            else:
                for candidate in output_dir.rglob(f"{stem}.wav"):
                    stem_files[stem] = candidate
                    break

    if not stem_files:
        all_wavs = list(output_dir.rglob("*.wav"))
        if all_wavs:
            for wav in all_wavs:
                stem_name = wav.stem
                stem_files[stem_name] = wav

    return stem_files
