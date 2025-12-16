# -*- coding: utf-8 -*-
import requests
import json
from typing import List, Dict
import base64
from pathlib import Path

# SSL FIX для Android
try:
    import certifi
    import os
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    SSL_VERIFY = certifi.where()
except:
    SSL_VERIFY = True

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeClient:
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
        
        try:
            resp = requests.post(API_URL, headers=self.headers,
                                json=payload, timeout=120, verify=SSL_VERIFY)
        except:
            # Fallback
            resp = requests.post(API_URL, headers=self.headers,
                                json=payload, timeout=120, verify=False)
        
        if resp.status_code != 200:
            raise Exception(f"API {resp.status_code}: {resp.text[:200]}")
        return resp.json()["content"][0]["text"]

    def stream(self, model: str, messages: List[Dict],
               system: str = "", max_tokens: int = 4096,
               temperature: float = 1.0):
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": True
        }
        if system:
            payload["system"] = system
        
        try:
            resp = requests.post(API_URL, headers=self.headers,
                                json=payload, stream=True, timeout=120, verify=SSL_VERIFY)
        except:
            resp = requests.post(API_URL, headers=self.headers,
                                json=payload, stream=True, timeout=120, verify=False)
        
        if resp.status_code != 200:
            raise Exception(f"API {resp.status_code}: {resp.text[:200]}")
        
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
                except:
                    continue


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


class Anthropic:
    def __init__(self, api_key: str):
        self._client = ClaudeClient(api_key)
        self.messages = Messages(self._client)
