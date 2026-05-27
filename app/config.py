from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    whisper_model: str = "small"
    whisper_device: str = "auto"  # "auto" will select CUDA if available, otherwise CPU
    whisper_compute_type: str = "int8"
    whisper_beam_size: int = 1

    clip_count_target: int = 3
    clip_min_count: int = 3
    clip_min_seconds: float = 45.0
    clip_max_seconds: float = 120.0
    clip_window_step: float = 30.0

    min_hook_score: float = 0.4
    min_conclusion_score: float = 0.4
    embedding_similarity_threshold: float = 0.85

    export_width: int = 1080
    export_height: int = 1920
    export_video_crf: int = 23
    export_video_preset: str = "fast"
    export_audio_bitrate: str = "128k"

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_send_results: bool = False

    job_ttl_hours: int = 24
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()
