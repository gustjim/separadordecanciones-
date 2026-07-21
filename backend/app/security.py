from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from .config import settings


UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

ALLOWED_URL_DOMAINS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "youtu.be", "music.youtube.com",
    "soundcloud.com", "www.soundcloud.com",
}


def sanitize_filename(name: str) -> str:
    clean = UNSAFE_FILENAME_CHARS.sub("_", name)
    clean = clean.strip(". ")
    if not clean:
        clean = "audio"
    if len(clean) > 200:
        clean = clean[:200]
    return clean


def validate_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in settings.ALLOWED_EXTENSIONS


def validate_mime_type(mime_type: str | None) -> bool:
    if mime_type is None:
        return False
    return mime_type in settings.ALLOWED_MIME_TYPES


def validate_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= settings.MAX_FILE_SIZE_BYTES


def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return str(resolved_target).startswith(str(resolved_base))
    except (ValueError, OSError):
        return False


def validate_audio_magic_bytes(header: bytes) -> bool:
    if len(header) < 12:
        return False

    if header[:3] == b"ID3" or header[:2] == b"\xff\xfb" or header[:2] == b"\xff\xf3":
        return True

    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return True

    if header[:4] == b"fLaC":
        return True

    if header[:4] == b"\x1aE\xdf\xa3" or header[4:8] == b"ftyp":
        return True

    if header[:4] == b"OggS":
        return True

    return False


def validate_media_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        return hostname in ALLOWED_URL_DOMAINS
    except (ValueError, TypeError):
        return False
