# -*- coding: utf-8 -*-
import os
import json
import threading
from pathlib import Path
import requests

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.core.window import Window

# === ШРИФТ ===
FONT_FILE = 'magistral-bold.ttf'
try:
    LabelBase.register(name='Magistral', fn_regular=FONT_FILE)
    FONT = 'Magistral'
except:
    FONT = 'Roboto'

Window.softinput_mode = 'resize'

# === ПУТИ ===
def get_data_dir():
    try:
        from android.storage import app_storage_path
        return Path(app_storage_path()) / 'claude_data'
    except:
        return Path.home() / '.claude_home'

CONFIG_FILE = get_data_dir() / 'config.json'

# === ИНТЕРФЕЙС ===
KV = '''
<RootWidget>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.1, 0.1, 0.1, 1
        Rectangle:
            pos: self.pos
            size: self.size
    
    Label:
        text: 'Claude Home'
        font_name: app.font
        size_hint_y: None
        height: '50dp'

    ScrollView:
        id: scroll
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: '10dp'
            spacing: '10dp'

    BoxLayout:
        size_hint_y: None
        height: '60dp'
        padding: '5dp'
        spacing: '5dp'
        TextInput:
            id: inp
            font_name: app.font
            hint_text: 'Напишите что-нибудь...'
            multiline: False
            on_text_validate: root.send()
        Button:
            text: '>>'
            size_hint_x: None
            width: '60dp'
            on_release: root.send()

<Msg@Label>:
    font_name: app.font
    size_hint_y: None
    height: self.texture_size[1] + 20
    text_size: self.width - 20, None
    padding: 10, 10
    canvas.before:
        Color:
            rgba: (0.2, 0.3, 0.4, 1) if self.is_ai else (0.3, 0.3, 0.3, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10]
'''

class RootWidget(BoxLayout):
    api_key = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Проверяем ключ через долю секунды после запуска
        Clock.schedule_once(self.check_api_key, 0.5)

    def check_api_key(self, dt):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
            except: pass
        
        if not self.api_key:
            self.show_api_popup()

    def show_api_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text="Введите Anthropic API Key:", font_name=FONT))
        
        key_input = TextInput(hint_text="sk-ant-...", multiline=False, password=True)
        content.add_widget(key_input)
        
        btn = Button(text="Сохранить", size_hint_y=None, height='50dp')
        content.add_widget(btn)
        
        popup = Popup(title="Первый запуск", content=content, size_hint=(0.9, 0.5), auto_dismiss=False)
        
        def save_key(instance):
            key = key_input.text.strip()
            if key.startswith("sk-"):
                get_data_dir().mkdir(parents=True, exist_ok=True)
                with open(CONFIG_FILE, 'w') as f:
                    json.dump({"api_key": key}, f)
                self.api_key = key
                popup.dismiss()

        btn.bind(on_release=save_key)
        popup.open()

    def add_bubble(self, text, is_ai=False):
        from kivy.factory import Factory
        msg = Factory.Msg(text=text)
        msg.is_ai = is_ai
        self.ids.chat_box.add_widget(msg)
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll, 'scroll_y', 0), 0.1)

    def send(self):
        text = self.ids.inp.text.strip()
        if not text or not self.api_key: return
        
        self.add_bubble(text, is_ai=False)
        self.ids.inp.text = ""
        
        # ЗАПУСК В ПОТОКЕ (чтобы не вылетало)
        threading.Thread(target=self._api_thread, args=(text,), daemon=True).start()

    def _api_thread(self, text):
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": "claude-3-5-sonnet-20241022", # Используйте рабочую модель
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": text}]
            }
            r = requests.post("api.anthropic.com", json=payload, headers=headers, timeout=30)
            
            if r.status_code == 200:
                reply = r.json()["content"][0]["text"]
            else:
                reply = f"Ошибка API: {r.status_code}"
        except Exception as e:
            reply = f"Ошибка сети: {str(e)}"
        
        # Возвращаемся в главный поток для отрисовки
        Clock.schedule_once(lambda dt: self.add_bubble(reply, is_ai=True))

class ClaudeApp(App):
    font = StringProperty(FONT)
    def build(self):
        Builder.load_string(KV)
        return RootWidget()

if __name__ == "__main__":
    ClaudeApp().run()
