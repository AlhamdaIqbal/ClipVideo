from __future__ import annotations

import shutil
import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def _vertical_video_filter() -> str:
    width = settings.export_width
    height = settings.export_height
    # Scale so the height fills the target (preserving aspect ratio),
    # then center-crop to the exact target width — no stretching/distortion.
    # This is the standard approach for converting landscape 16:9 → portrait 9:16
    # for TikTok / YouTube Shorts.
    return (
        f"scale=-2:{height},"
        f"crop={width}:{height}:(iw-{width})/2:0,"
        f"setsar=1"
    )


def _encode_args() -> list[str]:
    return [
        "-c:v",
        "libx264",
        "-preset",
        settings.export_video_preset,
        "-crf",
        str(settings.export_video_crf),
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "0",  # use all available CPU cores
        "-c:a",
        "aac",
        "-b:a",
        settings.export_audio_bitrate,
        "-movflags",
        "+faststart",
    ]


def _write_concat_file(clips: list[Path], list_path: Path) -> None:
    list_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for clip in clips:
        path_str = str(clip).replace("'", "'\\''")
        lines.append(f"file '{path_str}'")
    list_path.write_text("\n".join(lines), encoding="utf-8")


def export_clip(
    source_video: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    segments: list | None = None,
    smart_reframe: bool | None = None,
) -> Path:
    from tools.video_effects import generate_srt, track_face_and_reframe

    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec
    if duration <= 0:
        raise ValueError("Durasi clip tidak valid.")

    smart_reframe = settings.export_smart_reframe if smart_reframe is None else smart_reframe
    temp_video = output_path.parent / f"temp_tracked_{output_path.name}"
    reframe_success = False
    temp_srt = output_path.parent / f"sub_{output_path.name}.srt"
    should_burn_subtitles = bool(segments and settings.export_subtitles)

    if should_burn_subtitles:
        if not generate_srt(segments, temp_srt, start_sec, end_sec):
            should_burn_subtitles = False

    # 1. Try Smart Face Tracking
    if smart_reframe:
        try:
            reframe_success = track_face_and_reframe(
                source_video,
                output_path if should_burn_subtitles else temp_video,
                start_sec,
                end_sec,
                srt_path=temp_srt if should_burn_subtitles else None,
            )
        except Exception as err:
            logger.error(f"Gagal melakukan Smart Face Tracking: {err}. Menggunakan fallback Center Crop.")
            reframe_success = False

    if reframe_success and should_burn_subtitles:
        if temp_srt.exists():
            temp_srt.unlink()
        return output_path

    # Fallback to standard vertical Center Crop (single FFmpeg pass — crop + optional subtitle burn)
    if not reframe_success:
        local_srt = None
        try:
            if should_burn_subtitles:
                # Copy SRT to cwd to avoid Windows path escaping issues in FFmpeg
                local_srt = Path.cwd() / f"local_sub_{output_path.name}.srt"
                shutil.copy2(temp_srt, local_srt)
                style = (
                    "Alignment=2,FontName=Impact,FontSize=13,"
                    "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
                    "MarginV=60"
                )
                # Single pass: crop + subtitle burn together
                vf = f"{_vertical_video_filter()},subtitles={local_srt.name}:force_style='{style}'"
                dest = output_path
            else:
                vf = _vertical_video_filter()
                dest = output_path

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(start_sec),
                "-i", str(source_video),
                "-t", str(duration),
                "-vf", vf,
                *_encode_args(),
                str(dest),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg fallback gagal: {result.stderr[-500:]}")
        finally:
            if temp_srt.exists():
                temp_srt.unlink()
            if local_srt and local_srt.exists():
                local_srt.unlink()
            # temp_video is not created in this path, nothing to clean up

    return output_path


def concat_clips(clips: list[Path], output_path: Path) -> Path:
    if not clips:
        raise ValueError("Tidak ada clip untuk digabungkan.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if len(clips) == 1:
        shutil.copy2(clips[0], output_path)
        return output_path

    list_file = output_path.parent / "concat_list.txt"
    _write_concat_file(clips, list_file)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    cmd_encode = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-vf",
        _vertical_video_filter(),
        *_encode_args(),
        str(output_path),
    ]
    result = subprocess.run(cmd_encode, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg gagal saat menggabungkan clip: {result.stderr[-500:]}")

    return output_path
