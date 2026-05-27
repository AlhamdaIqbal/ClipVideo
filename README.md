# ClipVideo

Aplikasi web gratis untuk menganalisis video YouTube panjang, menemukan **3–5 segmen** dengan hook memikat dan kesimpulan jelas, lalu mengekspor **clip MP4** beserta timestamp dan **satu short final**.

Semua pemrosesan berjalan **lokal** (tanpa API AI berbayar):

- **yt-dlp** — unduh video
- **faster-whisper** — transkripsi ber-timestamp
- **Heuristik + embedding lokal** — skor hook, kesimpulan, dan variasi topik
- **ffmpeg** — potong video

## Persyaratan

1. **Python 3.11+**
2. **ffmpeg** di PATH ([unduh untuk Windows](https://www.gyan.dev/ffmpeg/builds/))
3. Koneksi internet (untuk unduh video & model pertama kali)

## Instalasi (Windows)

```bash
cd e:\Aplikasi\ClipVideo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Menjalankan

```bash
.venv\Scripts\activate
python run.py
```

Buka browser: **http://127.0.0.1:8000**

Tempel link YouTube → klik **Analisis** → tunggu progress selesai → preview dan unduh clip.

## Konfigurasi (`.env`)

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `WHISPER_MODEL` | `small` | `base` lebih cepat di CPU lemah; `medium` jika ada GPU |
| `WHISPER_DEVICE` | `cpu` | `cuda` jika NVIDIA + CUDA terpasang |
| `CLIP_COUNT_TARGET` | `5` | Jumlah clip target |
| `CLIP_MIN_SECONDS` | `45` | Durasi minimum clip |
| `CLIP_MAX_SECONDS` | `120` | Durasi maksimum clip |

## Contoh output API

```bash
curl -X POST http://127.0.0.1:8000/api/analyze -H "Content-Type: application/json" -d "{\"url\":\"https://www.youtube.com/watch?v=VIDEO_ID\"}"
```

Response job:

```json
{ "job_id": "abc123def456" }
```

Cek status:

```bash
curl http://127.0.0.1:8000/api/jobs/abc123def456
```

Hasil (setelah `status: done`):

```bash
curl http://127.0.0.1:8000/api/jobs/abc123def456/result
```

Response akan menyertakan daftar clip dan, jika berhasil, `final_short_url` untuk mengunduh satu short MP4 gabungan.

## Catatan

- Video **1 jam** di CPU bisa memakan **15–40 menit** (terutama transkripsi).
- Mengunduh dan memotong video YouTube mungkin melanggar **Terms of Service** YouTube — gunakan untuk keperluan pribadi/edukasi.
- Model Whisper dan embedding diunduh otomatis pada penggunaan pertama.

## Struktur

```
app/
  main.py          # FastAPI + routes
  pipeline/        # download, transcribe, analyze, export
  jobs/            # job manager + worker
static/            # UI web
data/jobs/         # output sementara (diabaikan git)
```

## Deploy untuk Bot Telegram (GitHub Actions + Vercel webhook)

Deploy endpoint webhook ke Vercel agar menerima request `{ "url": "...", "chat_id": "..." }` dan memicu GitHub repository dispatch.

Langkah deploy Vercel:

1. Pastikan file `api/enqueue.js`, `vercel.json`, dan `package.json` ada di repo.
2. Pasang Vercel CLI atau gunakan dashboard Vercel.
3. Di Vercel, atur environment variables:
   - `GITHUB_TOKEN` = GitHub personal access token dengan izin `repo` dan `workflow`
   - `REPO_OWNER` = nama pemilik repo GitHub
   - `REPO_NAME` = nama repo GitHub
   - optional `ENQUEUE_SECRET` = secret header untuk mengamankan webhook
4. Deploy ke Vercel:

```bash
cd e:/Aplikasi/ClipVideo
vercel --prod
```

Endpoint publik akan tersedia pada path `/enqueue`.

Di GitHub repo, tambahkan secret `TELEGRAM_BOT_TOKEN`.

Workflow `.github/workflows/clip.yml` akan men-trigger job saat webhook menerima request. Actions menjalankan pipeline di runner Ubuntu, membuat `short.mp4`, dan mengunggah hasil ke Telegram.

Batasan dan catatan:
- GitHub Actions free tier memiliki kuota dan timeout; cocok untuk penggunaan ringan.
- Actions runner tidak memiliki GPU. Untuk transkripsi cepat, gunakan model `tiny` atau `small`.
- Pastikan `requirements.txt` sudah lengkap; instal di workflow memakan waktu.
- `httpx` sudah ditambahkan ke dependency agar Vercel dapat memanggil GitHub API.

Contoh panggilan test:

```bash
curl -X POST https://your-project.vercel.app/enqueue \
  -H "Content-Type: application/json" \
  -H "X-ENQUEUE-SECRET: your-secret-if-set" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID", "chat_id": "123456789"}'
```

Setelah webhook menerima request, GitHub Actions akan dijalankan dan bot akan mengirimkan progress & hasil ke `chat_id`.

## Menjalankan Bot Telegram

Untuk menghubungkan bot Telegram dengan webhook Vercel:

### 1. Setup Environment Variables

Buat file `.env` atau set environment variables:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
VERCEL_WEBHOOK_URL=https://your-project.vercel.app/enqueue
ENQUEUE_SECRET=your_secret_if_set
```

### 2. Jalankan Bot

```bash
.venv\Scripts\activate
python tools/telegram_bot.py
```

### 3. Cara Kerja

1. User kirim link YouTube ke bot Telegram
2. Bot mengekstrak URL dan memanggil Vercel webhook
3. Vercel webhook trigger GitHub Actions
4. GitHub Actions memproses video dan mengirim hasil ke Telegram

### 4. Commands Bot

- `/start` - Mulai bot dan lihat instruksi
- `/help` - Bantuan penggunaan
- Kirim link YouTube langsung untuk memproses

