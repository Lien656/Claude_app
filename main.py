# -*- coding: utf-8 -*-
import threading
import json
import os
from pathlib import Path
import requests

# === КРИТИЧЕСКИЙ ФИКС SSL ДЛЯ ANDROID ===
import certifi
# Указываем Python, где искать сертификаты безопасности
os.environ['SSL_CERT_FILE'] = certifi.where()

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
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

Window.softinput_mode = 'below_target'

FONT_NAME = 'Roboto'
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT_NAME = 'Magistral'
except:
    pass

# Цвета
BLACK, DARK, DARK2 = [0.08, 0.08, 0.08, 1], [0.12, 0.12, 0.12, 1], [0.16, 0.16, 0.16, 1]
RED, TEXT_WHITE, TEXT_GRAY = [0.5, 0.15, 0.15, 1], [0.92, 0.88, 0.85, 1], [0.55, 0.55, 0.55, 1]

def get_config_path():
    try:
        from android.storage import app_storage_path
        d = Path(app_storage_path())
        d.mkdir(parents=True, exist_ok=True)
        return d / 'config.json'
    except:
        return Path('config.json')

class MsgBubble(BoxLayout):
    def __init__(self, text, is_ai=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = dp(12)
        bg = [0.25, 0.15, 0.15, 1] if is_ai else DARK2
        with self.canvas.before:
            Color(*bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self._upd, size=self._upd)
        
        lbl = Label(text=text, font_name=FONT_NAME, font_size=dp(16), color=TEXT_WHITE,
                    size_hint_y=None, halign='left', valign='top', markup=True)
        lbl.bind(width=lambda s, w: setattr(s, 'text_size', (w, None)))
        lbl.bind(texture_size=self._res)
        self.add_widget(lbl)
        
        btn = Button(text="копировать", size_hint=(None, None), size=(dp(90), dp(28)), 
                     font_size=dp(10), background_color=[1,1,1,0.1])
        btn.bind(on_release=lambda x: Clipboard.copy(text))
        self.add_widget(btn)

    def _upd(self, *a): self.rect.pos, self.rect.size = self.pos, self.size
    def _res(self, i, s): i.height = s; self.height = s + dp(65)

class RootWidget(BoxLayout):
    kb_height = NumericProperty(0)
    api_key = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        Window.bind(on_keyboard_height=self._upd_kb)
        Clock.schedule_once(self.check_key, 0.5)

    def _upd_kb(self, w, h):
        self.kb_height = h
        self.padding = [0, 0, 0, h]

    def check_key(self, dt):
        path = get_config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.api_key = data.get('key', "")
                if self.api_key: return
            except: pass
        self.ask_key_popup()

    def ask_key_popup(self):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        inp = TextInput(hint_text="sk-ant-...", multiline=False, size_hint_y=None, height=dp(50))
        btn = Button(text="СОХРАНИТЬ", size_hint_y=None, height=dp(55), background_color=RED)
        box.add_widget(Label(text="Введи Claude API Key:", font_name=FONT_NAME, font_size=dp(18)))
        box.add_widget(inp)
        box.add_widget(btn)
        pop = Popup(title="Авторизация", content=box, size_hint=(0.9, 0.45), auto_dismiss=False)
        
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
        self.ids.chat.add_widget(MsgBubble(text=str(t), is_ai=ai))
        Clock.schedule_once(lambda d: setattr(self.ids.scrl, 'scroll_y', 0), 0.2)

    def _query(self, t):
        try:
            # Расширенные заголовки для стабильности и user-agent
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "user-agent": "Mozilla/5.0 (Android 13)" 
            }
            data = {
                "model": MODEL,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": t}]
            }
            r = requests.post("api.anthropic.com", 
                              headers=headers, json=data, timeout=60)
            
            if r.status_code == 200:
                res = r.json()['content']
            else:
                # Если ошибка сервера - выводим ее в чат, а не падаем
                res = f"Ошибка сервера ({r.status_code}):\n{r.text[:200]}"
        except Exception as e:
            # Если ошибка сети/SSL - выводим ее в чат
            res = f"Ошибка сети или SSL:\n{str(e)}"
        
        Clock.schedule_once(lambda d: self.add_msg(res, True))

class ClaudeHome(App):
    def build(self):
        kv = f'''
RootWidget:
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(10)
        canvas.before:
            Color:
                rgba: {DARK}
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "Claude Home 🖤"
            font_name: "{FONT_NAME}"
            bold: True
            font_size: dp(20)
        Button:
            text: "ВСТАВИТЬ"
            font_name: "{FONT_NAME}"
            size_hint_x: None
            width: dp(100)
            background_color: [1,1,1,0.1]
            on_release: inp.text += Clipboard.paste()

    ScrollView:
        id: scrl
        do_scroll_x: False
        BoxLayout:
            id: chat
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(12)
            spacing: dp(15)

    BoxLayout:
        size_hint_y: None
        height: dp(70)
        padding: dp(8)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: {DARK}
            Rectangle:
                pos: self.pos
                size: self.size
        TextInput:
            id: inp
            font_name: "{FONT_NAME}"
            hint_text: "Твое сообщение..."
            multiline: False
            font_size: dp(16)
            background_color: {DARK2}
            foreground_color: {TEXT_WHITE}
            padding: [dp(10), dp(15)]
            on_text_validate: root.send()
        Button:
            text: "->"
            font_size: dp(24)
            size_hint_x: None
            width: dp(65)
            background_color: {RED}
            on_release: root.send()
'''
        return Builder.load_string(kv)

if __name__ == '__main__':
    ClaudeHome().run()
