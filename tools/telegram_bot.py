import os
import re
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# Configuration
VERCEL_WEBHOOK_URL = os.environ.get("VERCEL_WEBHOOK_URL")
ENQUEUE_SECRET = os.environ.get("ENQUEUE_SECRET")

# YouTube URL pattern
YOUTUBE_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Halo! Kirimkan link YouTube dan saya akan membuat short video untuk Anda.\n\n'
        'Contoh: https://youtube.com/watch?v=...'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Kirimkan link YouTube dan bot akan:\n'
        '1. Mendownload video\n'
        '2. Mentranskripsi audio\n'
        '3. Menganalisis dan mencari clip terbaik\n'
        '4. Mengirim short video kembali ke Anda\n\n'
        'Proses ini memakan waktu beberapa menit.'
    )


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
    
    # Send to Vercel webhook
    if not VERCEL_WEBHOOK_URL:
        await update.message.reply_text(
            'Server tidak dikonfigurasi dengan benar.'
        )
        return
    
    try:
        await update.message.reply_text(
            f'Menerima link: {url}\n'
            'Memproses... Ini akan memakan waktu beberapa menit.'
        )
        
        # Call Vercel webhook
        headers = {}
        if ENQUEUE_SECRET:
            headers['X-ENQUEUE-SECRET'] = ENQUEUE_SECRET
        
        payload = {
            "url": url,
            "chat_id": chat_id
        }
        
        response = requests.post(
            VERCEL_WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            await update.message.reply_text(
                'Video berhasil di-queue! Anda akan menerima notifikasi saat proses selesai.'
            )
        else:
            await update.message.reply_text(
                f'Gagal memproses: {response.status_code} {response.text}'
            )
            
    except Exception as e:
        await update.message.reply_text(
            f'Terjadi kesalahan: {str(e)}'
        )


def main():
    """Start the bot."""
    # Create the Application
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
    print("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
