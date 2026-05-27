from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.jobs.manager import job_manager
from app.models.schemas import ClipScores, ClipSegment, JobResult, JobStatus, TranscriptSegment
from app.pipeline.analyze import CandidateClip, find_best_clips, format_timestamp
from app.pipeline.download import download_youtube
from app.pipeline.export import concat_clips, export_clip
from app.pipeline.transcribe import get_audio_path, transcribe_audio
from tools.telegram_utils import send_message, send_video


def run_analysis_job(job_id: str, url: str) -> None:
    try:
        job = job_manager.get_job(job_id)
        if not job or not job.job_dir:
            return

        job_dir = Path(job.job_dir)

        job_manager.update(
            job_id,
            status=JobStatus.DOWNLOADING,
            progress=5,
            message="Mengunduh video dari YouTube...",
        )
        download = download_youtube(url, job_dir)

        job_manager.update(
            job_id,
            status=JobStatus.TRANSCRIBING,
            progress=25,
            message="Mentranskripsi audio (ini bisa memakan waktu)...",
        )
        audio_path = get_audio_path(download.video_path, job_dir)
        segments = transcribe_audio(audio_path)

        transcript_path = job_dir / "transcript.json"
        transcript_path.write_text(
            json.dumps([s.model_dump() for s in segments], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        job_manager.update(
            job_id,
            status=JobStatus.ANALYZING,
            progress=60,
            message="Menganalisis topik dan mencari hook terbaik...",
        )
        clips = find_best_clips(segments)
        if not clips:
            raise ValueError("Tidak ditemukan segmen clip yang memenuhi kriteria.")

        job_manager.update(
            job_id,
            status=JobStatus.EXPORTING,
            progress=75,
            message="Mengekspor file MP4...",
        )

        clips_dir = job_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        clip_results: list[ClipSegment] = []

        exported_clips: list[Path] = []
        for rank, cand in enumerate(clips, start=1):
            out_path = clips_dir / f"clip_{rank}.mp4"
            export_clip(download.video_path, out_path, cand.start_sec, cand.end_sec)
            exported_clips.append(out_path)
            progress = 75 + int(20 * rank / len(clips))
            job_manager.update(
                job_id,
                progress=progress,
                message=f"Mengekspor clip {rank}/{len(clips)}...",
            )
            clip_results.append(_to_clip_segment(job_id, rank, cand))

        final_short_url = None
        if exported_clips:
            job_manager.update(
                job_id,
                progress=95,
                message="Menggabungkan clip menjadi short final...",
            )
            final_short_path = clips_dir / "short.mp4"
            try:
                concat_clips(exported_clips, final_short_path)
                final_short_url = f"/clips/{job_id}/short.mp4"
                _send_telegram_result(final_short_path, download.title)
            except Exception as exc:
                # Jangan hentikan proses jika penggabungan final gagal.
                job_manager.update(
                    job_id,
                    message="Clip diekspor, tetapi short final gagal digabungkan.",
                )
                final_short_url = None

        result = JobResult(
            job_id=job_id,
            video_title=download.title,
            video_url=url,
            thumbnail_url=download.thumbnail_url,
            duration_sec=download.duration,
            clips=clip_results,
            final_short_url=final_short_url,
        )

        result_path = job_dir / "result.json"
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        job_manager.update(
            job_id,
            status=JobStatus.DONE,
            progress=100,
            message="Selesai!",
            result=result,
        )
    except Exception as exc:
        job_manager.update(
            job_id,
            status=JobStatus.ERROR,
            progress=0,
            message="Terjadi kesalahan.",
            error=str(exc),
        )


def _send_telegram_result(video_path: Path, title: str) -> None:
    if not settings.telegram_send_results:
        return
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    try:
        send_video(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            video_path,
            caption=f"Short dari {title}",
        )
    except Exception as exc:
        try:
            send_message(
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                f"Short selesai dibuat, tetapi gagal diunggah ke Telegram: {exc}",
            )
        except Exception:
            pass


def _to_clip_segment(job_id: str, rank: int, cand: CandidateClip) -> ClipSegment:
    return ClipSegment(
        rank=rank,
        topic=cand.topic,
        hook_text=cand.hook_text,
        conclusion_text=cand.conclusion_text,
        start_sec=round(cand.start_sec, 1),
        end_sec=round(cand.end_sec, 1),
        start_label=format_timestamp(cand.start_sec),
        end_label=format_timestamp(cand.end_sec),
        mp4_url=f"/clips/{job_id}/clip_{rank}.mp4",
        scores=ClipScores(
            hook=round(cand.hook_score, 2),
            conclusion=round(cand.conclusion_score, 2),
            interest=round(cand.interest_score, 2),
            total=round(cand.total_score, 2),
        ),
    )
