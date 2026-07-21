from __future__ import annotations

import logging
import time
import threading
import shutil
from pathlib import Path

from .config import settings
from .jobs import list_all_jobs, delete_job

logger = logging.getLogger(__name__)

_cleanup_running = False
_cleanup_thread: threading.Thread | None = None


def cleanup_old_jobs():
    while _cleanup_running:
        try:
            now = time.time()
            max_age_seconds = settings.CLEANUP_MAX_AGE_HOURS * 3600
            jobs = list_all_jobs()
            for job_id, job in jobs.items():
                if now - job.created_at > max_age_seconds:
                    logger.info("Limpiando job antiguo: %s", job_id)
                    delete_job(job_id)

            if settings.UPLOAD_DIR.exists():
                for item in settings.UPLOAD_DIR.iterdir():
                    if item.is_file():
                        age = now - item.stat().st_mtime
                        if age > max_age_seconds:
                            logger.info("Eliminando upload huérfano: %s", item.name)
                            item.unlink(missing_ok=True)

            for job_dir in settings.JOBS_DIR.iterdir():
                if job_dir.is_dir():
                    age = now - job_dir.stat().st_mtime
                    if age > max_age_seconds:
                        logger.info("Eliminando directorio de job huérfano: %s", job_dir.name)
                        shutil.rmtree(job_dir, ignore_errors=True)

        except Exception as e:
            logger.warning("Error en limpieza automática: %s", e)

        time.sleep(300)


def start_cleanup_service():
    global _cleanup_running, _cleanup_thread
    if _cleanup_running:
        return
    _cleanup_running = True
    _cleanup_thread = threading.Thread(target=cleanup_old_jobs, daemon=True)
    _cleanup_thread.start()


def stop_cleanup_service():
    global _cleanup_running
    _cleanup_running = False
