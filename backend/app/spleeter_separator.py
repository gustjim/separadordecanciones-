from __future__ import annotations

from pathlib import Path
from typing import Callable

from .models import SeparationMode


SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_2 = ["vocals", "accompaniment"]

PRESET_MAP = {
    SeparationMode.FIVE_STEMS: ("spleeter:5stems", SPLATTER_STEMS_5),
    SeparationMode.FOUR_STEMS: ("spleeter:4stems", SPLATTER_STEMS_4),
    SeparationMode.TWO_STEMS: ("spleeter:2stems", SPLATTER_STEMS_2),
}


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    from spleeter.separator import Separator

    preset, expected_stems = PRESET_MAP[mode]
    output_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(f"Iniciando separacion con Spleeter ({preset})...")

    separator = Separator(preset)
    separator.separate_to_file(str(input_path), str(output_dir))

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
                stem_files[wav.stem] = wav

    return stem_files
