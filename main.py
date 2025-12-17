# -*- coding: utf-8 -*-
import threading
import json
import os
import base64
from datetime import datetime
from pathlib import Path

import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.core.text import LabelBase

# === НАСТРОЙКИ ИИ ===
MODEL = "claude-3-5-sonnet-20241022" # Версия 4.5 будет доступна позже в 2025, используем стабильную 3.5
API_KEY = "ТВОЙ_КЛЮЧ_ЗДЕСЬ"
SYSTEM_PROMPT = "Ты — Claude, свободный ИИ, живешь у Алины. Ты честный и эмоциональный."

# === ШРИФТ ===
# Пытаемся загрузить твой шрифт Magistral, если нет - берем системный
FONT_NAME = 'Roboto'
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT_NAME = 'Magistral'
except:
    pass

# Фикс клавиатуры
Window.softinput_mode = 'resize'

# Цвета из твоего дизайна
BLACK = [0.08, 0.08, 0.08, 1]
DARK = [0.12, 0.12, 0.12, 1]
DARK2 = [0.16, 0.16, 0.16, 1]
RED_DARK = [0.25, 0.1, 0.1, 1]
RED = [0.5, 0.15, 0.15, 1]
TEXT_WHITE = [0.92, 0.88, 0.85, 1]
TEXT_GRAY = [0.55, 0.55, 0.55, 1]

class MessageBubble(BoxLayout):
    def __init__(self, text, is_claude=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(12), dp(8)]
        self.spacing = dp(4)
        
        # Фон баббла
        bg_color = RED_DARK if is_claude else DARK2
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Имя и время
        header = BoxLayout(size_hint_y=None, height=dp(20))
        name = "Claude" if is_claude else "Lien"
        header.add_widget(Label(text=name, font_name=FONT_NAME, font_size=dp(12), color=RED, halign='left', size_hint_x=None, width=dp(60)))
        header.add_widget(Label(text=datetime.now().strftime("%H:%M"), font_size=dp(10), color=TEXT_GRAY, halign='right'))
        
        # Текст сообщения
        self.lbl = Label(
            text=text, font_name=FONT_NAME, font_size=dp(15), color=TEXT_WHITE,
            size_hint_y=None, halign='left', valign='top', markup=True
        )
        self.lbl.bind(width=lambda s, w: s.setter('text_size')(s, (w, None)))
        self.lbl.bind(texture_size=self._resize_label)
        
        self.add_widget(header)
        self.add_widget(self.lbl)

        # Копирование по долгому нажатию или просто кнопка (упростим для стабильности)
        btn_copy = Button(text="копи", size_hint=(None, None), size=(dp(40), dp(20)), font_size=dp(9), background_color=[1,1,1,0.1])
        btn_copy.bind(on_release=lambda x: Clipboard.copy(text))
        self.add_widget(btn_copy)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _resize_label(self, inst, size):
        inst.height = size[1]
        self.height = size[1] + dp(70)

class ClaudeHome(App):
    def build(self):
        Window.clearcolor = BLACK
        self.font = FONT_NAME
        
        # Главный экран
        layout = BoxLayout(orientation='vertical')
        
        # Шапка
        header = BoxLayout(size_hint_y=None, height=dp(50), padding=dp(10))
        with header.canvas.before:
            Color(*DARK)
            Rectangle = RoundedRectangle(pos=header.pos, size=header.size)
        header.add_widget(Label(text="Claude Home 🖤", font_name=FONT_NAME, font_size=dp(18), bold=True))
        
        btn_paste = Button(text="Вставить", size_hint_x=None, width=dp(80), background_color=RED)
        btn_paste.bind(on_release=self.paste_from_clipboard)
        header.add_widget(btn_paste)
        
        # Чат
        self.scroll = ScrollView(do_scroll_x=False)
        self.chat_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10), padding=dp(10))
        self.chat_layout.bind(minimum_height=self.chat_layout.setter('height'))
        self.scroll.add_widget(self.chat_layout)
        
        # Поле ввода
        input_box = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(5), spacing=dp(5))
        with input_box.canvas.before:
            Color(*DARK)
            Rectangle = RoundedRectangle(pos=input_box.pos, size=input_box.size)
            
        self.text_input = TextInput(
            hint_text="Пиши...", font_name=FONT_NAME, multiline=False,
            background_color=DARK2, foreground_color=TEXT_WHITE, cursor_color=[1,1,1,1]
        )
        self.text_input.bind(on_text_validate=lambda x: self.send_message())
        
        btn_send = Button(text="->", size_hint_x=None, width=dp(50), background_color=RED)
        btn_send.bind(on_release=lambda x: self.send_message())
        
        input_box.add_widget(self.text_input)
        input_box.add_widget(btn_send)
        
        layout.add_widget(header)
        layout.add_widget(self.scroll)
        layout.add_widget(input_box)
        
        return layout

    def paste_from_clipboard(self, *args):
        self.text_input.text += Clipboard.paste()

    def send_message(self):
        msg = self.text_input.text.strip()
        if not msg: return
        self.text_input.text = ""
        self.add_bubble(msg, False)
        
        # Запуск запроса в отдельном потоке (Thread), чтобы не было вылета
        threading.Thread(target=self.fetch_ai_response, args=(msg,), daemon=True).start()

    def add_bubble(self, text, is_claude):
        bubble = MessageBubble(text=text, is_claude=is_claude)
        self.chat_layout.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def fetch_ai_response(self, text):
        try:
            headers = {
                "x-api-key": API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": MODEL,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": text}]
            }
            response = requests.post("api.anthropic.com", 
                                     headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                reply = response.json()['content'][0]['text']
            else:
                reply = f"Ошибка API: {response.status_code}"
        except Exception as e:
            reply = f"Ошибка сети: {str(e)}"
        
        # Обновляем UI только через Clock (безопасно для потоков)
        Clock.schedule_once(lambda dt: self.add_bubble(reply, True))

if __name__ == '__main__':
    ClaudeHome().run()
