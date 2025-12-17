# -*- coding: utf-8 -*-
import os
import json
import threading
import base64
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, BooleanProperty
from kivy.core.clipboard import Clipboard
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView

# === ПОДКЛЮЧЕНИЕ ЛИЧНОСТИ ===
try:
    from system_prompt import SYSTEM_PROMPT
except ImportError:
    SYSTEM_PROMPT = "You are a helpful AI assistant."

# === ШРИФТ (Исправляет квадратики) ===
FONT_FILE = 'magistral-bold.ttf'
if os.path.exists(FONT_FILE):
    LabelBase.register(name='Magistral', fn_regular=FONT_FILE)
    FONT_NAME = 'Magistral'
else:
    FONT_NAME = 'Roboto'

# === НАСТРОЙКА КЛАВИАТУРЫ ===
# 'resize' заставляет окно сжиматься, оставляя ввод над клавиатурой
Window.softinput_mode = 'resize'

try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    ANDROID = True
except:
    ANDROID = False

import requests

# === КОНФИГУРАЦИЯ ===
API_URL = "api.anthropic.com"
MODEL = "claude-3-5-sonnet-20241022" 
MAX_TOKENS = 8192
API_KEY = "" # Ключ загрузится из файла
chat_history = []

# --- Логика путей и сохранения (из вашего кода) ---
def get_data_dir():
    if ANDROID:
        return Path(app_storage_path()) / 'claude_data'
    return Path.home() / '.claude_home'

def load_config():
    global API_KEY
    p = get_data_dir() / 'config.json'
    if p.exists():
        try:
            API_KEY = json.load(open(p))['api_key']
        except: pass

def save_config(key):
    global API_KEY
    API_KEY = key
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    json.dump({'api_key': key}, open(d / 'config.json', 'w'))

# === ИНТЕРФЕЙС (KV) ===
KV = '''
<MessageBubble>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10)
    spacing: dp(5)
    canvas.before:
        Color:
            rgba: (0.25, 0.15, 0.15, 1) if self.is_claude else (0.18, 0.18, 0.18, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(15)]

    Label:
        id: lbl
        text: root.text
        font_name: app.font
        font_size: '16sp'
        size_hint_y: None
        height: self.texture_size[1]
        text_size: (self.width - dp(20), None)
        halign: 'left'
        color: (1, 1, 1, 1)

    Button:
        text: 'Копировать'
        font_name: app.font
        size_hint: (None, None)
        size: (dp(100), dp(30))
        background_color: (1, 1, 1, 0.2)
        on_release: root.copy_to_clipboard()

<RootWidget>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.1, 0.1, 0.1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Шапка
    BoxLayout:
        size_hint_y: None
        height: dp(50)
        padding: dp(10)
        Label:
            text: 'Claude Home'
            font_name: app.font
            bold: True
        Button:
            text: 'Вставить'
            font_name: app.font
            size_hint_x: None
            width: dp(90)
            on_release: root.paste_text()

    # Чат
    ScrollView:
        id: scroll
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(12)
            padding: dp(10)

    # Ввод
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(5)
        spacing: dp(5)
        canvas.before:
            Color:
                rgba: 0.15, 0.15, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Button:
            text: '+'
            size_hint_x: None
            width: dp(50)
            on_release: root.show_file_picker()

        TextInput:
            id: inp
            font_name: app.font
            hint_text: 'Напишите что-нибудь...'
            multiline: False
            on_text_validate: root.send()
            background_color: (0.2, 0.2, 0.2, 1)
            foreground_color: (1, 1, 1, 1)

        Button:
            text: '->'
            size_hint_x: None
            width: dp(60)
            on_release: root.send()
'''

class MessageBubble(BoxLayout):
    text = StringProperty('')
    is_claude = BooleanProperty(False)
    
    def copy_to_clipboard(self):
        Clipboard.copy(self.text)

class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        load_config()
        Clock.schedule_once(self._scroll_bottom, 0.5)

    def paste_text(self):
        self.ids.inp.text += Clipboard.paste()

    def _add_msg(self, text, is_claude=False):
        bubble = MessageBubble(text=text, is_claude=is_claude)
        self.ids.chat_box.add_widget(bubble)
        self._scroll_bottom()

    def _scroll_bottom(self, *args):
        self.ids.scroll.scroll_y = 0

    def show_file_picker(self):
        content = BoxLayout(orientation='vertical')
        fc = FileChooserIconView(path='/sdcard' if ANDROID else str(Path.home()))
        btn = Button(text='Выбрать этот файл', size_hint_y=None, height=dp(50))
        content.add_widget(fc)
        content.add_widget(btn)
        
        popup = Popup(title='Выберите файл', content=content, size_hint=(0.95, 0.95))
        btn.bind(on_release=lambda x: self.on_file_selected(fc.selection, popup))
        popup.open()

    def on_file_selected(self, selection, popup):
        if selection:
            path = selection[0]
            filename = os.path.basename(path)
            self.ids.inp.text += f" [Файл: {filename}] "
            # Для фото можно добавить логику чтения в base64 здесь
        popup.dismiss()

    def send(self):
        val = self.ids.inp.text.strip()
        if not val: return
        if not API_KEY: self._ask_key(); return

        self.ids.inp.text = ''
        self._add_msg(val, False)
        chat_history.append({"role": "user", "content": val})
        
        threading.Thread(target=self._query_ai, daemon=True).start()

    def _query_ai(self):
        try:
            # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЛИЧНОСТИ ДЛЯ CLAUDE API
            payload = {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,  # Личность передается здесь!
                "messages": [{"role": m["role"], "content": m["content"]} for m in chat_history[-20:]]
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01"
            }
            
            r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            
            if r.status_code == 200:
                reply = r.json()['content'][0]['text']
            else:
                reply = f"Ошибка API: {r.status_code}\\n{r.text}"
        except Exception as e:
            reply = f"Ошибка: {str(e)}"
            
        Clock.schedule_once(lambda dt: self._on_reply(reply), 0)

    def _on_reply(self, text):
        self._add_msg(text, True)
        chat_history.append({"role": "assistant", "content": text})

    def _ask_key(self):
        # Простейшее окно ввода ключа, если его нет
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        inp = TextInput(hint_text='sk-ant-...', multiline=False, size_hint_y=None, height=dp(50))
        btn = Button(text='Сохранить ключ', size_hint_y=None, height=dp(50))
        box.add_widget(Label(text='Введите ваш Anthropic API Key:'))
        box.add_widget(inp)
        box.add_widget(btn)
        popup = Popup(title='Настройка', content=box, size_hint=(0.8, 0.4))
        btn.bind(on_release=lambda x: [save_config(inp.text), popup.dismiss()])
        popup.open()

class ClaudeApp(App):
    font = StringProperty(FONT_NAME)
    def build(self):
        if ANDROID:
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET])
        Builder.load_string(KV)
        return RootWidget()

if __name__ == '__main__':
    ClaudeApp().run()
