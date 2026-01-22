# -*- coding: utf-8 -*-
import os
import json
import base64
import requests
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"

# --- ключ берётся КАК БЫЛ ---
CFG = Path.home() / ".claude_home" / "config.json"
API_KEY = json.loads(CFG.read_text()).get("api_key", "")

HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": VERSION,
    "content-type": "application/json",
}

def _img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def send_message(user_text, history, system_prompt, image_path=None):
    messages = history[:]

    if image_path:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": _img_to_base64(image_path),
                    },
                },
            ],
        })
    else:
        messages.append({"role": "user", "content": user_text})

    payload = {
        "model": "claude-3-5-sonnet-20240620",
        "system": system_prompt,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 1.0,
    }

    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=120)
    data = r.json()

    text = ""
    for b in data.get("content", []):
        if b.get("type") == "text":
            text += b.get("text", "")

    return text