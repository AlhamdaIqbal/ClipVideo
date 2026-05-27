from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.models.schemas import TranscriptSegment


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )

    segments_iter, _info = model.transcribe(
        str(audio_path),
        beam_size=settings.whisper_beam_size,
        vad_filter=True,
        word_timestamps=False,
    )

    segments: list[TranscriptSegment] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=text,
            )
        )

    return segments


def get_audio_path(video_path: Path, job_dir: Path) -> Path:
    """Use video file directly; faster-whisper accepts common video formats."""
    return video_path
