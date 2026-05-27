from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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

    # Try stream copy first (fast)
    cmd_copy = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_sec),
        "-i",
        str(source_video),
        "-t",
        str(duration),
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(output_path),
    ]

    result = subprocess.run(cmd_copy, capture_output=True, text=True)
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    # Fallback: re-encode for browser compatibility
    cmd_encode = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_sec),
        "-i",
        str(source_video),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd_encode, capture_output=True, text=True)
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
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd_encode, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg gagal saat menggabungkan clip: {result.stderr[-500:]}")

    return output_path
