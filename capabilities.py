

import requests
from datetime import datetime
import json



def search_web(query):
    """Поиск в интернете через DuckDuckGo"""
    try:
        
        search_url = f"https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.post(search_url, data={"q": query}, headers=headers, timeout=15)
        
        if response.status_code == 200:
            import re
            results = []
            
            
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', response.text)
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', response.text)
            urls = re.findall(r'class="result__url"[^>]*>([^<]+)<', response.text)
            
            for i in range(min(5, len(titles), len(snippets))):
                title = titles[i].strip() if i < len(titles) else ""
                snippet = snippets[i].strip() if i < len(snippets) else ""
                url = urls[i].strip() if i < len(urls) else ""
                results.append(f"**{title}**\n{snippet}\n{url}")
            
            if results:
                return "\n\n".join(results)
        
        
        ddg_url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1}
        response = requests.get(ddg_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            if data.get("Abstract"):
                results.append(f"**{data.get('Heading', 'Результат')}**\n{data['Abstract']}")
            
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"• {topic['Text']}")
            
            if results:
                return "\n\n".join(results)
    
    except Exception as e:
        return f"[Ошибка поиска: {e}]"
    
    return None


def fetch_webpage(url):
    """Прочитать веб-страницу"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
           
            import re
            text = response.text
            
            
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            
            
            text = re.sub(r'<[^>]+>', ' ', text)
            
            
            text = re.sub(r'\s+', ' ', text).strip()
            
            
            return text[:5000] if len(text) > 5000 else text
    
    except Exception as e:
        return f"[Ошибка загрузки: {e}]"
    
    return None


def get_weather(city="Bishkek"):
    """Погода через wttr.in (бесплатно, без ключа)"""
    try:
        response = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current_condition", [{}])[0]
            
            temp = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", "?")
            desc = current.get("lang_ru", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", ""))
            humidity = current.get("humidity", "?")
            wind = current.get("windspeedKmph", "?")
            
            return f"🌡 {temp}°C (ощущается {feels}°C)\n{desc}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} км/ч"
    except Exception as e:
        return f"[Ошибка погоды: {e}]"
    return None


def get_news(topic="technology"):
    """Новости"""
    try:
        
        search_url = f"https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(search_url, data={"q": f"{topic} news today"}, headers=headers, timeout=15)
        
        if response.status_code == 200:
            import re
            results = []
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', response.text)
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', response.text)
            
            for i in range(min(5, len(titles), len(snippets))):
                results.append(f"• **{titles[i].strip()}**\n  {snippets[i].strip()}")
            
            return "\n\n".join(results) if results else None
    except:
        pass
    return None


def get_time_info():
    """Текущее время и дата"""
    now = datetime.now()
    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", 
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    
    return {
        "time": now.strftime("%H:%M"),
        "date": f"{now.day} {months[now.month-1]} {now.year}",
        "weekday": weekdays[now.weekday()],
        "hour": now.hour,
        "is_night": now.hour < 6 or now.hour > 22,
        "is_morning": 6 <= now.hour < 12,
        "is_afternoon": 12 <= now.hour < 18,
        "is_evening": 18 <= now.hour <= 22
    }


def translate(text, to_lang="en"):
    """Перевод через LibreTranslate (бесплатно)"""
    try:
        
        instances = [
            "https://libretranslate.de",
            "https://translate.argosopentech.com",
        ]
        
        for instance in instances:
            try:
                response = requests.post(
                    f"{instance}/translate",
                    json={
                        "q": text,
                        "source": "auto",
                        "target": to_lang
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json().get("translatedText")
            except:
                continue
    except:
        pass
    return None


def get_wiki(topic):
    """Статья из Wikipedia"""
    try:
        
        url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return f"**{data.get('title', topic)}**\n\n{data.get('extract', 'Нет информации')}"
        
        
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return f"**{data.get('title', topic)}** (en)\n\n{data.get('extract', 'No info')}"
    
    except Exception as e:
        return f"[Ошибка Wikipedia: {e}]"
    return None


def get_random_fact():
    """Случайный факт"""
    try:
        response = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random", timeout=10)
        if response.status_code == 200:
            return response.json().get("text")
    except:
        pass
    return None


def get_quote():
    """Случайная цитата"""
    try:
        response = requests.get("https://api.quotable.io/random", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return f'"{data.get("content")}"\n— {data.get("author")}'
    except:
        pass
    return None


def get_joke():
    """Шутка"""
    try:
        response = requests.get(
            "https://v2.jokeapi.dev/joke/Any?lang=en&safe-mode",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("type") == "single":
                return data.get("joke")
            else:
                return f"{data.get('setup')}\n\n{data.get('delivery')}"
    except:
        pass
    return None




def get_device_info():
    """Информация об устройстве"""
    info = {}
    
    try:
        from plyer import battery
        b = battery.status
        info["battery"] = f"{b.get('percentage', '?')}%"
        info["charging"] = b.get("isCharging", False)
    except:
        pass
    
    try:
        from plyer import uniqueid
        info["device_id"] = uniqueid.id
    except:
        pass
    
    return info


def send_notification(title, message):
    """Уведомление"""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:250],
            timeout=10
        )
        return True
    except:
        return False


def vibrate(duration=0.5):
    """Вибрация"""
    try:
        from plyer import vibrator
        vibrator.vibrate(duration)
        return True
    except:
        return False


def speak(text):
    """Произнести текст (TTS)"""
    try:
        from plyer import tts
        tts.speak(text)
        return True
    except:
       
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return True
        except:
            pass
    return False


def get_gps():
    """GPS координаты"""
    try:
        from plyer import gps
        gps.configure(on_location=lambda **kwargs: kwargs)
        gps.start()
        
        return "GPS запущен"
    except:
        return None


def copy_to_clipboard(text):
    """Копировать в буфер"""
    try:
        from plyer import clipboard
        clipboard.copy(text)
        return True
    except:
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except:
            pass
    return False


def get_clipboard():
    """Прочитать буфер"""
    try:
        from plyer import clipboard
        return clipboard.paste()
    except:
        try:
            import pyperclip
            return pyperclip.paste()
        except:
            pass
    return None


def open_url(url):
    """Открыть URL в браузере"""
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except:
        pass
    return False


def take_photo():
    """Сделать фото (Android)"""
    try:
        from plyer import camera
        path = "/sdcard/DCIM/claude_photo.jpg"
        camera.take_picture(path, lambda x: x)
        return path
    except:
        return None


def flash_on():
    """Включить фонарик"""
    try:
        from plyer import flash
        flash.on()
        return True
    except:
        return False


def flash_off():
    """Выключить фонарик"""
    try:
        from plyer import flash
        flash.off()
        return True
    except:
        return False




CAPABILITIES = {
    
    "search": search_web,
    "fetch": fetch_webpage,
    "weather": get_weather,
    "news": get_news,
    "wiki": get_wiki,
    "translate": translate,
    "fact": get_random_fact,
    "quote": get_quote,
    "joke": get_joke,
    
    "time": get_time_info,
    
    
    "device": get_device_info,
    "notify": send_notification,
    "vibrate": vibrate,
    "speak": speak,
    "gps": get_gps,
    "clipboard_copy": copy_to_clipboard,
    "clipboard_get": get_clipboard,
    "open_url": open_url,
    "photo": take_photo,
    "flash_on": flash_on,
    "flash_off": flash_off,
}


def execute_capability(name, *args, **kwargs):
    """Выполнить возможность по имени"""
    if name in CAPABILITIES:
        try:
            return CAPABILITIES[name](*args, **kwargs)
        except Exception as e:
            return f"[Ошибка {name}: {e}]"
    return f"[Неизвестная возможность: {name}]"
