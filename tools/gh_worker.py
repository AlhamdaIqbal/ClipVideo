from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from app.pipeline.download import download_youtube
from app.pipeline.transcribe import get_audio_path, transcribe_audio
from app.pipeline.analyze import find_best_clips, format_timestamp
from app.pipeline.export import export_clip, concat_clips
from tools.telegram_utils import send_message, send_document


def run_job(payload: dict) -> int:
    url = payload.get("url")
    chat_id = payload.get("chat_id")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not url or not chat_id or not bot_token:
        print("Missing payload or TELEGRAM_BOT_TOKEN")
        return 2

    try:
        send_message(bot_token, chat_id, f"Memulai proses auto-clip untuk: {url}")

        work_dir = Path.cwd() / "gh_job"
        if work_dir.exists():
            for p in work_dir.iterdir():
                if p.is_file():
                    p.unlink()
        work_dir.mkdir(parents=True, exist_ok=True)

        download = download_youtube(url, work_dir)
        send_message(bot_token, chat_id, f"Video diunduh: {download.title}")

        audio_path = get_audio_path(download.video_path, work_dir)
        send_message(bot_token, chat_id, "Mulai transkripsi (ini bisa memakan waktu)...")
        segments = transcribe_audio(audio_path)
        send_message(bot_token, chat_id, f"Transkripsi selesai: {len(segments)} segmen")

        send_message(bot_token, chat_id, "Menganalisis dan mencari clip terbaik...")
        clips = find_best_clips(segments)
        if not clips:
            send_message(bot_token, chat_id, "Tidak ditemukan clip yang layak.")
            return 0

        clips_dir = work_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        exported = []
        for i, c in enumerate(clips, start=1):
            out = clips_dir / f"clip_{i}.mp4"
            export_clip(download.video_path, out, c.start_sec, c.end_sec)
            exported.append(out)
            send_message(bot_token, chat_id, f"Clip {i}/{len(clips)} diekspor: {out.name}")

        final_short = clips_dir / "short.mp4"
        try:
            concat_clips(exported, final_short)
            send_message(bot_token, chat_id, "Short final dibuat, mengunggah ke Telegram...")
            send_document(bot_token, chat_id, final_short, caption=f"Short dari {download.title}")
        except Exception:
            send_message(bot_token, chat_id, "Gagal membuat short final, mengunggah clip individu...")
            for f in exported:
                send_document(bot_token, chat_id, f, caption=f.name)

        send_message(bot_token, chat_id, "Selesai.")
        return 0
    except Exception as exc:
        try:
            send_message(bot_token, chat_id, f"Terjadi kesalahan: {exc}")
        except Exception:
            pass
        traceback.print_exc()
        return 3


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--payload-file":
        path = Path(sys.argv[2])
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif len(sys.argv) >= 3 and sys.argv[1] == "--payload":
        payload = json.loads(sys.argv[2])
    else:
        print("Usage: gh_worker.py --payload-file <file.json>  OR --payload '<json>'")
        sys.exit(2)

    sys.exit(run_job(payload))


if __name__ == "__main__":
    main()
