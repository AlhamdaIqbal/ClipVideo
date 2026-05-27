from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import settings


def _vertical_video_filter() -> str:
    width = settings.export_width
    height = settings.export_height
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
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
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec
    if duration <= 0:
        raise ValueError("Durasi clip tidak valid.")

    # Always re-encode so every clip is a browser/Telegram-friendly 9:16 MP4.
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_sec),
        "-i",
        str(source_video),
        "-t",
        str(duration),
        "-vf",
        _vertical_video_filter(),
        *_encode_args(),
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg gagal: {result.stderr[-500:]}")

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
