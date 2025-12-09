# api_client.py
# Прямые вызовы Claude API через httpx (без anthropic SDK)
# Потому что anthropic SDK не компилируется в APK

import httpx
import json
from typing import Generator, List, Dict, Optional
import base64

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

class ClaudeClient:
    """Клиент для Claude API через httpx"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION
        }
    
    def create(
        self,
        model: str,
        messages: List[Dict],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> str:
        """Обычный запрос (без стриминга)"""
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }
        
        if system:
            payload["system"] = system
        
        with httpx.Client(timeout=120) as client:
            response = client.post(API_URL, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                error = response.json()
                raise Exception(f"API Error {response.status_code}: {error}")
            
            data = response.json()
            return data["content"][0]["text"]
    
    def stream(
        self,
        model: str,
        messages: List[Dict],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> Generator[str, None, None]:
        """Стриминг - возвращает текст по частям"""
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": True
        }
        
        if system:
            payload["system"] = system
        
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", API_URL, headers=self.headers, json=payload) as response:
                if response.status_code != 200:
                    error_text = response.read().decode()
                    raise Exception(f"API Error {response.status_code}: {error_text}")
                
                for line in response.iter_lines():
                    if line.startswith("data: "):
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
    
    def send_with_image(
        self,
        model: str,
        image_path: str,
        text: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> str:
        """Отправка сообщения с картинкой"""
        
        # Определяем тип файла
        ext = image_path.lower().split(".")[-1]
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        
        # Читаем и кодируем
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
        
        return self.create(
            model=model,
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature
        )


# Для совместимости со старым кодом
class Messages:
    def __init__(self, client: ClaudeClient):
        self._client = client
    
    def create(self, model, messages, system="", max_tokens=4096, temperature=1.0, **kwargs):
        text = self._client.create(model, messages, system, max_tokens, temperature)
        # Возвращаем объект похожий на anthropic response
        return type('Response', (), {
            'content': [type('Content', (), {'text': text})()]
        })()
    
    def stream(self, model, messages, system="", max_tokens=4096, temperature=1.0, **kwargs):
        return StreamContext(self._client, model, messages, system, max_tokens, temperature)


class StreamContext:
    """Контекст для стриминга - имитирует anthropic SDK"""
    
    def __init__(self, client, model, messages, system, max_tokens, temperature):
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
    """Drop-in замена для anthropic.Anthropic"""
    
    def __init__(self, api_key: str):
        self._client = ClaudeClient(api_key)
        self.messages = Messages(self._client)
    
    def send_image(self, model, image_path, text, system="", max_tokens=4096, temperature=1.0):
        """Дополнительный метод для отправки картинок"""
        return self._client.send_with_image(model, image_path, text, system, max_tokens, temperature)
