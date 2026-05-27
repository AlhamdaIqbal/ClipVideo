from __future__ import annotations

import requests
from pathlib import Path


def send_message(bot_token: str, chat_id: str | int, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})
    resp.raise_for_status()
    return resp.json()


def send_document(bot_token: str, chat_id: str | int, file_path: Path, caption: str | None = None) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = requests.post(url, data=data, files=files)
    resp.raise_for_status()
    return resp.json()
