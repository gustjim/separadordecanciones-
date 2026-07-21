import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.jobs import create_job, get_job, delete_job, list_all_jobs
from app.config import Settings


@pytest.fixture(autouse=True)
def cleanup():
    from app import jobs as jobs_module
    jobs_module._jobs.clear()
    yield
    jobs_module._jobs.clear()


class TestCreateJob:
    def test_creates_job_with_correct_fields(self):
        job = create_job("test-123", "song.mp3", "dos_pistas", "wav")
        assert job.job_id == "test-123"
        assert job.filename == "song.mp3"
        assert job.mode.value == "dos_pistas"
        assert job.output_format.value == "wav"
        assert job.status.value == "recibido"

    def test_creates_job_four_stems(self):
        job = create_job("test-456", "song.flac", "cuatro_pistas", "mp3")
        assert job.mode.value == "cuatro_pistas"
        assert job.output_format.value == "mp3"

    def test_creates_job_directory(self):
        settings = Settings()
        job_id = "test-dir-create"
        create_job(job_id, "test.mp3", "dos_pistas", "wav")
        job = get_job(job_id)
        assert job.job_dir.exists()
        assert job.tracks_dir.exists()


class TestGetJob:
    def test_get_existing_job(self):
        create_job("test-get", "song.mp3", "dos_pistas", "wav")
        job = get_job("test-get")
        assert job is not None
        assert job.job_id == "test-get"

    def test_get_nonexistent_job(self):
        job = get_job("nonexistent")
        assert job is None


class TestDeleteJob:
    def test_delete_existing(self):
        create_job("test-del", "song.mp3", "dos_pistas", "wav")
        result = delete_job("test-del")
        assert result is True
        assert get_job("test-del") is None

    def test_delete_nonexistent(self):
        result = delete_job("nonexistent")
        assert result is False


class TestListAllJobs:
    def test_list_empty(self):
        assert list_all_jobs() == {}

    def test_list_with_jobs(self):
        create_job("j1", "a.mp3", "dos_pistas", "wav")
        create_job("j2", "b.wav", "cuatro_pistas", "mp3")
        jobs = list_all_jobs()
        assert len(jobs) == 2
        assert "j1" in jobs
        assert "j2" in jobs
