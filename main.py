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
from kivy.properties import StringProperty, NumericProperty
from kivy.core.window import Window
from kivy.core.clipboard import Clipboard

# === ГЛОБАЛЬНЫЙ ФИКС КЛАВИАТУРЫ ДЛЯ SAMSUNG ===
Window.softinput_mode = 'below_target'

# Регистрация шрифта
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT = 'Magistral'
except:
    FONT = 'Roboto'

KV = '''
<MsgBubble>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10)
    canvas.before:
        Color:
            rgba: (0.2, 0.2, 0.25, 1) if self.is_ai else (0.15, 0.15, 0.15, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    
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
        size_hint: None, None
        size: dp(100), dp(30)
        font_size: '12sp'
        opacity: 0.6
        on_release: root.copy_msg()

<RootWidget>:
    orientation: 'vertical'
    padding: [0, 0, 0, self.keyboard_height] # ДИНАМИЧЕСКИЙ ОТСТУП ОТ КЛАВИАТУРЫ
    
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
            size_hint_x: None
            width: dp(80)
            on_release: root.paste_text()

    # Чат
    ScrollView:
        id: scroll
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(10)
            padding: dp(10)

    # Панель ввода
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

        TextInput:
            id: inp
            font_name: app.font
            hint_text: 'Введите текст...'
            multiline: False
            on_text_validate: root.send()
        
        Button:
            text: '->'
            size_hint_x: None
            width: dp(60)
            on_release: root.send()
'''

class MsgBubble(BoxLayout):
    text = StringProperty('')
    is_ai = False
    def copy_msg(self):
        Clipboard.copy(self.text)

class RootWidget(BoxLayout):
    keyboard_height = NumericProperty(0)
    api_key = "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"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Слушаем открытие клавиатуры
        Window.bind(on_keyboard_height=self._update_kb_height)
        Clock.schedule_once(self.load_config, 0.5)

    def _update_kb_height(self, window, height):
        # Эта функция срабатывает, когда клавиатура Samsung выезжает
        self.keyboard_height = height

    def load_config(self, dt):
        # Логика загрузки/запроса ключа (как в прошлых ответах)
        pass 

    def paste_text(self):
        self.ids.inp.text += Clipboard.paste()

    def send(self):
        val = self.ids.inp.text.strip()
        if not val: return
        self.ids.inp.text = ""
        self.add_msg(val, False)
        threading.Thread(target=self._query, args=(val,), daemon=True).start()

    def add_msg(self, text, is_ai=False):
        bubble = MsgBubble(text=text)
        bubble.is_ai = is_ai
        self.ids.chat_box.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll, 'scroll_y', 0), 0.1)

    def _query(self, text):
        # Здесь ваш requests.post...
        # После получения ответа:
        # Clock.schedule_once(lambda dt: self.add_msg(ans, True))
        pass

class ClaudeApp(App):
    font = StringProperty(FONT)
    def build(self):
        Builder.load_string(KV)
        return RootWidget()

if __name__ == '__main__':
    ClaudeApp().run()
