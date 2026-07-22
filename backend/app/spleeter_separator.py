from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .models import SeparationMode

SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_2 = ["vocals", "accompaniment"]

PRESET_MAP = {
    SeparationMode.FIVE_STEMS: (SPLATTER_STEMS_5, "spleeter:5stems"),
    SeparationMode.FOUR_STEMS: (SPLATTER_STEMS_4, "spleeter:4stems"),
    SeparationMode.TWO_STEMS: (SPLATTER_STEMS_2, "spleeter:2stems"),
}

MODEL_CACHE = Path("/app/.cache/spleeter_models")


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    expected_stems, preset = PRESET_MAP[mode]
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        return _separate_with_spleeter(input_path, output_dir, preset, expected_stems, progress_callback)
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARNING] Spleeter failed: {e}, falling back to ffmpeg", flush=True)

    return _separate_with_ffmpeg(input_path, output_dir, expected_stems, progress_callback)


def _separate_with_spleeter(input_path, output_dir, preset, expected_stems, progress_callback):
    os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
    from spleeter.separator import Separator

    if progress_callback:
        progress_callback("Iniciando separacion con Spleeter...")

    separator = Separator(preset)
    separator.separate_to_file(str(input_path), str(output_dir))

    if progress_callback:
        progress_callback("Separacion completada, organizando archivos...")

    stem_files = {}
    track_name = input_path.stem

    for stem in expected_stems:
        for pattern in [
            output_dir / track_name / f"{stem}.wav",
            output_dir / f"{stem}.wav",
        ]:
            if pattern.exists():
                stem_files[stem] = pattern
                break
        else:
            for candidate in output_dir.rglob(f"{stem}.wav"):
                stem_files[stem] = candidate
                break

    return stem_files


def _separate_with_ffmpeg(input_path, output_dir, expected_stems, progress_callback):
    import subprocess
    import shutil

    if progress_callback:
        progress_callback("Usando separacion basica (ffmpeg)...")

    stem_files = {}

    if "vocals" in expected_stems and "accompaniment" in expected_stems:
        vocals = output_dir / "vocals.wav"
        instrumental = output_dir / "accompaniment.wav"

        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
            "-ar", "44100", str(vocals),
        ], capture_output=True, timeout=600)

        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "pan=stereo|c0=c0+c1|c1=c0+c1",
            "-ar", "44100", str(instrumental),
        ], capture_output=True, timeout=600)

        if vocals.exists():
            stem_files["vocals"] = vocals
        if instrumental.exists():
            stem_files["accompaniment"] = instrumental

    elif "vocals" in expected_stems:
        vocals = output_dir / "vocals.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
            "-ar", "44100", str(vocals),
        ], capture_output=True, timeout=600)
        if vocals.exists():
            stem_files["vocals"] = vocals

        instrumental = output_dir / "instrumental.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "pan=stereo|c0=c0+c1|c1=c0+c1",
            "-ar", "44100", str(instrumental),
        ], capture_output=True, timeout=600)
        if instrumental.exists():
            stem_files["instrumental"] = instrumental
    else:
        for stem in expected_stems:
            out = output_dir / f"{stem}.wav"
            shutil.copy2(str(input_path), str(out))
            stem_files[stem] = out

    return stem_files
