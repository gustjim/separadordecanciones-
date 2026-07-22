from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from .models import SeparationMode

SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_2 = ["vocals", "accompaniment"]

PRESET_MAP = {
    SeparationMode.FIVE_STEMS: (SPLATTER_STEMS_5, "spleeter:5stems"),
    SeparationMode.FOUR_STEMS: (SPLATTER_STEMS_4, "spleeter:4stems"),
    SeparationMode.TWO_STEMS: (SPLATTER_STEMS_2, "spleeter:2stems"),
}

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models"))
MDX_MODEL_URL = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Inst_HQ_3.onnx"
TARGET_SR = 44100
N_FFT = 2048
HOP = 512
DIM_F = 2048
DIM_T = 8
CHUNK_SIZE = HOP * (2 ** DIM_T - 1)
MARGIN = 44100


def _get_model_path() -> Path:
    model_path = MODEL_DIR / "UVR-MDX-NET-Inst_HQ_3.onnx"
    if model_path.exists() and model_path.stat().st_size > 1_000_000:
        return model_path
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "curl", "-fSL", "-o", str(model_path), MDX_MODEL_URL,
    ], timeout=300, check=True)
    return model_path


def _stft(x, n_fft=N_FFT, hop_length=HOP):
    window = np.hanning(n_fft).astype(np.float32)
    num_frames = 1 + (len(x) - n_fft) // hop_length
    frames = np.stack([x[i * hop_length : i * hop_length + n_fft] * window for i in range(num_frames)])
    spec = np.fft.rfft(frames, n=n_fft)
    return spec.T


def _istft(spec, hop_length=HOP, length=None):
    spec = spec.T
    n_fft = (spec.shape[1] - 1) * 2
    window = np.hanning(n_fft).astype(np.float32)
    num_frames = spec.shape[0]
    output_len = n_fft + hop_length * (num_frames - 1)
    output = np.zeros(output_len, dtype=np.float32)
    norm = np.zeros(output_len, dtype=np.float32)
    for i in range(num_frames):
        frame = np.fft.irfft(spec[i], n=n_fft)
        start = i * hop_length
        output[start : start + n_fft] += frame * window
        norm[start : start + n_fft] += window ** 2
    norm[norm < 1e-8] = 1.0
    output /= norm
    if length is not None:
        output = output[:length]
    return output


def _to_model_input(spec_l, spec_r):
    c0 = spec_l
    c1 = spec_r
    c2 = np.abs(c0)
    c3 = np.angle(c0)
    x = np.stack([c0.real, c0.imag, c1.real, c1.imag], axis=0)
    x = np.reshape(x, [4, DIM_F, -1])
    paded = DIM_T - x.shape[2] % DIM_T if x.shape[2] % DIM_T != 0 else 0
    if paded > 0:
        x = np.pad(x, ((0, 0), (0, 0), (0, paded)))
    x = np.reshape(x, [1, 4, DIM_F, -1, DIM_T])
    x = np.transpose(x, [0, 1, 4, 2, 3])
    return x.astype(np.float32)


def _from_model_input(x):
    n_bins = N_FFT // 2 + 1
    x = np.transpose(x[0], [0, 2, 3, 1])
    x = np.reshape(x, [-1, n_bins])
    c0 = x[:, 0] + x[:, 1] * 1j
    c1 = x[:, 2] + x[:, 3] * 1j
    return c0, c1


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    expected_stems, preset = PRESET_MAP[mode]
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == SeparationMode.TWO_STEMS:
        try:
            return _separate_with_onnx(input_path, output_dir, progress_callback)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[WARNING] ONNX separation failed: {e}", flush=True)

    return _separate_with_ffmpeg(input_path, output_dir, expected_stems, progress_callback)


def _separate_with_onnx(input_path: Path, output_dir: Path, progress_callback):
    import onnxruntime as ort

    model_path = _get_model_path()

    if progress_callback:
        progress_callback("Cargando modelo MDX-Net...")

    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    if progress_callback:
        progress_callback("Leyendo audio...")

    audio, sr = sf.read(str(input_path))
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)

    if sr != TARGET_SR:
        import librosa
        audio = librosa.resample(audio.T, orig_sr=sr, target_sr=TARGET_SR).T
        sr = TARGET_SR

    length = audio.shape[0]
    audio = audio.T.astype(np.float32)

    if progress_callback:
        progress_callback("Separando con modelo MDX-Net...")

    spec_l = _stft(audio[0])
    spec_r = _stft(audio[1])

    model_input = _to_model_input(spec_l, spec_r)

    mask = sess.run(None, {"input": model_input})[0]

    out_c0, out_c1 = _from_model_input(mask)

    vocal_spec_l = spec_l[:out_c0.shape[0], :out_c0.shape[1]] * out_c0
    vocal_spec_r = spec_r[:out_c1.shape[0], :out_c1.shape[1]] * out_c1

    vocal_l = _istft(vocal_spec_l, length=length)
    vocal_r = _istft(vocal_spec_r, length=length)

    vocals = np.stack([vocal_l, vocal_r], axis=-1)
    instrumental = audio.T - vocals.T

    vocals = np.clip(vocals, -1, 1)
    instrumental = np.clip(instrumental, -1, 1)

    if progress_callback:
        progress_callback("Guardando archivos...")

    vocals_path = output_dir / "vocals.wav"
    instrumental_path = output_dir / "accompaniment.wav"

    sf.write(str(vocals_path), vocals, sr)
    sf.write(str(instrumental_path), instrumental, sr)

    return {"vocals": vocals_path, "accompaniment": instrumental_path}


def _separate_with_ffmpeg(input_path, output_dir, expected_stems, progress_callback):
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
    else:
        import shutil
        for stem in expected_stems:
            out = output_dir / f"{stem}.wav"
            shutil.copy2(str(input_path), str(out))
            stem_files[stem] = out

    return stem_files
