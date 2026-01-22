# -*- coding: utf-8 -*-
"""API клиент для Anthropic"""

import os
import json
import requests

API_URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"

# ---------- SSL FIX ----------
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    SSL_VERIFY = certifi.where()
except Exception:
    SSL_VERIFY = True


class APIError(Exception):
    pass


class AnthropicClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def send(
        self,
        messages,
        system,
        model="claude-3-5-sonnet-20240620",
        max_tokens=512,          # ✅ БЫЛО 4000 → СТАЛО 512
        temperature=1.0,
    ):

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": VERSION,
        }

        payload = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            r = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=180,
                verify=SSL_VERIFY,
            )
        except requests.exceptions.SSLError:
            r = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=180,
                verify=False,
            )

        if r.status_code != 200:
            raise APIError(f"{r.status_code}: {r.text[:200]}")

        data = r.json()
        blocks = data.get("content", [])

        text = ""
        for b in blocks:
            if b.get("type") == "text":
                text += b.get("text", "")

        return text


# --------- ПРОСТОЙ ХЕЛПЕР ДЛЯ main.py ---------

_client = None


def send_message(user_text, history=None, system_prompt=""):
    global _client

    if _client is None:
        from pathlib import Path
        cfg = Path.home() / ".claude_home" / "config.json"
        api_key = json.loads(cfg.read_text()).get("api_key", "")
        _client = AnthropicClient(api_key)

    msgs = history[:] if history else []
    msgs.append({"role": "user", "content": user_text})

    return _client.send(
        messages=msgs,
        system=system_prompt,
    )