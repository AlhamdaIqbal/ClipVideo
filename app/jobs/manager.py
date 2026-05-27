from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from app.config import JOBS_DIR, settings
from app.models.schemas import JobProgress, JobResult, JobStatus


@dataclass
class Job:
    job_id: str
    url: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    result: Optional[JobResult] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    job_dir: Optional[str] = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, url: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        job = Job(job_id=job_id, url=url, job_dir=str(job_dir))
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        result: JobResult | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if message is not None:
                job.message = message
            if error is not None:
                job.error = error
            if result is not None:
                job.result = result

    def to_progress(self, job: Job) -> JobProgress:
        return JobProgress(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            error=job.error,
        )

    def cleanup_old_jobs(self) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=settings.job_ttl_hours)
        expired = []

        with self._lock:
            for jid, job in list(self._jobs.items()):
                if job.created_at < cutoff:
                    expired.append(job)
                    del self._jobs[jid]

        for job in expired:
            if job.job_dir:
                job_dir = Path(job.job_dir)
                if job_dir.exists():
                    try:
                        shutil.rmtree(job_dir)
                    except Exception:
                        pass

        if JOBS_DIR.exists():
            for job_dir in JOBS_DIR.iterdir():
                if not job_dir.is_dir():
                    continue
                if job_dir.name in self._jobs:
                    continue
                try:
                    modified = datetime.utcfromtimestamp(job_dir.stat().st_mtime)
                    if modified < cutoff:
                        shutil.rmtree(job_dir)
                except Exception:
                    pass


job_manager = JobManager()


def run_in_background(fn: Callable[[], None]) -> None:
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()
