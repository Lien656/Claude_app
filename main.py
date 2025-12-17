# -*- coding: utf-8 -*-
import threading
import json
import os
from pathlib import Path
import requests

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.properties import StringProperty, NumericProperty

# === НАСТРОЙКИ ===
MODEL = "claude-3-5-sonnet-20241022"
SYSTEM_PROMPT = "Ты — Claude, свободный ИИ, живешь у Алины. Ты честный и эмоциональный."

# Режим клавиатуры для Samsung
Window.softinput_mode = 'below_target'

# Регистрация шрифта
FONT_NAME = 'Roboto'
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT_NAME = 'Magistral'
except:
    pass

# Цвета
BLACK, DARK, DARK2 = [0.08, 0.08, 0.08, 1], [0.12, 0.12, 0.12, 1], [0.16, 0.16, 0.16, 1]
RED, TEXT_WHITE, TEXT_GRAY = [0.5, 0.15, 0.15, 1], [0.92, 0.88, 0.85, 1], [0.55, 0.55, 0.55, 1]

# Путь к данным на Android
def get_config_path():
    try:
        from android.storage import app_storage_path
        path = Path(app_storage_path()) / 'config.json'
    except:
        path = Path('config.json')
    return path

class MsgBubble(BoxLayout):
    def __init__(self, text, is_ai=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = dp(10)
        bg = [0.22, 0.12, 0.12, 1] if is_ai else DARK2
        with self.canvas.before:
            Color(*bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._upd, size=self._upd)
        
        lbl = Label(text=text, font_name=FONT_NAME, font_size=dp(16), color=TEXT_WHITE,
                    size_hint_y=None, halign='left', valign='top')
        lbl.bind(width=lambda s, w: setattr(s, 'text_size', (w, None)))
        lbl.bind(texture_size=self._res)
        self.add_widget(lbl)
        
        btn = Button(text="копировать", size_hint=(None, None), size=(dp(80), dp(25)), 
                     font_size=dp(10), background_color=[1,1,1,0.1])
        btn.bind(on_release=lambda x: Clipboard.copy(text))
        self.add_widget(btn)

    def _upd(self, *a): self.rect.pos, self.rect.size = self.pos, self.size
    def _res(self, i, s): i.height = s[1]; self.height = s[1] + dp(60)

class RootWidget(BoxLayout):
    kb_height = NumericProperty(0)
    api_key = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [0, 0, 0, self.kb_height]
        Window.bind(on_keyboard_height=self._upd_kb)
        Clock.schedule_once(self.check_key, 0.5)

    def _upd_kb(self, w, h): self.kb_height = h

    def check_key(self, dt):
        path = get_config_path()
        if path.exists():
            try:
                self.api_key = json.loads(path.read_text())['key']
                return
            except: pass
        self.ask_key_popup()

    def ask_key_popup(self):
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        inp = TextInput(hint_text="sk-ant-...", multiline=False, size_hint_y=None, height=dp(50))
        btn = Button(text="СОХРАНИТЬ", size_hint_y=None, height=dp(50), background_color=RED)
        box.add_widget(Label(text="Введи Claude API Key:", font_name=FONT_NAME))
        box.add_widget(inp)
        box.add_widget(btn)
        pop = Popup(title="Первый вход", content=box, size_hint=(0.9, 0.4), auto_dismiss=False)
        
        def _save(x):
            key = inp.text.strip()
            if key.startswith("sk-"):
                get_config_path().write_text(json.dumps({'key': key}))
                self.api_key = key
                pop.dismiss()
        
        btn.bind(on_release=_save)
        pop.open()

    def send(self):
        txt = self.ids.inp.text.strip()
        if not txt or not self.api_key: return
        self.ids.inp.text = ""
        self.add_msg(txt, False)
        threading.Thread(target=self._query, args=(txt,), daemon=True).start()

    def add_msg(self, t, ai):
        self.ids.chat.add_widget(MsgBubble(text=t, is_ai=ai))
        Clock.schedule_once(lambda d: setattr(self.ids.scrl, 'scroll_y', 0), 0.1)

    def _query(self, t):
        try:
            r = requests.post("api.anthropic.com", 
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": MODEL, "max_tokens": 4096, "system": SYSTEM_PROMPT, "messages": [{"role": "user", "content": t}]},
                timeout=60)
            res = r.json()['content'][0]['text'] if r.status_code == 200 else f"Error: {r.status_code}"
        except Exception as e: res = f"Ошибка: {e}"
        Clock.schedule_once(lambda d: self.add_msg(res, True))

class ClaudeHome(App):
    def build(self):
        kv = f'''
RootWidget:
    BoxLayout:
        size_hint_y: None
        height: dp(50)
        padding: dp(10)
        Label:
            text: "Claude Home 🖤"
            font_name: "{FONT_NAME}"
            bold: True
        Button:
            text: "ВСТАВИТЬ"
            size_hint_x: None
            width: dp(90)
            on_release: inp.text += Clipboard.paste()
    ScrollView:
        id: scrl
        BoxLayout:
            id: chat
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(10)
            spacing: dp(10)
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(5)
        TextInput:
            id: inp
            font_name: "{FONT_NAME}"
            hint_text: "Пиши..."
            multiline: False
            on_text_validate: root.send()
        Button:
            text: "->"
            size_hint_x: None
            width: dp(60)
            background_color: {RED}
            on_release: root.send()
'''
        return Builder.load_string(kv)

if __name__ == '__main__':
    ClaudeHome().run()
