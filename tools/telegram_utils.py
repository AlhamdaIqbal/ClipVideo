from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import requests

from app.config import settings


def _file_size_mb(file_path: Path) -> float:
    return file_path.stat().st_size / (1024 * 1024)


def _media_duration_sec(file_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return max(0.0, float(result.stdout.strip()))
    except ValueError:
        return 0.0


def _compress_for_telegram(file_path: Path, max_upload_mb: int) -> Path:
    if _file_size_mb(file_path) <= max_upload_mb:
        return file_path

    duration = _media_duration_sec(file_path)
    if duration <= 0:
        return file_path

    max_bytes = max_upload_mb * 1024 * 1024
    total_kbps = int((max_bytes * 8 / duration) / 1000 * 0.9)
    audio_kbps = min(96, max(48, total_kbps // 8))
    video_kbps = max(250, total_kbps - audio_kbps)

    tmp_dir = Path(tempfile.mkdtemp(prefix="clipvideo_telegram_"))
    compressed = tmp_dir / f"{file_path.stem}_telegram.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(file_path),
        "-vf",
        f"scale={settings.telegram_compress_width}:{settings.telegram_compress_height}:force_original_aspect_ratio=decrease,"
        f"pad={settings.telegram_compress_width}:{settings.telegram_compress_height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        f"{video_kbps}k",
        "-maxrate",
        f"{video_kbps}k",
        "-bufsize",
        f"{video_kbps * 2}k",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_kbps}k",
        "-movflags",
        "+faststart",
        str(compressed),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not compressed.exists():
        raise RuntimeError(f"Gagal mengompres video untuk Telegram: {result.stderr[-500:]}")
    if _file_size_mb(compressed) > max_upload_mb:
        raise RuntimeError(
            f"Video masih terlalu besar untuk Telegram setelah kompresi: {_file_size_mb(compressed):.1f} MB"
        )
    return compressed


def send_message(bot_token: str, chat_id: str | int, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def send_document(bot_token: str, chat_id: str | int, file_path: Path, caption: str | None = None) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = requests.post(url, data=data, files=files, timeout=300)
    resp.raise_for_status()
    return resp.json()


def send_video(bot_token: str, chat_id: str | int, file_path: Path, caption: str | None = None) -> dict:
    upload_path = _compress_for_telegram(file_path, settings.telegram_max_upload_mb)
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    with open(upload_path, "rb") as f:
        files = {"video": f}
        data = {"chat_id": chat_id, "supports_streaming": "true"}
        if caption:
            data["caption"] = caption[:1024]
        resp = requests.post(url, data=data, files=files, timeout=300)
    resp.raise_for_status()
    return resp.json()
