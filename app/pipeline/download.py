from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yt_dlp


@dataclass
class DownloadResult:
    video_path: Path
    audio_path: Path | None
    title: str
    duration: float | None
    thumbnail_url: str | None


def download_youtube(url: str, output_dir: Path) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    info_path = output_dir / "info.json"

    ydl_opts: dict = {
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "writethumbnail": False,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise ValueError("Tidak dapat mengambil info video.")

    info_path.write_text(json.dumps(info, ensure_ascii=False, default=str), encoding="utf-8")

    video_path = _find_file(output_dir, "source", (".mp4", ".mkv", ".webm"))
    if video_path is None:
        raise FileNotFoundError("File video tidak ditemukan setelah unduhan.")

    title = info.get("title") or "Untitled"
    duration = info.get("duration")
    thumbnail = info.get("thumbnail")

    return DownloadResult(
        video_path=video_path,
        audio_path=None,
        title=title,
        duration=float(duration) if duration else None,
        thumbnail_url=thumbnail,
    )


def _find_file(directory: Path, prefix: str, extensions: tuple[str, ...]) -> Path | None:
    for path in directory.iterdir():
        if path.stem.startswith(prefix) and path.suffix.lower() in extensions:
            return path
    return None
