from __future__ import annotations

from pathlib import Path
from typing import Callable

from .models import SeparationMode


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    from audio_separator.separator import Separator

    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == SeparationMode.FIVE_STEMS:
        model_name = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
        stems_map = {
            "vocals": "Vocals",
            "drums": "Drums",
            "bass": "Bass",
            "piano": "Piano",
            "other": "Other",
        }
    elif mode == SeparationMode.FOUR_STEMS:
        model_name = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
        stems_map = {
            "vocals": "Vocals",
            "drums": "Drums",
            "bass": "Bass",
            "other": "Other",
        }
    else:
        model_name = "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt"
        stems_map = {
            "vocals": "Vocals",
            "accompaniment": "Instrumental",
        }

    if progress_callback:
        progress_callback("Cargando modelo de separacion...")

    separator = Separator()
    separator.load_model(model_filename=model_name)

    if progress_callback:
        progress_callback("Separando audio...")

    output_files = separator.separate(str(input_path))

    if progress_callback:
        progress_callback("Separacion completada, organizando archivos...")

    stem_files = {}
    for output_file in output_files:
        output_path = Path(output_file)
        if not output_path.exists():
            continue
        filename = output_path.stem.lower()
        for key, label in stems_map.items():
            if label.lower() in filename:
                dest = output_dir / f"{key}.wav"
                import shutil
                shutil.move(str(output_path), str(dest))
                stem_files[key] = dest
                break
        else:
            dest = output_dir / output_path.name
            import shutil
            shutil.move(str(output_path), str(dest))
            stem_files[output_path.stem] = dest

    return stem_files
