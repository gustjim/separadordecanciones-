import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.security import (
    sanitize_filename,
    validate_extension,
    validate_mime_type,
    validate_file_size,
    is_safe_path,
    validate_audio_magic_bytes,
    validate_media_url,
)
from app.config import Settings


class TestSanitizeFilename:
    def test_safe_name_unchanged(self):
        assert sanitize_filename("song.mp3") == "song.mp3"

    def test_unsafe_chars_replaced(self):
        result = sanitize_filename('song<>:"/\\|?*.mp3')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_empty_becomes_audio(self):
        assert sanitize_filename("") == "audio"

    def test_dots_only_becomes_audio(self):
        assert sanitize_filename("...") == "audio"

    def test_long_name_truncated(self):
        long_name = "a" * 300 + ".mp3"
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestValidateExtension:
    def test_valid_mp3(self):
        assert validate_extension("song.mp3") is True

    def test_valid_wav(self):
        assert validate_extension("song.wav") is True

    def test_valid_flac(self):
        assert validate_extension("song.flac") is True

    def test_valid_m4a(self):
        assert validate_extension("song.m4a") is True

    def test_valid_ogg(self):
        assert validate_extension("song.ogg") is True

    def test_invalid_txt(self):
        assert validate_extension("file.txt") is False

    def test_invalid_exe(self):
        assert validate_extension("virus.exe") is False

    def test_case_insensitive(self):
        assert validate_extension("song.MP3") is True
        assert validate_extension("song.WAV") is True


class TestValidateMimeType:
    def test_valid_audio_mpeg(self):
        assert validate_mime_type("audio/mpeg") is True

    def test_valid_audio_wav(self):
        assert validate_mime_type("audio/wav") is True

    def test_invalid_text(self):
        assert validate_mime_type("text/plain") is False

    def test_none(self):
        assert validate_mime_type(None) is False


class TestValidateFileSize:
    def test_zero_size(self):
        assert validate_file_size(0) is False

    def test_normal_size(self):
        assert validate_file_size(1024 * 1024) is True

    def test_over_limit(self):
        assert validate_file_size(300 * 1024 * 1024) is False

    def test_exactly_at_limit(self):
        settings = Settings()
        assert validate_file_size(settings.MAX_FILE_SIZE_BYTES) is True


class TestIsSafePath:
    def test_safe_path(self):
        base = Path("/tmp/base")
        target = Path("/tmp/base/file.txt")
        assert is_safe_path(base, target) is True

    def test_unsafe_path_traversal(self):
        base = Path("/tmp/base")
        target = Path("/tmp/base/../../etc/passwd")
        assert is_safe_path(base, target) is False

    def test_unsafe_deep_traversal(self):
        base = Path("/tmp/base")
        target = Path("/tmp/base/sub/../../../etc/shadow")
        assert is_safe_path(base, target) is False


class TestValidateAudioMagicBytes:
    def test_mp3_id3(self):
        assert validate_audio_magic_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00") is True

    def test_mp3_ff_fb(self):
        assert validate_audio_magic_bytes(b"\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00") is True

    def test_wav_riff(self):
        header = b"RIFF\x00\x00\x00\x00WAVEfmt"
        assert validate_audio_magic_bytes(header) is True

    def test_flac(self):
        assert validate_audio_magic_bytes(b"fLaC\x00\x00\x00\x22\x00\x00\x00\x00") is True

    def test_ogg(self):
        assert validate_audio_magic_bytes(b"OggS\x00\x02\x00\x00\x00\x00\x00\x00") is True

    def test_mp4_ftyp(self):
        header = b"\x00\x00\x00\x1cftypisom"
        assert validate_audio_magic_bytes(header) is True

    def test_invalid_text(self):
        assert validate_audio_magic_bytes(b"This is just text") is False

    def test_too_short(self):
        assert validate_audio_magic_bytes(b"RI") is False

    def test_empty(self):
        assert validate_audio_magic_bytes(b"") is False


class TestValidateMediaUrl:
    def test_youtube_standard(self):
        assert validate_media_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_youtube_short(self):
        assert validate_media_url("https://youtu.be/dQw4w9WgXcQ") is True

    def test_youtube_mobile(self):
        assert validate_media_url("https://m.youtube.com/watch?v=abc123") is True

    def test_youtube_music(self):
        assert validate_media_url("https://music.youtube.com/watch?v=abc123") is True

    def test_soundcloud(self):
        assert validate_media_url("https://soundcloud.com/artist/track") is True

    def test_invalid_domain(self):
        assert validate_media_url("https://evil.com/watch?v=abc") is False

    def test_invalid_scheme(self):
        assert validate_media_url("ftp://youtube.com/watch?v=abc") is False

    def test_empty_string(self):
        assert validate_media_url("") is False

    def test_no_scheme(self):
        assert validate_media_url("youtube.com/watch?v=abc") is False

    def test_just_text(self):
        assert validate_media_url("not a url") is False
