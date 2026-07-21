from __future__ import annotations

import enum
from typing import Optional
from pydantic import BaseModel


class JobStatus(str, enum.Enum):
    RECEIVED = "recibido"
    VALIDATING = "validando_audio"
    PREPARING = "preparando_audio"
    SEPARATING = "separando_pistas"
    CONVERTING = "convirtiendo_resultados"
    CREATING_ZIP = "creando_zip"
    COMPLETED = "completado"
    ERROR = "error"


class SeparationMode(str, enum.Enum):
    TWO_STEMS = "dos_pistas"
    FOUR_STEMS = "cuatro_pistas"
    FIVE_STEMS = "cinco_pistas"


class OutputFormat(str, enum.Enum):
    WAV = "wav"
    MP3 = "mp3"


class JobCreate(BaseModel):
    pass


class TrackInfo(BaseModel):
    name: str
    filename: str
    duration_seconds: float = 0.0
    size_bytes: int = 0
    format: str = "wav"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    filename: str = ""
    mode: SeparationMode = SeparationMode.TWO_STEMS
    output_format: OutputFormat = OutputFormat.WAV
    progress_message: str = ""
    error_message: str = ""
    tracks: list[TrackInfo] = []
    created_at: float = 0.0


class HealthResponse(BaseModel):
    status: str
    ffmpeg_available: bool
    demucs_available: bool
    spleeter_available: bool = False
    url_download_enabled: bool = True
    python_version: str
    disk_space_mb: float = 0.0
    ytdlp_available: bool = False


class ErrorResponse(BaseModel):
    detail: str
