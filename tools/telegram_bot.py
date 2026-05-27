import os
import re
import time
import sys
import shutil
import asyncio
import logging
import requests
from pathlib import Path

# Add project root directory to sys.path to allow importing from the 'app' module
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import pipeline functions
from app.pipeline.download import download_youtube
from app.pipeline.transcribe import get_audio_path, transcribe_audio
from app.pipeline.analyze import find_best_clips
from app.pipeline.export import export_clip, concat_clips

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
VERCEL_WEBHOOK_URL = os.environ.get("VERCEL_WEBHOOK_URL")
ENQUEUE_SECRET = os.environ.get("ENQUEUE_SECRET")
# Set to True to process directly on this machine instead of using Vercel/GitHub actions webhook
USE_LOCAL_PROCESSING = True

# YouTube URL pattern
YOUTUBE_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'
)

# Semaphore to limit CPU-heavy concurrent processing to 1 video at a time
SEMAPHORE = asyncio.Semaphore(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Halo! Kirimkan link YouTube dan saya akan membuat short video untuk Anda secara otomatis.\n\n'
        'Contoh: https://youtube.com/watch?v=...'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Kirimkan link YouTube dan bot akan:\n'
        '1. Mendownload video\n'
        '2. Mentranskripsi audio\n'
        '3. Menganalisis dan mencari klip terbaik\n'
        '4. Mengirim short video kembali ke Anda\n\n'
        'Seluruh file hasil pemrosesan akan langsung dihapus dari server setelah dikirim agar penyimpanan tetap bersih!'
    )


async def process_video_direct(url: str, status_message: Update.message) -> None:
    """Download, analyze, clip, and send video, then completely delete the job folder."""
    chat_id = status_message.chat_id
    timestamp = int(time.time())
    job_dir = Path.cwd() / "data" / "telegram_jobs" / f"{chat_id}_{timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Downloading
        await status_message.edit_text("⏳ [1/5] 📥 Mengunduh video dari YouTube...")
        download = await asyncio.to_thread(download_youtube, url, job_dir)
        
        # Step 2: Transcribing
        await status_message.edit_text(
            f"⏳ [2/5] 🎙️ Mentranskripsi audio (ini memerlukan waktu beberapa menit)...\n"
            f"🎥 Judul: *{download.title}*",
            parse_mode="Markdown"
        )
        audio_path = get_audio_path(download.video_path, job_dir)
        segments = await asyncio.to_thread(transcribe_audio, audio_path)
        
        if not segments:
            await status_message.edit_text("❌ Gagal: Tidak ada suara/audio yang terdeteksi untuk ditranskripsi.")
            return

        # Step 3: Analyzing
        await status_message.edit_text(
            f"⏳ [3/5] 🧠 Menganalisis transkrip untuk mencari klip terbaik...\n"
            f"🎥 Judul: *{download.title}*",
            parse_mode="Markdown"
        )
        clips = await asyncio.to_thread(find_best_clips, segments)
        if not clips:
            await status_message.edit_text("❌ Gagal: Tidak ditemukan bagian video yang layak dijadikan klip.")
            return

        # Step 4: Exporting
        await status_message.edit_text(
            f"⏳ [4/5] 🎬 Mengekspor klip (0/{len(clips)})...\n"
            f"🎥 Judul: *{download.title}*",
            parse_mode="Markdown"
        )
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        exported_clips = []
        for rank, cand in enumerate(clips, start=1):
            out_path = clips_dir / f"clip_{rank}.mp4"
            await status_message.edit_text(
                f"⏳ [4/5] 🎬 Mengekspor klip ({rank}/{len(clips)})...\n"
                f"🎥 Judul: *{download.title}*",
                parse_mode="Markdown"
            )
            await asyncio.to_thread(export_clip, download.video_path, out_path, cand.start_sec, cand.end_sec, segments=segments)
            exported_clips.append(out_path)
            
        # Step 5: Merging and Sending
        await status_message.edit_text(
            f"⏳ [5/5] 🔄 Menggabungkan klip menjadi Short final...\n"
            f"🎥 Judul: *{download.title}*",
            parse_mode="Markdown"
        )
        final_short_path = clips_dir / "short.mp4"
        
        try:
            await asyncio.to_thread(concat_clips, exported_clips, final_short_path)
            await status_message.edit_text(
                f"📤 Mengunggah Short final ke Telegram...\n"
                f"🎥 Judul: *{download.title}*",
                parse_mode="Markdown"
            )
            await status_message.chat.send_action(action="upload_video")
            with open(final_short_path, "rb") as video_file:
                await status_message.chat.send_video(
                    video=video_file,
                    caption=f"🎥 *{download.title}*\n\n✨ Hasil auto-clip video gabungan!",
                    parse_mode="Markdown",
                    write_timeout=300
                )
            await status_message.delete()
        except Exception as merge_err:
            logger.error(f"Gagal menggabungkan klip, mengirimkan klip individu: {merge_err}")
            await status_message.edit_text(
                f"⚠️ Gagal membuat Short gabungan. Mengunggah {len(exported_clips)} klip individu...\n"
                f"🎥 Judul: *{download.title}*",
                parse_mode="Markdown"
            )
            for i, clip_path in enumerate(exported_clips, start=1):
                await status_message.chat.send_action(action="upload_video")
                with open(clip_path, "rb") as video_file:
                    await status_message.chat.send_video(
                        video=video_file,
                        caption=f"🎥 Klip {i} dari {download.title}",
                        write_timeout=300
                    )
            await status_message.edit_text("✅ Seluruh klip individu berhasil dikirim!")
            
    except Exception as e:
        await status_message.edit_text(f"❌ Terjadi kesalahan saat memproses video: {str(e)}")
        logger.exception("Error processing clip direct")
        
    finally:
        # ABSOLUTELY delete all local files for this job to save disk space
        if job_dir.exists():
            try:
                shutil.rmtree(job_dir)
                logger.info(f"Berhasil membersihkan direktori kerja sementara: {job_dir}")
            except Exception as clean_err:
                logger.error(f"Gagal menghapus direktori kerja sementara {job_dir}: {clean_err}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and extract YouTube URLs."""
    text = update.message.text
    
    # Extract YouTube URL
    match = YOUTUBE_PATTERN.search(text)
    if not match:
        await update.message.reply_text(
            'Link tidak valid. Kirimkan link YouTube yang valid.'
        )
        return
    
    url = match.group(0)
    chat_id = update.effective_chat.id
    
    if USE_LOCAL_PROCESSING:
        # Direct local execution mode
        if SEMAPHORE.locked():
            status_message = await update.message.reply_text(
                "⏳ Antrean: Bot sedang memproses video lain. Permintaan Anda berada dalam antrean..."
            )
        else:
            status_message = await update.message.reply_text(
                "⏳ Mempersiapkan pemrosesan video..."
            )
            
        async def run_with_semaphore():
            async with SEMAPHORE:
                await process_video_direct(url, status_message)
                
        # Run background task so event loop is completely free to handle other users
        asyncio.create_task(run_with_semaphore())
        
    else:
        # Webhook delegation mode
        if not VERCEL_WEBHOOK_URL:
            await update.message.reply_text(
                'Server tidak dikonfigurasi dengan benar (VERCEL_WEBHOOK_URL kosong).'
            )
            return
        
        try:
            await update.message.reply_text(
                f'Menerima link: {url}\n'
                'Memproses melalui Webhook... Ini akan memakan waktu beberapa menit.'
            )
            
            headers = {}
            if ENQUEUE_SECRET:
                headers['X-ENQUEUE-SECRET'] = ENQUEUE_SECRET
            
            payload = {
                "url": url,
                "chat_id": chat_id
            }
            
            # Send to webhook in thread to avoid blocking the async event loop
            response = await asyncio.to_thread(
                requests.post,
                VERCEL_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                await update.message.reply_text(
                    'Video berhasil masuk antrean server! Anda akan menerima hasil di sini saat selesai.'
                )
            else:
                await update.message.reply_text(
                    f'Gagal memproses ke webhook: {response.status_code} {response.text}'
                )
                
        except Exception as e:
            await update.message.reply_text(
                f'Terjadi kesalahan: {str(e)}'
            )


def main():
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    application = Application.builder().token(token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("Bot starting polling mode...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
