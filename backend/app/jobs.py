from __future__ import annotations

import time
import shutil
import threading
from typing import Optional
from pathlib import Path

from .config import settings
from .models import JobStatus, SeparationMode, OutputFormat, TrackInfo


class Job:
    def __init__(
        self,
        job_id: str,
        filename: str,
        mode: SeparationMode = SeparationMode.TWO_STEMS,
        output_format: OutputFormat = OutputFormat.WAV,
    ):
        self.job_id = job_id
        self.filename = filename
        self.mode = mode
        self.output_format = output_format
        self.status = JobStatus.RECEIVED
        self.progress_message = "Trabajo creado"
        self.error_message = ""
        self.tracks: list[TrackInfo] = []
        self.created_at = time.time()
        self.job_dir: Optional[Path] = None
        self.tracks_dir: Optional[Path] = None
        self.original_path: Optional[Path] = None
        self._attr_lock = threading.Lock()
        self._zip_path: Optional[Path] = None

    def update_status(self, status: JobStatus, message: str = ""):
        with self._attr_lock:
            self.status = status
            if message:
                self.progress_message = message

    def set_error(self, message: str):
        with self._attr_lock:
            self.status = JobStatus.ERROR
            self.error_message = message

    def append_track(self, track: TrackInfo):
        with self._attr_lock:
            self.tracks.append(track)

    def get_snapshot(self) -> dict:
        with self._attr_lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "filename": self.filename,
                "mode": self.mode,
                "output_format": self.output_format,
                "progress_message": self.progress_message,
                "error_message": self.error_message,
                "tracks": list(self.tracks),
                "created_at": self.created_at,
            }

    def to_response(self) -> dict:
        snap = self.get_snapshot()
        return {
            "job_id": snap["job_id"],
            "status": snap["status"].value,
            "filename": snap["filename"],
            "mode": snap["mode"].value,
            "output_format": snap["output_format"].value,
            "progress_message": snap["progress_message"],
            "error_message": snap["error_message"],
            "tracks": [t.dict() for t in snap["tracks"]],
            "created_at": snap["created_at"],
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_active_jobs_count = 0
_active_jobs_lock = threading.Lock()


def create_job(job_id: str, filename: str, mode: str, output_format: str) -> Job:
    if mode == "cinco_pistas":
        sep_mode = SeparationMode.FIVE_STEMS
    elif mode == "cuatro_pistas":
        sep_mode = SeparationMode.FOUR_STEMS
    else:
        sep_mode = SeparationMode.TWO_STEMS
    out_fmt = OutputFormat.MP3 if output_format == "mp3" else OutputFormat.WAV

    job = Job(job_id=job_id, filename=filename, mode=sep_mode, output_format=out_fmt)

    job.job_dir = settings.JOBS_DIR / job_id
    job.job_dir.mkdir(parents=True, exist_ok=True)
    job.tracks_dir = job.job_dir / "tracks"
    job.tracks_dir.mkdir(parents=True, exist_ok=True)

    with _lock:
        _jobs[job_id] = job

    return job


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def update_job_status(job_id: str, status: JobStatus, message: str = ""):
    job = get_job(job_id)
    if job:
        job.update_status(status, message)


def set_job_error(job_id: str, message: str):
    job = get_job(job_id)
    if job:
        job.set_error(message)


def delete_job(job_id: str) -> bool:
    with _lock:
        job = _jobs.pop(job_id, None)
    if job:
        if job.job_dir and job.job_dir.exists():
            shutil.rmtree(job.job_dir, ignore_errors=True)
        return True
    return False


def list_all_jobs() -> dict[str, Job]:
    with _lock:
        return dict(_jobs)


def get_active_job_count() -> int:
    with _active_jobs_lock:
        return _active_jobs_count


def increment_active_jobs():
    global _active_jobs_count
    with _active_jobs_lock:
        _active_jobs_count += 1


def decrement_active_jobs():
    global _active_jobs_count
    with _active_jobs_lock:
        _active_jobs_count = max(0, _active_jobs_count - 1)
