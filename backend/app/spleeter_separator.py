from __future__ import annotations

import gc
import os
from pathlib import Path
from typing import Callable

import numpy as np
import torch

from .models import SeparationMode

SPLATTER_STEMS_2 = ["vocals", "accompaniment"]
SPLATTER_STEMS_4 = ["vocals", "drums", "bass", "other"]
SPLATTER_STEMS_5 = ["vocals", "drums", "bass", "piano", "other"]

PRESET_MAP = {
    SeparationMode.TWO_STEMS: (SPLATTER_STEMS_2, "spleeter:2stems"),
    SeparationMode.FOUR_STEMS: (SPLATTER_STEMS_4, "spleeter:4stems"),
    SeparationMode.FIVE_STEMS: (SPLATTER_STEMS_5, "spleeter:5stems"),
}

MODEL_DIR = Path("/app/models")
SR = 44100
N_FFT = 2048
HOP = 1024
DIM_F = 1024
DIM_T = 8
CHUNK_SIZE = HOP * (2 ** DIM_T - 1)
MARGIN = SR


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


def _stft_torch(x, n_fft=N_FFT, hop_length=HOP):
    window = torch.hann_window(n_fft, periodic=True)
    spec = torch.stft(x, n_fft=n_fft, hop_length=hop_length, window=window, center=True, return_complex=True)
    spec_real = torch.view_as_real(spec)
    return spec_real.permute(0, 3, 1, 2)


def _istft_torch(x, n_fft=N_FFT, hop_length=HOP, length=None):
    c = 4
    x = x.reshape(-1, c // 2, 2, n_fft // 2 + 1, x.shape[-1])
    x = x.permute(0, 2, 3, 4, 1).reshape(-1, 2, n_fft // 2 + 1, x.shape[-1])
    x = x.permute(0, 2, 3, 1)
    x = torch.complex(x[..., 0], x[..., 1])
    window = torch.hann_window(n_fft, periodic=True)
    y = torch.istft(x, n_fft=n_fft, hop_length=hop_length, window=window, center=True)
    if length is not None:
        y = y[..., :length]
    return y


def _process_chunk(model, mix_waves, n_fft=N_FFT, hop=HOP, dim_f=DIM_F, dim_t=DIM_T, denoise=True):
    n_bins = n_fft // 2 + 1
    n = mix_waves.shape[0] // 2
    chunk_size = hop * (dim_t - 1)

    trim = n_fft // 2
    gen_size = chunk_size - 2 * trim
    pad = gen_size - mix_waves.shape[1] % gen_size if mix_waves.shape[1] % gen_size != 0 else 0

    if pad > 0:
        mix_p = torch.cat([
            torch.zeros(2, trim),
            mix_waves,
            torch.zeros(2, pad),
            torch.zeros(2, trim),
        ], dim=1)
    else:
        mix_p = torch.cat([
            torch.zeros(2, trim),
            mix_waves,
            torch.zeros(2, trim),
        ], dim=1)

    mix_chunks = []
    i = 0
    while i < mix_waves.shape[1] + pad:
        mix_chunks.append(mix_p[:, i:i + chunk_size])
        i += gen_size

    mix_tensor = torch.stack(mix_chunks)
    spek = _stft_torch(mix_tensor, n_fft=n_fft, hop_length=hop)

    n_batch = spek.shape[0]
    target_shape = [n_batch, 4, dim_f, dim_t]
    current_shape = list(spek.shape)

    if current_shape[2] > dim_f:
        spek = spek[:, :, :dim_f]
    if current_shape[3] < dim_t:
        spek = torch.nn.functional.pad(spek, (0, dim_t - current_shape[3]))
    elif current_shape[3] > dim_t:
        spek = spek[:, :, :, :dim_t]

    if denoise:
        pred_neg = model.run(None, {"input": -spek.cpu().numpy()})[0]
        pred_pos = model.run(None, {"input": spek.cpu().numpy()})[0]
        spec_pred = torch.from_numpy((-pred_neg * 0.5 + pred_pos * 0.5)).float()
    else:
        pred = model.run(None, {"input": spek.cpu().numpy()})[0]
        spec_pred = torch.from_numpy(pred).float()

    tar_waves = _istft_torch(spec_pred, n_fft=n_fft, hop_length=hop)
    tar_signal = tar_waves[:, :, trim:-trim].transpose(0, 1).reshape(2, -1).numpy()
    tar_signal = tar_signal[:, :-pad] if pad > 0 else tar_signal

    return tar_signal


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

    audio, sr = sf.read(str(input_path), dtype="float32")
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)

    if sr != SR:
        import scipy.signal
        num = int(len(audio) * SR / sr)
        audio = np.stack([
            scipy.signal.resample(audio[:, 0], num),
            scipy.signal.resample(audio[:, 1], num),
        ], axis=-1)

    length = audio.shape[0]
    mix = audio.T.astype(np.float32)

    if progress_callback:
        progress_callback("Separando con modelo MDX-Net...")

    margin_size = min(MARGIN, length)
    counter = -1

    sources_list = []
    for skip in range(0, length, CHUNK_SIZE):
        counter += 1
        s_margin = 0 if counter == 0 else margin_size
        end = min(skip + CHUNK_SIZE + margin_size, length)
        start = skip - s_margin
        segment = mix[:, start:end]

        chunk_sources = _process_chunk(sess, torch.from_numpy(segment))

        if counter == 0:
            sources_list.append(chunk_sources[:, :CHUNK_SIZE])
        elif skip + CHUNK_SIZE >= length:
            sources_list.append(chunk_sources[:, margin_size:])
        else:
            sources_list.append(chunk_sources[:, margin_size:margin_size + CHUNK_SIZE])

        del segment, chunk_sources
        gc.collect()

    vocals_np = np.concatenate(sources_list, axis=1)[:, :length]
    inst_np = mix - vocals_np

    vocals = np.clip(vocals_np.T, -1, 1)
    inst = np.clip(inst_np.T, -1, 1)

    if progress_callback:
        progress_callback("Guardando archivos...")

    v_path = output_dir / "vocals.wav"
    i_path = output_dir / "accompaniment.wav"
    sf.write(str(v_path), vocals, SR)
    sf.write(str(i_path), inst, SR)

    return {"vocals": v_path, "accompaniment": i_path}


def _separate_ffmpeg(input_path, output_dir, expected_stems, progress_callback):
    import subprocess
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
