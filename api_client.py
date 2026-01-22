# -*- coding: utf-8 -*-
import json
import base64
import requests
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"

_client_api_key = None


def _load_api_key():
    """
    Безопасная загрузка ключа.
    НЕ падает на Android, если файла нет.
    """
    global _client_api_key
    if _client_api_key is not None:
        return _client_api_key

    try:
        cfg = Path.home() / ".claude_home" / "config.json"
        if cfg.exists():
            _client_api_key = json.loads(cfg.read_text()).get("api_key", "")
        else:
            _client_api_key = ""
    except Exception:
        _client_api_key = ""

    return _client_api_key


def _img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def send_message(user_text, history, system_prompt, image_path=None):
    api_key = _load_api_key()

    if not api_key:
        return "API ключ не найден. Проверь config.json."

    headers = {
        "x-api-key": api_key,
        "anthropic-version": VERSION,
        "content-type": "application/json",
    }

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

    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        data = r.json()
    except Exception as e:
        return "Ошибка соединения с API"

    text = ""
    for b in data.get("content", []):
        if b.get("type") == "text":
            text += b.get("text", "")

    return text