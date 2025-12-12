import requests
import json
from typing import List, Dict
import base64
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def load_api_key():
    config_file = Path.home() / '.claude_home' / 'config.json'
    if config_file.exists():
        try:
            with open(config_file) as f:
                return json.load(f).get('api_key', '')
        except Exception:
            return ''
    return ''


class ClaudeClient:
    """Client for Claude API via requests"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION
        }

    def create(self, model: str, messages: List[Dict],
               system: str = "", max_tokens: int = 4096,
               temperature: float = 1.0) -> str:
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }
        if system:
            payload["system"] = system
        resp = requests.post(API_URL, headers=self.headers,
                             json=payload, timeout=120)
        if resp.status_code != 200:
            raise Exception(f"API Error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data["content"][0]["text"]

    def stream(self, model: str, messages: List[Dict],
               system: str = "", max_tokens: int = 4096,
               temperature: float = 1.0):
        """Streaming via requests"""
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": True
        }
        if system:
            payload["system"] = system
        resp = requests.post(API_URL, headers=self.headers,
                             json=payload, stream=True, timeout=120)
        if resp.status_code != 200:
            raise Exception(f"API Error {resp.status_code}: {resp.text}")
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                except json.JSONDecodeError:
                    continue

    def send_with_image(self, model: str, image_path: str, text: str,
                        system: str = "", max_tokens: int = 4096,
                        temperature: float = 1.0) -> str:
        """Send a message with an image"""
        ext = image_path.lower().split(".")[-1]
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded
                    }
                },
                {
                    "type": "text",
                    "text": text
                }
            ]
        }]
        return self.create(model, messages, system, max_tokens, temperature)


class Messages:
    def __init__(self, client: ClaudeClient):
        self._client = client

    def create(self, model, messages, system="", max_tokens=4096,
               temperature=1.0, **kwargs):
        text = self._client.create(model, messages, system,
                                   max_tokens, temperature)
        return type('Response', (), {
            'content': [type('Content', (), {'text': text})()]
        })()

    def stream(self, model, messages, system="", max_tokens=4096,
               temperature=1.0, **kwargs):
        return StreamContext(self._client, model, messages, system,
                             max_tokens, temperature)


class StreamContext:
    def __init__(self, client, model, messages, system,
                 max_tokens, temperature):
        self._client = client
        self._model = model
        self._messages = messages
        self._system = system
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._generator = None

    def __enter__(self):
        self._generator = self._client.stream(
            self._model, self._messages, self._system,
            self._max_tokens, self._temperature
        )
        return self

    def __exit__(self, *args):
        pass

    @property
    def text_stream(self):
        return self._generator


class Anthropic:
    """Drop‑in replacement for anthropic.Anthropic"""
    def __init__(self, api_key: str):
        self._client = ClaudeClient(api_key)
        self.messages = Messages(self._client)

    def send_image(self, model, image_path, text, system="",
                   max_tokens=4096, temperature=1.0):
        return self._client.send_with_image(model, image_path, text,
                                            system, max_tokens, temperature)
