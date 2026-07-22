from __future__ import annotations

import gc
import os
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np

from .models import SeparationMode

SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_2 = ["vocals", "accompaniment"]

PRESET_MAP = {
    SeparationMode.FIVE_STEMS: (SPLATTER_STEMS_5, "spleeter:5stems"),
    SeparationMode.FOUR_STEMS: (SPLATTER_STEMS_4, "spleeter:4stems"),
    SeparationMode.TWO_STEMS: (SPLATTER_STEMS_2, "spleeter:2stems"),
}

MODEL_DIR = Path("/app/models")
SR = 44100
N_FFT = 2048
HOP = 512
CHUNK_SECONDS = 15


def separate_audio_spleeter(
    input_path: Path,
    output_dir: Path,
    mode: SeparationMode,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    expected_stems, _ = PRESET_MAP[mode]
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == SeparationMode.TWO_STEMS:
        try:
            return _separate_onnx(input_path, output_dir, progress_callback)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[WARNING] ONNX failed: {e}", flush=True)

    return _separate_ffmpeg(input_path, output_dir, expected_stems, progress_callback)


def _load_audio(input_path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    audio, sr = sf.read(str(input_path), dtype="float32")
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)
    if sr != SR:
        import scipy.signal
        num_samples = int(len(audio) * SR / sr)
        audio = np.stack([
            scipy.signal.resample(audio[:, 0], num_samples),
            scipy.signal.resample(audio[:, 1], num_samples),
        ], axis=-1)
        sr = SR
    return audio, sr


def _stft(x):
    window = np.hanning(N_FFT).astype(np.float32)
    n_frames = 1 + (len(x) - N_FFT) // HOP
    frames = np.stack([x[i * HOP : i * HOP + N_FFT] * window for i in range(n_frames)])
    return np.fft.rfft(frames, n=N_FFT).T


def _istft(spec, length=None):
    spec = spec.T
    n_fft2 = (spec.shape[1] - 1) * 2
    window = np.hanning(n_fft2).astype(np.float32)
    total = n_fft2 + HOP * (spec.shape[0] - 1)
    out = np.zeros(total, dtype=np.float32)
    norm = np.zeros(total, dtype=np.float32)
    for i in range(spec.shape[0]):
        frame = np.fft.irfft(spec[i], n=n_fft2)
        s = i * HOP
        out[s : s + n_fft2] += frame * window
        norm[s : s + n_fft2] += window * window
    norm[norm < 1e-8] = 1.0
    out /= norm
    return out[:length] if length else out


def _separate_onnx(input_path: Path, output_dir: Path, progress_callback):
    import onnxruntime as ort
    import soundfile as sf

    model_path = MODEL_DIR / "UVR_MDXNET_KARA.onnx"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    if progress_callback:
        progress_callback("Cargando modelo MDX-Net...")

    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    if progress_callback:
        progress_callback("Leyendo audio...")

    audio, sr = _load_audio(input_path)
    length = audio.shape[0]
    audio_T = audio.T.astype(np.float32)

    chunk_samples = CHUNK_SECONDS * SR
    vocal_l = np.zeros(length, dtype=np.float32)
    vocal_r = np.zeros(length, dtype=np.float32)

    total_chunks = max(1, (length + chunk_samples - 1) // chunk_samples)

    for ci, start in enumerate(range(0, length, chunk_samples)):
        end = min(start + chunk_samples, length)
        seg_l = audio_T[0, start:end]
        seg_r = audio_T[1, start:end]

        spec_l = _stft(seg_l)
        spec_r = _stft(seg_r)
        spec = np.stack([spec_l.real, spec_l.imag, spec_r.real, spec_r.imag], axis=0)

        dim_f, dim_t = spec.shape[1], spec.shape[2]
        pad = (8 - dim_t % 8) % 8
        if pad > 0:
            spec = np.pad(spec, ((0, 0), (0, 0), (0, pad)))
        spec = spec.reshape(1, 4, spec.shape[1], -1, 8).transpose(0, 1, 4, 2, 3).astype(np.float32)

        if progress_callback:
            progress_callback(f"Separando chunk {ci + 1}/{total_chunks}...")

        pred = sess.run(None, {"input": spec})[0]

        pred = pred.transpose(0, 1, 3, 4, 2).reshape(4, dim_f, -1)[:, :, :dim_t]
        vocal_spec_l = pred[0] + 1j * pred[1]
        vocal_spec_r = pred[2] + 1j * pred[3]

        vocal_l[start:end] = _istft(vocal_spec_l, length=end - start)
        vocal_r[start:end] = _istft(vocal_spec_r, length=end - start)

        del spec, pred
        gc.collect()

    vocals = np.stack([vocal_l, vocal_r], axis=-1)
    inst = audio - vocals

    vocals = np.clip(vocals, -1, 1)
    inst = np.clip(inst, -1, 1)

    if progress_callback:
        progress_callback("Guardando archivos...")

    v_path = output_dir / "vocals.wav"
    i_path = output_dir / "accompaniment.wav"
    sf.write(str(v_path), vocals, SR)
    sf.write(str(i_path), inst, SR)

    return {"vocals": v_path, "accompaniment": i_path}


def _separate_ffmpeg(input_path, output_dir, expected_stems, progress_callback):
    stem_files = {}
    vocals = output_dir / "vocals.wav"
    instrumental = output_dir / "accompaniment.wav"

    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", "pan=stereo|c0=c0-c1|c1=c1-c0", "-ar", "44100", str(vocals),
    ], capture_output=True, timeout=600)

    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", "pan=stereo|c0=c0+c1|c1=c0+c1", "-ar", "44100", str(instrumental),
    ], capture_output=True, timeout=600)

    if vocals.exists():
        stem_files["vocals"] = vocals
    if instrumental.exists():
        stem_files["accompaniment"] = instrumental
    return stem_files
