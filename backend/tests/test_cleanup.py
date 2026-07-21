import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import pytest
from unittest.mock import patch, MagicMock
from app import jobs as jobs_module
from app.config import settings
from app.cleanup import cleanup_old_jobs, start_cleanup_service, stop_cleanup_service


@pytest.fixture(autouse=True)
def reset():
    jobs_module._jobs.clear()
    yield
    jobs_module._jobs.clear()


class TestCleanupOldJobs:
    def test_deletes_old_jobs(self):
        job = jobs_module.create_job("old-job", "old.mp3", "dos_pistas", "wav")
        job.created_at = time.time() - (settings.CLEANUP_MAX_AGE_HOURS * 3600 + 100)

        with patch("app.cleanup.delete_job") as mock_delete:
            with patch("app.cleanup.list_all_jobs", return_value={"old-job": job}):
                with patch("app.cleanup.settings.UPLOAD_DIR") as mock_upload_dir:
                    mock_upload_dir.exists.return_value = False
                    with patch("app.cleanup.settings.JOBS_DIR") as mock_jobs_dir:
                        mock_jobs_dir.iterdir.return_value = []
                        import app.cleanup as cleanup_mod
                        original_running = cleanup_mod._cleanup_running
                        cleanup_mod._cleanup_running = False
                        try:
                            cleanup_old_jobs.__wrapped = None
                            jobs_module._jobs["old-job"] = job
                            cleanup_mod._cleanup_running = True
                            call_count = [0]
                            original_sleep = time.sleep
                            def mock_sleep(secs):
                                call_count[0] += 1
                                if call_count[0] >= 1:
                                    cleanup_mod._cleanup_running = False
                            with patch("app.cleanup.time.sleep", side_effect=mock_sleep):
                                cleanup_old_jobs()
                            mock_delete.assert_called_with("old-job")
                        finally:
                            cleanup_mod._cleanup_running = original_running

    def test_keeps_recent_jobs(self):
        job = jobs_module.create_job("new-job", "new.mp3", "dos_pistas", "wav")

        with patch("app.cleanup.delete_job") as mock_delete:
            with patch("app.cleanup.list_all_jobs", return_value={"new-job": job}):
                with patch("app.cleanup.settings.UPLOAD_DIR") as mock_upload_dir:
                    mock_upload_dir.exists.return_value = False
                    with patch("app.cleanup.settings.JOBS_DIR") as mock_jobs_dir:
                        mock_jobs_dir.iterdir.return_value = []
                        import app.cleanup as cleanup_mod
                        original_running = cleanup_mod._cleanup_running
                        cleanup_mod._cleanup_running = False
                        try:
                            jobs_module._jobs["new-job"] = job
                            cleanup_mod._cleanup_running = True
                            call_count = [0]
                            def mock_sleep(secs):
                                call_count[0] += 1
                                if call_count[0] >= 1:
                                    cleanup_mod._cleanup_running = False
                            with patch("app.cleanup.time.sleep", side_effect=mock_sleep):
                                cleanup_old_jobs()
                            mock_delete.assert_not_called()
                        finally:
                            cleanup_mod._cleanup_running = original_running


class TestStartStopCleanupService:
    def test_start_creates_thread(self):
        import app.cleanup as cleanup_mod
        original_running = cleanup_mod._cleanup_running
        original_thread = cleanup_mod._cleanup_thread
        cleanup_mod._cleanup_running = False
        cleanup_mod._cleanup_thread = None
        try:
            start_cleanup_service()
            assert cleanup_mod._cleanup_running is True
            assert cleanup_mod._cleanup_thread is not None
            assert cleanup_mod._cleanup_thread.daemon is True
        finally:
            cleanup_mod._cleanup_running = original_running
            cleanup_mod._cleanup_thread = original_thread

    def test_stop_sets_flag(self):
        import app.cleanup as cleanup_mod
        original_running = cleanup_mod._cleanup_running
        cleanup_mod._cleanup_running = True
        try:
            stop_cleanup_service()
            assert cleanup_mod._cleanup_running is False
        finally:
            cleanup_mod._cleanup_running = original_running

    def test_start_does_not_duplicate(self):
        import app.cleanup as cleanup_mod
        original_running = cleanup_mod._cleanup_running
        existing_thread = MagicMock()
        cleanup_mod._cleanup_running = True
        cleanup_mod._cleanup_thread = existing_thread
        try:
            start_cleanup_service()
            assert cleanup_mod._cleanup_thread is existing_thread
        finally:
            cleanup_mod._cleanup_running = original_running
            cleanup_mod._cleanup_thread = None
