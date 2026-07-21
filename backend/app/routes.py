from __future__ import annotations

import logging
import os
import uuid
import zipfile
import shutil
import threading

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import FileResponse

from .config import settings
from .models import (
    JobStatus, JobResponse, HealthResponse,
    SeparationMode, OutputFormat, TrackInfo,
)
from .jobs import create_job, get_job, delete_job, get_active_job_count, increment_active_jobs, decrement_active_jobs
from .security import (
    sanitize_filename, validate_extension,
    validate_file_size, validate_audio_magic_bytes, is_safe_path,
    validate_media_url,
)
from .audio_utils import (
    check_ffmpeg, check_demucs, check_spleeter,
    get_audio_duration, get_audio_info,
)
from .separator import separate_audio, convert_results
from .downloader import check_ytdlp, download_audio_from_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health_check():
    disk_usage = 0.0
    try:
        usage = os.statvfs(str(settings.BASE_DIR))
        disk_usage = (usage.f_bavail * usage.f_frsize) / (1024 * 1024)
    except (OSError, AttributeError):
        pass

    return HealthResponse(
        status="ok",
        ffmpeg_available=check_ffmpeg(),
        demucs_available=check_demucs(),
        spleeter_available=check_spleeter(),
        python_version=f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        disk_space_mb=round(disk_usage, 1),
        ytdlp_available=check_ytdlp(),
    )


@router.post("/jobs", response_model=JobResponse)
async def create_new_job(
    file: UploadFile = File(...),
    mode: str = Form("dos_pistas"),
    output_format: str = Form("wav"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No se ha proporcionado un archivo.")

    if not validate_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use uno de: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}",
        )

    if get_active_job_count() >= settings.MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail="Demasiados trabajos en proceso. Espere a que termine alguno.",
        )

    safe_name = sanitize_filename(file.filename)
    job_id = str(uuid.uuid4())

    header = await file.read(16)
    if not validate_audio_magic_bytes(header):
        raise HTTPException(
            status_code=400,
            detail="El archivo no parece ser un archivo de audio válido.",
        )
    await file.seek(0)

    job = create_job(job_id, safe_name, mode, output_format)

    input_path = settings.UPLOAD_DIR / f"{job_id}_{safe_name}"

    total_bytes = 0
    try:
        with open(input_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if not validate_file_size(total_bytes):
                    f.close()
                    input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo excede el límite de {settings.MAX_FILE_SIZE_MB} MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {e}")

    job.original_path = input_path

    thread = threading.Thread(
        target=_process_job, args=(job_id,), daemon=True
    )
    thread.start()

    return JobResponse(**job.to_response())


@router.post("/jobs/url", response_model=JobResponse)
async def create_job_from_url(
    url: str = Form(...),
    mode: str = Form("dos_pistas"),
    output_format: str = Form("wav"),
):
    if not validate_media_url(url):
        raise HTTPException(
            status_code=400,
            detail="URL no válida. Use enlaces de YouTube o SoundCloud.",
        )

    if not check_ytdlp():
        raise HTTPException(
            status_code=503,
            detail="yt-dlp no está instalado en el servidor.",
        )

    if get_active_job_count() >= settings.MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail="Demasiados trabajos en proceso. Espere a que termine alguno.",
        )

    job_id = str(uuid.uuid4())
    safe_name = f"url_{job_id[:8]}"
    job = create_job(job_id, safe_name, mode, output_format)

    thread = threading.Thread(
        target=_process_url_job, args=(job_id, url), daemon=True
    )
    thread.start()

    return JobResponse(**job.to_response())


def _process_url_job(job_id: str, url: str):
    from .jobs import update_job_status, set_job_error

    job = get_job(job_id)
    if not job:
        return

    increment_active_jobs()
    try:
        update_job_status(job_id, JobStatus.RECEIVED, "Descargando audio desde la URL...")

        download_dir = job.job_dir / "download"
        download_dir.mkdir(parents=True, exist_ok=True)

        def dl_progress(msg: str):
            update_job_status(job_id, JobStatus.PREPARING, msg)

        audio_path, safe_title = download_audio_from_url(
            url=url,
            output_dir=download_dir,
            progress_callback=dl_progress,
        )

        job.filename = f"{safe_title}.wav"
        job.original_path = audio_path

        update_job_status(job_id, JobStatus.VALIDATING, "Validando audio descargado...")
        audio_info = get_audio_info(job.original_path)
        update_job_status(
            job_id, JobStatus.PREPARING,
            f"Audio detectado: {audio_info['duration']:.1f}s, "
            f"{audio_info['sample_rate']}Hz, {audio_info['channels']} canales"
        )

        engine = "Spleeter" if job.mode == SeparationMode.FIVE_STEMS else "Demucs"
        update_job_status(job_id, JobStatus.SEPARATING, f"Separando pistas con {engine}...")

        raw_output_dir = job.job_dir / "raw"
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        def demucs_progress(msg: str):
            update_job_status(job_id, JobStatus.SEPARATING, msg)

        stem_files = separate_audio(
            input_path=job.original_path,
            output_dir=raw_output_dir,
            mode=job.mode,
            progress_callback=demucs_progress,
        )

        if not stem_files:
            set_job_error(job_id, f"{engine} no generó ninguna pista.")
            return

        final_dir = job.tracks_dir
        final_files = dict(stem_files)

        if job.output_format == OutputFormat.MP3:
            update_job_status(job_id, JobStatus.CONVERTING, "Convirtiendo a MP3...")
            final_files = convert_results(stem_files, final_dir, demucs_progress)
        else:
            for stem_name, src_path in stem_files.items():
                dst = final_dir / src_path.name
                shutil.copy2(src_path, dst)
                final_files[stem_name] = dst

        for stem_name, file_path in final_files.items():
            if not file_path.exists():
                continue
            duration = get_audio_duration(file_path)
            size = file_path.stat().st_size
            track = TrackInfo(
                name=stem_name,
                filename=file_path.name,
                duration_seconds=duration,
                size_bytes=size,
                format=job.output_format.value,
            )
            job.append_track(track)

        update_job_status(job_id, JobStatus.CREATING_ZIP, "Creando archivo ZIP...")
        _create_job_zip(job)

        update_job_status(job_id, JobStatus.COMPLETED, "Proceso completado exitosamente.")

    except Exception as e:
        logger.exception("Error procesando URL job %s", job_id)
        set_job_error(job_id, f"Error durante el procesamiento: {str(e)}")
    finally:
        decrement_active_jobs()


def _process_job(job_id: str):
    from .jobs import get_job, update_job_status, set_job_error

    job = get_job(job_id)
    if not job:
        return

    increment_active_jobs()
    try:
        update_job_status(job_id, JobStatus.VALIDATING, "Validando archivo de audio...")
        if not job.original_path or not job.original_path.exists():
            set_job_error(job_id, "El archivo subido no se encontró.")
            return

        audio_info = get_audio_info(job.original_path)
        update_job_status(
            job_id, JobStatus.PREPARING,
            f"Audio detectado: {audio_info['duration']:.1f}s, "
            f"{audio_info['sample_rate']}Hz, {audio_info['channels']} canales"
        )

        engine = "Spleeter" if job.mode == SeparationMode.FIVE_STEMS else "Demucs"
        update_job_status(job_id, JobStatus.SEPARATING, f"Separando pistas con {engine} (esto puede tardar varios minutos)...")

        raw_output_dir = job.job_dir / "raw"
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        def demucs_progress(msg: str):
            update_job_status(job_id, JobStatus.SEPARATING, msg)

        stem_files = separate_audio(
            input_path=job.original_path,
            output_dir=raw_output_dir,
            mode=job.mode,
            progress_callback=demucs_progress,
        )

        if not stem_files:
            set_job_error(job_id, f"{engine} no generó ninguna pista.")
            return

        final_dir = job.tracks_dir
        final_files = dict(stem_files)

        if job.output_format == OutputFormat.MP3:
            update_job_status(job_id, JobStatus.CONVERTING, "Convirtiendo a MP3...")
            final_files = convert_results(stem_files, final_dir, demucs_progress)
        else:
            for stem_name, src_path in stem_files.items():
                dst = final_dir / src_path.name
                shutil.copy2(src_path, dst)
                final_files[stem_name] = dst

        for stem_name, file_path in final_files.items():
            if not file_path.exists():
                continue
            duration = get_audio_duration(file_path)
            size = file_path.stat().st_size
            track = TrackInfo(
                name=stem_name,
                filename=file_path.name,
                duration_seconds=duration,
                size_bytes=size,
                format=job.output_format.value,
            )
            job.tracks.append(track)

        update_job_status(job_id, JobStatus.CREATING_ZIP, "Creando archivo ZIP...")
        _create_job_zip(job)

        update_job_status(job_id, JobStatus.COMPLETED, "Proceso completado exitosamente.")

    except Exception as e:
        logger.exception("Error procesando job %s", job_id)
        set_job_error(job_id, f"Error durante el procesamiento: {str(e)}")
    finally:
        decrement_active_jobs()


def _create_job_zip(job):
    zip_path = job.job_dir / f"{job.job_id}_tracks.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for track in job.tracks:
                track_file = job.tracks_dir / track.filename
                if track_file.exists():
                    zf.write(track_file, track.filename)
        job._zip_path = zip_path
    except Exception as e:
        logger.error("Error creando ZIP para job %s: %s", job.job_id, e)
        job._zip_path = None


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return JobResponse(**job.to_response())


@router.get("/jobs/{job_id}/tracks")
def get_job_tracks(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return {"tracks": [t.model_dump() for t in job.tracks]}


@router.get("/jobs/{job_id}/tracks/{track_name}")
def download_track(job_id: str, track_name: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")

    for track in job.tracks:
        if track.name == track_name or track.filename == track_name:
            file_path = job.tracks_dir / track.filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Archivo de pista no encontrado.")

            if not is_safe_path(job.tracks_dir, file_path):
                raise HTTPException(status_code=403, detail="Acceso denegado.")

            ext = file_path.suffix
            media_type = "audio/wav" if ext == ".wav" else "audio/mpeg" if ext == ".mp3" else "application/octet-stream"

            return FileResponse(
                path=str(file_path),
                filename=track.filename,
                media_type=media_type,
            )

    raise HTTPException(status_code=404, detail=f"Pista '{track_name}' no encontrada.")


@router.get("/jobs/{job_id}/download-all")
def download_all_tracks(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")

    zip_path = getattr(job, "_zip_path", None)
    if not zip_path or not zip_path.exists():
        raise HTTPException(status_code=404, detail="Archivo ZIP no disponible.")

    if not is_safe_path(job.job_dir, zip_path):
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    safe_stem = sanitize_filename(job.filename.rsplit('.', 1)[0])
    return FileResponse(
        path=str(zip_path),
        filename=f"pistas_{safe_stem}.zip",
        media_type="application/zip",
    )


@router.delete("/jobs/{job_id}")
def remove_job(job_id: str):
    deleted = delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return {"message": "Trabajo eliminado correctamente."}
