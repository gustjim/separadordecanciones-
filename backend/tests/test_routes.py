import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import jobs as jobs_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_jobs():
    jobs_module._jobs.clear()
    jobs_module._active_jobs_count = 0
    yield
    jobs_module._jobs.clear()
    jobs_module._active_jobs_count = 0


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ffmpeg_available" in data
        assert "demucs_available" in data
        assert "python_version" in data
        assert "disk_space_mb" in data


class TestCreateJob:
    def _make_audio_file(self, name="test.mp3"):
        header = b"\xff\xfb\x90\x00" + b"\x00" * 100
        return io.BytesIO(header)

    def test_create_job_with_valid_file(self):
        audio = self._make_audio_file("test.mp3")
        response = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "dos_pistas", "output_format": "wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] in ("recibido", "validando_audio", "preparando_audio")
        assert data["filename"] == "test.mp3"
        assert data["mode"] == "dos_pistas"
        assert data["output_format"] == "wav"

    def test_create_job_with_invalid_extension(self):
        audio = io.BytesIO(b"not an audio file")
        response = client.post(
            "/api/jobs",
            files={"file": ("test.txt", audio, "text/plain")},
            data={"mode": "dos_pistas"},
        )
        assert response.status_code == 400
        assert "Formato no soportado" in response.json()["detail"]

    def test_create_job_with_unsafe_magic_bytes(self):
        audio = io.BytesIO(b"This is definitely not audio content at all")
        response = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "dos_pistas"},
        )
        assert response.status_code == 400
        assert "audio válido" in response.json()["detail"]

    def test_create_job_no_file(self):
        response = client.post("/api/jobs")
        assert response.status_code == 422


class TestGetJobStatus:
    def test_get_nonexistent_job(self):
        response = client.get("/api/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_get_existing_job(self):
        audio = io.BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
        create_resp = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "cuatro_pistas"},
        )
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["mode"] == "cuatro_pistas"


class TestGetJobTracks:
    def test_tracks_nonexistent_job(self):
        response = client.get("/api/jobs/fake/tracks")
        assert response.status_code == 404

    def test_tracks_existing_job(self):
        audio = io.BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
        create_resp = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "dos_pistas"},
        )
        job_id = create_resp.json()["job_id"]
        response = client.get(f"/api/jobs/{job_id}/tracks")
        assert response.status_code == 200
        assert "tracks" in response.json()


class TestDownloadTrack:
    def test_download_nonexistent_track(self):
        response = client.get("/api/jobs/fake/tracks/vocals")
        assert response.status_code == 404

    def test_download_track_job_not_found(self):
        audio = io.BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
        create_resp = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "dos_pistas"},
        )
        job_id = create_resp.json()["job_id"]
        response = client.get(f"/api/jobs/{job_id}/tracks/nonexistent")
        assert response.status_code == 404


class TestDownloadAll:
    def test_download_all_nonexistent(self):
        response = client.get("/api/jobs/fake/download-all")
        assert response.status_code == 404


class TestDeleteJob:
    def test_delete_nonexistent_job(self):
        response = client.delete("/api/jobs/nonexistent")
        assert response.status_code == 404

    def test_delete_existing_job(self):
        audio = io.BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 100)
        create_resp = client.post(
            "/api/jobs",
            files={"file": ("test.mp3", audio, "audio/mpeg")},
            data={"mode": "dos_pistas"},
        )
        job_id = create_resp.json()["job_id"]
        response = client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Trabajo eliminado correctamente."

        get_resp = client.get(f"/api/jobs/{job_id}")
        assert get_resp.status_code == 404
