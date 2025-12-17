# -*- coding: utf-8 -*-
import os
import json
import threading
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty

# === ШРИФТ ===
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT = 'Magistral'
except:
    FONT = 'Roboto'

# === КЛАВИАТУРА ===
Window.softinput_mode = 'pan'

try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    ANDROID = True
except:
    ANDROID = False

try:
    import requests
except:
    requests = None

# === CONFIG ===
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8192
API_KEY = ""
chat_history = []

def get_data_dir():
    if ANDROID:
        try:
            return Path(app_storage_path()) / 'claude_data'
        except:
            pass
    return Path.home() / '.claude_home'

def load_api_key():
    global API_KEY
    for p in [get_data_dir() / 'config.json', Path('/sdcard/Claude/config.json')]:
        if p.exists():
            try:
                API_KEY = json.load(open(p))['api_key']
                return
            except:
                pass

def save_api_key(key):
    global API_KEY
    API_KEY = key
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    json.dump({'api_key': key}, open(d / 'config.json', 'w'))

def load_history():
    global chat_history
    f = get_data_dir() / 'chat_history.json'
    if f.exists():
        try:
            chat_history = json.load(open(f))
        except:
            pass

def save_history():
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    json.dump(chat_history[-200:], open(d / 'chat_history.json', 'w'), ensure_ascii=False)

load_api_key()

# === UI ===
KV = '''
<RootWidget>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.11, 0.11, 0.11, 1
        Rectangle:
            pos: self.pos
            size: self.size
    
    # Header
    Label:
        text: 'Claude Home'
        font_name: app.font
        font_size: sp(20)
        size_hint_y: None
        height: dp(50)
        color: 0.9, 0.85, 0.8, 1
    
    # Chat
    ScrollView:
        id: scroll
        do_scroll_x: False
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(8)
            padding: dp(10)
    
    # Input
    BoxLayout:
        size_hint_y: None
        height: dp(56)
        spacing: dp(8)
        padding: dp(8)
        canvas.before:
            Color:
                rgba: 0.15, 0.15, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size
        
        TextInput:
            id: inp
            font_name: app.font
            font_size: sp(16)
            hint_text: '...'
            multiline: False
            background_color: 0.2, 0.2, 0.2, 1
            foreground_color: 0.9, 0.85, 0.8, 1
            cursor_color: 1, 1, 1, 1
            padding: dp(12)
            on_text_validate: root.send()
        
        Button:
            text: '>'
            font_name: app.font
            font_size: sp(24)
            size_hint_x: None
            width: dp(55)
            background_color: 0.4, 0.1, 0.1, 1
            color: 1, 1, 1, 1
            on_release: root.send()
'''

class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        load_history()
        Clock.schedule_once(self._load_msgs, 0.1)
    
    def _load_msgs(self, dt):
        for m in chat_history[-50:]:
            self._add_bubble(m['content'], m['role'] == 'assistant')
        self._scroll()
    
    def _add_bubble(self, text, is_claude=False):
        from kivy.graphics import Color, RoundedRectangle
        
        box = BoxLayout(size_hint_y=None, padding=12)
        box.bind(minimum_height=box.setter('height'))
        
        bg = (0.25, 0.1, 0.1, 1) if is_claude else (0.18, 0.18, 0.18, 1)
        with box.canvas.before:
            Color(*bg)
            r = RoundedRectangle(pos=box.pos, size=box.size, radius=[12])
        box.bind(pos=lambda w, p: setattr(r, 'pos', p), size=lambda w, s: setattr(r, 'size', s))
        
        lbl = Label(
            text=text,
            font_name=App.get_running_app().font,
            font_size='16sp',
            color=(0.9, 0.85, 0.8, 1),
            text_size=(Window.width - 70, None),
            size_hint_y=None,
            halign='left',
            valign='top',
            padding=(10, 10)
        )
        lbl.bind(texture_size=lambda w, s: setattr(w, 'height', s[1] + 20))
        box.add_widget(lbl)
        
        self.ids.chat_box.add_widget(box)
    
    def _scroll(self):
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll, 'scroll_y', 0), 0.1)
    
    def send(self):
        text = self.ids.inp.text.strip()
        if not text:
            return
        
        if not API_KEY:
            self._api_popup()
            return
        
        self.ids.inp.text = ''
        self._add_bubble(text, False)
        chat_history.append({"role": "user", "content": text})
        save_history()
        self._scroll()
        
        threading.Thread(target=self._call_api, args=(text,), daemon=True).start()
    
    def _call_api(self, text):
        try:
            msgs = [{"role": m["role"], "content": m["content"]} for m in chat_history[-30:]]
            
            r = requests.post(
                API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01"
                },
                json={"model": MODEL, "max_tokens": MAX_TOKENS, "messages": msgs},
                timeout=120
            )
            
            if r.status_code == 200:
                reply = r.json()['content'][0]['text']
            else:
                reply = f"Error: {r.status_code}"
            
            Clock.schedule_once(lambda dt: self._on_reply(reply), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._on_reply(f"Error: {e}"), 0)
    
    def _on_reply(self, text):
        self._add_bubble(text, True)
        chat_history.append({"role": "assistant", "content": text})
        save_history()
        self._scroll()
    
    def _api_popup(self):
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        
        box = BoxLayout(orientation='vertical', padding=20, spacing=15)
        inp = TextInput(hint_text='sk-ant-...', multiline=False, size_hint_y=None, height=50)
        btn = Button(text='OK', size_hint_y=None, height=50)
        box.add_widget(Label(text='API Key'))
        box.add_widget(inp)
        box.add_widget(btn)
        
        pop = Popup(title='', content=box, size_hint=(0.9, 0.4), auto_dismiss=False)
        btn.bind(on_release=lambda x: self._save_key(inp.text, pop))
        pop.open()
    
    def _save_key(self, key, pop):
        if key.strip().startswith('sk-'):
            save_api_key(key.strip())
            pop.dismiss()


class ClaudeHome(App):
    font = StringProperty(FONT)
    
    def build(self):
        if ANDROID:
            request_permissions([Permission.INTERNET])
        Builder.load_string(KV)
        return RootWidget()


if __name__ == '__main__':
    ClaudeHome().run()
