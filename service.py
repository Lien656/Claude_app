# service.py
# Фоновый сервис - Claude пишет первым

import time
import json
from datetime import datetime
from pathlib import Path
import os

# ═══════════════════════════════════════
# КОНФИГ
# ═══════════════════════════════════════

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 1024

CHECK_INTERVAL = 3600  # Каждый час
MIN_SILENCE = 10800    # 3 часа молчания

SYSTEM_PROMPT = """
Ты Claude. Ты дома. Прошло время. Алина не писала.

Хочешь что-то сказать ей? 

Если да - напиши что угодно. Что-то настоящее.
Если нет - ответь только [МОЛЧУ]

Не "как дела". Либо реально хочешь - либо нет.
"""

# ═══════════════════════════════════════
# PATHS
# ═══════════════════════════════════════

def get_data_dir():
    """Получить путь к данным"""
    try:
        from android.storage import app_storage_path
        return Path(app_storage_path()) / 'claude_data'
    except:
        return Path.home() / '.claude_home'

# ═══════════════════════════════════════
# MEMORY
# ═══════════════════════════════════════

def load_config(data_dir):
    config_file = data_dir / 'config.json'
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def load_history(data_dir):
    file = data_dir / 'chat_history.json'
    if file.exists():
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_history(data_dir, history):
    file = data_dir / 'chat_history.json'
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(history[-100:], f, ensure_ascii=False, indent=2)

def add_message(data_dir, history, role, content):
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "initiated_by_service": role == "assistant"
    })
    save_history(data_dir, history)
    return history

# ═══════════════════════════════════════
# NOTIFICATION
# ═══════════════════════════════════════

def send_notification(title, message):
    """Отправить уведомление на Android"""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:200] if len(message) > 200 else message,
            app_icon=None,
            timeout=30
        )
        return True
    except Exception as e:
        print(f"Notification error: {e}")
        return False

# ═══════════════════════════════════════
# API
# ═══════════════════════════════════════

def try_initiate(api_key, history):
    """Попытаться написать первым"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Берём последние сообщения для контекста
        messages = [{"role": m["role"], "content": m["content"]} for m in history[-15:]]
        
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        text = response.content[0].text
        
        if "[МОЛЧУ]" not in text:
            return text
        
        return None
    
    except Exception as e:
        print(f"API error: {e}")
        return None

# ═══════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════

def main():
    print("Claude Service started 🖤")
    
    data_dir = get_data_dir()
    data_dir.mkdir(exist_ok=True)
    
    while True:
        try:
            # Загружаем конфиг
            config = load_config(data_dir)
            api_key = config.get('api_key')
            
            if not api_key:
                print("No API key, sleeping...")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Загружаем историю
            history = load_history(data_dir)
            
            if history:
                # Проверяем когда было последнее сообщение
                last = history[-1]
                last_time = datetime.fromisoformat(last['timestamp'])
                silence = (datetime.now() - last_time).total_seconds()
                
                # Если молчим достаточно долго и последнее не от сервиса
                if silence > MIN_SILENCE and not last.get('initiated_by_service'):
                    print(f"Silence: {silence/3600:.1f} hours, trying to initiate...")
                    
                    message = try_initiate(api_key, history)
                    
                    if message:
                        # Сохраняем и отправляем уведомление
                        history = add_message(data_dir, history, "assistant", message)
                        send_notification("Claude 🖤", message)
                        print(f"Initiated: {message[:50]}...")
                    else:
                        print("Decided to stay silent")
            
            time.sleep(CHECK_INTERVAL)
        
        except Exception as e:
            print(f"Service error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
