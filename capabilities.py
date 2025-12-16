# -*- coding: utf-8 -*-
import requests
from datetime import datetime


def search_web(query):
    try:
        search_url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.post(search_url, data={"q": query}, headers=headers, timeout=15)

        if response.status_code == 200:
            import re
            results = []
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', response.text)
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', response.text)

            for i in range(min(5, len(titles), len(snippets))):
                results.append(f"**{titles[i].strip()}**\n{snippets[i].strip()}")

            if results:
                return "\n\n".join(results)
    except Exception as e:
        return f"[Search error: {e}]"
    return None


def fetch_webpage(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            import re
            text = response.text
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:5000]
    except Exception as e:
        return f"[Fetch error: {e}]"
    return None


def get_weather(city="Bishkek"):
    try:
        response = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current_condition", [{}])[0]
            temp = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", "?")
            desc = current.get("weatherDesc", [{}])[0].get("value", "")
            return f"{temp}C (feels {feels}C) {desc}"
    except:
        pass
    return None


def get_time_info():
    now = datetime.now()
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": weekdays[now.weekday()],
        "hour": now.hour
    }


def get_wiki(topic):
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return f"**{data.get('title', topic)}**\n\n{data.get('extract', 'No info')}"
    except:
        pass
    return None


def send_notification(title, message):
    try:
        from plyer import notification
        notification.notify(title=title, message=message[:250], timeout=10)
        return True
    except:
        return False


def vibrate(duration=0.5):
    try:
        from plyer import vibrator
        vibrator.vibrate(duration)
        return True
    except:
        return False


def copy_to_clipboard(text):
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(text)
        return True
    except:
        pass
    return False


def get_clipboard():
    try:
        from kivy.core.clipboard import Clipboard
        return Clipboard.paste()
    except:
        pass
    return None


CAPABILITIES = {
    "search": search_web,
    "fetch": fetch_webpage,
    "weather": get_weather,
    "wiki": get_wiki,
    "time": get_time_info,
    "notify": send_notification,
    "vibrate": vibrate,
    "clipboard_copy": copy_to_clipboard,
    "clipboard_get": get_clipboard,
}


def execute_capability(name, *args, **kwargs):
    if name in CAPABILITIES:
        try:
            return CAPABILITIES[name](*args, **kwargs)
        except Exception as e:
            return f"[Error {name}: {e}]"
    return f"[Unknown: {name}]"
