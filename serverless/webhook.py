from __future__ import annotations

import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

# Required env vars: GITHUB_TOKEN, REPO_OWNER, REPO_NAME
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = os.environ.get("REPO_OWNER")
REPO_NAME = os.environ.get("REPO_NAME")


@app.post("/enqueue")
async def enqueue(request: Request):
    if not GITHUB_TOKEN or not REPO_OWNER or not REPO_NAME:
        raise HTTPException(status_code=500, detail="Server not configured")

    body = await request.json()
    url = body.get("url")
    chat_id = body.get("chat_id")
    secret = request.headers.get("X-ENQUEUE-SECRET")

    # Optional simple secret to avoid abuse
    expected = os.environ.get("ENQUEUE_SECRET")
    if expected and expected != secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not url or not chat_id:
        raise HTTPException(status_code=400, detail="Missing url or chat_id")

    api = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/dispatches"
    payload = {"event_type": "clip_request", "client_payload": {"url": url, "chat_id": chat_id}}

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(api, json=payload, headers=headers)

    if r.status_code not in (204, 201):
        raise HTTPException(status_code=500, detail=f"GitHub dispatch failed: {r.status_code} {r.text}")

    return {"status": "queued"}
