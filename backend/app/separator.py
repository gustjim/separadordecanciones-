from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .config import settings
from .models import SeparationMode
from .audio_utils import check_ffmpeg, check_demucs, convert_wav_to_mp3

os.environ.setdefault("HF_HOME", "/app/.cache/huggingface")
os.environ.setdefault("TORCH_HOME", "/app/.cache/torch")


def _resolve_demucs_cmd() -> list[str]:
    path = shutil.which("demucs")
    if path:
        return [path]
    prefix = Path(sys.prefix).resolve()
    candidate = prefix / "bin" / "demucs"
    if candidate.exists():
        return [str(candidate)]
    for alt in [Path("/usr/local/bin/demucs"), prefix / "local" / "bin" / "demucs"]:
        if alt.exists():
            return [str(alt)]
    return [sys.executable, "-m", "demucs"]


def separate_audio(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    from .spleeter_separator import separate_audio_spleeter

    demucs_enabled = os.environ.get("DEMUCS_ENABLED", "false").lower() == "true"

    if demucs_enabled and check_demucs() and check_ffmpeg():
        try:
            return _separate_demucs(input_path, output_dir, mode, progress_callback)
        except Exception as e:
            msg = str(e)
            if progress_callback:
                progress_callback(f"Demucs falló ({msg}), usando Spleeter como respaldo...")
            print(f"[WARNING] Demucs failed, falling back to Spleeter: {msg}", flush=True)

    if mode == SeparationMode.FIVE_STEMS:
        if progress_callback:
            progress_callback("Usando Spleeter (5 stems: vocals, drums, bass, piano, other)...")
        return separate_audio_spleeter(
            input_path=input_path,
            output_dir=output_dir,
            mode=mode,
            progress_callback=progress_callback,
        )

    if mode == SeparationMode.TWO_STEMS:
        if progress_callback:
            progress_callback("Usando Spleeter (2 stems: vocals + accompaniment)...")
        return separate_audio_spleeter(input_path, output_dir, mode, progress_callback)

    if mode == SeparationMode.FOUR_STEMS:
        if progress_callback:
            progress_callback("Usando Spleeter (4 stems: vocals, drums, bass, other)...")
        return separate_audio_spleeter(input_path, output_dir, mode, progress_callback)

    raise RuntimeError("No hay motor de separación disponible. Instale Demucs o Spleeter.")


def _separate_demucs(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = _resolve_demucs_cmd() + [
        "-n", settings.DEMUCS_MODEL,
        "-d", settings.DEMUCS_DEVICE,
        "--out", str(output_dir),
        "--filename", "{stem}.{ext}",
    ]

    local_model_dir = Path("/app/models/htdemucs")
    if not local_model_dir.exists():
        local_model_dir = Path(__file__).resolve().parent.parent.parent / "models" / "htdemucs"
    if local_model_dir.exists() and (local_model_dir / "htdemucs.yaml").exists():
        cmd.extend(["--repo", str(local_model_dir.parent)])

    if mode == SeparationMode.TWO_STEMS:
        cmd.extend(["--two-stems", "vocals"])

    cmd.append(str(input_path))

    if progress_callback:
        progress_callback("Iniciando separación con Demucs...")

    env = os.environ.copy()
    env["HF_HOME"] = "/app/.cache/huggingface"
    env["TORCH_HOME"] = "/app/.cache/torch"

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,
        env=env,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Error desconocido de Demucs"
        raise RuntimeError(f"Demucs falló: {error_msg}")

    if progress_callback:
        progress_callback("Separación completada, buscando archivos de resultado...")

    stem_files = {}
    possible_stems_4 = ["vocals", "drums", "bass", "other"]
    possible_stems_2 = ["vocals", "no_vocals"]
    possible_stems = possible_stems_2 if mode == SeparationMode.TWO_STEMS else possible_stems_4

    for stem in possible_stems:
        wav_file = output_dir / f"{stem}.wav"
        if wav_file.exists():
            stem_files[stem] = wav_file
        else:
            for candidate in output_dir.rglob(f"{stem}.wav"):
                stem_files[stem] = candidate
                break

    if not stem_files:
        all_wavs = list(output_dir.rglob("*.wav"))
        if all_wavs:
            for wav in all_wavs:
                stem_files[wav.stem] = wav

    return stem_files


def convert_results(
    stem_files: dict[str, Path],
    output_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    converted = {}
    total = len(stem_files)
    for i, (stem_name, wav_path) in enumerate(stem_files.items()):
        if progress_callback:
            progress_callback(f"Convirtiendo pista {i+1}/{total}: {stem_name}")
        mp3_path = output_dir / f"{stem_name}.mp3"
        if convert_wav_to_mp3(wav_path, mp3_path):
            converted[stem_name] = mp3_path
        else:
            converted[stem_name] = wav_path
    return converted
