from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import DATA_DIR, JOBS_DIR, ROOT_DIR, settings
from app.jobs.manager import job_manager, run_in_background
from app.jobs.worker import run_analysis_job
from app.models.schemas import AnalyzeRequest, AnalyzeResponse, JobProgress, JobResult, JobStatus

STATIC_DIR = ROOT_DIR / "static"


def _start_job_cleanup_loop() -> None:
    def run() -> None:
        while True:
            job_manager.cleanup_old_jobs()
            time.sleep(3600)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    _start_job_cleanup_loop()
    yield


app = FastAPI(title="ClipVideo", description="Analisis clip YouTube gratis", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    url = request.url.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="URL harus berupa link YouTube yang valid.")

    job = job_manager.create_job(url)
    run_in_background(lambda: run_analysis_job(job.job_id, url))
    return AnalyzeResponse(job_id=job.job_id)


@app.get("/api/jobs/{job_id}", response_model=JobProgress)
async def get_job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return job_manager.to_progress(job)


@app.get("/api/jobs/{job_id}/result", response_model=JobResult)
async def get_job_result(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    if job.status == JobStatus.ERROR:
        raise HTTPException(status_code=400, detail=job.error or "Job gagal.")
    if job.status != JobStatus.DONE or not job.result:
        raise HTTPException(status_code=202, detail="Job masih berjalan.")
    return job.result


@app.get("/clips/{job_id}/{filename}")
async def serve_clip(job_id: str, filename: str):
    if ".." in job_id or ".." in filename:
        raise HTTPException(status_code=400, detail="Path tidak valid.")
    clip_path = JOBS_DIR / job_id / "clips" / filename
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip tidak ditemukan.")
    return FileResponse(clip_path, media_type="video/mp4")


def main():
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
