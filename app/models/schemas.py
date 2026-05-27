from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    EXPORTING = "exporting"
    DONE = "done"
    ERROR = "error"


class ClipScores(BaseModel):
    hook: float
    conclusion: float
    interest: float
    total: float


class ClipSegment(BaseModel):
    rank: int
    topic: str
    hook_text: str
    conclusion_text: str
    start_sec: float
    end_sec: float
    start_label: str
    end_label: str
    mp4_url: str
    scores: ClipScores


class AnalyzeRequest(BaseModel):
    url: str = Field(..., min_length=10)


class AnalyzeResponse(BaseModel):
    job_id: str


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str = ""
    error: Optional[str] = None


class JobResult(BaseModel):
    job_id: str
    video_title: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_sec: Optional[float] = None
    clips: list[ClipSegment]
    final_short_url: Optional[str] = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
