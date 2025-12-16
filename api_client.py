# -*- coding: utf-8 -*-
"""API клиент для Anthropic"""

import requests
import json

API_URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"

# SSL fix для Android
try:
    import certifi
    import os
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    SSL_VERIFY = certifi.where()
except:
    SSL_VERIFY = True


class APIError(Exception):
    pass


class Anthropic:
    """Клиент Anthropic API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.messages = Messages(self)
    
    def _request(self, payload):
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": VERSION
        }
        
        try:
            resp = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=180,  # 3 минуты для длинных ответов
                verify=SSL_VERIFY
            )
        except requests.exceptions.SSLError:
            # Fallback без SSL верификации
            resp = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=180,
                verify=False
            )
        
        if resp.status_code != 200:
            try:
                err = resp.json()
                msg = err.get('error', {}).get('message', resp.text[:200])
            except:
                msg = resp.text[:200]
            raise APIError(f"API {resp.status_code}: {msg}")
        
        return resp.json()


class Messages:
    """Интерфейс messages"""
    
    def __init__(self, client):
        self.client = client
    
    def create(self, model, messages, system="", max_tokens=8192, temperature=1.0, **kwargs):
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }
        
        if system:
            payload["system"] = system
        
        data = self.client._request(payload)
        
        # Возвращаем объект с .content[0].text
        return Response(data)


class Response:
    """Ответ API"""
    
    def __init__(self, data):
        self.data = data
        self.content = [Content(c) for c in data.get('content', [])]
        self.model = data.get('model', '')
        self.stop_reason = data.get('stop_reason', '')
        self.usage = data.get('usage', {})


class Content:
    """Контент ответа"""
    
    def __init__(self, data):
        self.type = data.get('type', 'text')
        self.text = data.get('text', '')
