from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Settings:
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    UPLOAD_DIR: Path = field(default=None)
    JOBS_DIR: Path = field(default=None)
    MAX_FILE_SIZE_MB: int = 200
    MAX_FILE_SIZE_BYTES: int = 200 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = field(default_factory=lambda: {
        ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"
    })
    ALLOWED_MIME_TYPES: set = field(default_factory=lambda: {
        "audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac",
        "audio/x-flac", "audio/mp4", "audio/m4a", "audio/aac",
        "audio/ogg", "audio/x-m4a", "audio/mp3",
    })
    MAX_CONCURRENT_JOBS: int = 2
    DEMUCS_MODEL: str = "htdemucs"
    DEMUCS_DEVICE: str = "cpu"
    CLEANUP_MAX_AGE_HOURS: int = 2
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    URL_DOWNLOAD_ENABLED: bool = True
    YOUTUBE_ENABLED: bool = True
    SOUNDCLOUD_ENABLED: bool = True

    def __post_init__(self):
        import os
        env_val = os.environ.get("URL_DOWNLOAD_ENABLED", "true").lower()
        self.URL_DOWNLOAD_ENABLED = env_val in ("true", "1", "yes")
        yt_val = os.environ.get("YOUTUBE_ENABLED", "true").lower()
        self.YOUTUBE_ENABLED = yt_val in ("true", "1", "yes")
        sc_val = os.environ.get("SOUNDCLOUD_ENABLED", "true").lower()
        self.SOUNDCLOUD_ENABLED = sc_val in ("true", "1", "yes")
        if self.UPLOAD_DIR is None:
            self.UPLOAD_DIR = self.BASE_DIR / "temp_uploads"
        if self.JOBS_DIR is None:
            self.JOBS_DIR = self.BASE_DIR / "temp_jobs"
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.JOBS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
