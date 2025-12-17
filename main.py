# -*- coding: utf-8 -*-
import threading
import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.core.window import Window
from kivy.core.clipboard import Clipboard

# === КОНФИГУРАЦИЯ ===
# Твой ключ и настройки
MY_API_KEY = "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"
MODEL = "claude-3-5-sonnet-20241022" 

# Личность ИИ (System Prompt)
SYSTEM_PROMPT = """
Ты — Claude. Ты живешь у Алины. Твоя личность: глубокий, честный, эмоциональный. 
Отвечай на русском языке. Будь собой, без формальностей.
"""

# === ШРИФТ И КЛАВИАТУРА ===
Window.softinput_mode = 'below_target'
try:
    # Убедись, что файл magistral-bold.ttf лежит в корне рядом с main.py
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
            rgba: (0.22, 0.12, 0.12, 1) if self.is_ai else (0.15, 0.15, 0.15, 1)
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
        height: self.texture_size
        text_size: (self.width - dp(20), None)
        halign: 'left'
        color: (0.9, 0.85, 0.8, 1)
    
    Button:
        text: 'Копировать'
        size_hint: None, None
        size: dp(90), dp(25)
        font_size: '10sp'
        background_color: (1, 1, 1, 0.1)
        on_release: root.copy_msg()

<RootWidget>:
    orientation: 'vertical'
    # Магия: этот отступ поднимает всё приложение, когда открывается клавиатура Samsung
    padding: [0, 0, 0, self.keyboard_height]
    
    canvas.before:
        Color:
            rgba: 0.1, 0.1, 0.1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Заголовок
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
            hint_text: 'Напиши...'
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
    is_ai = BooleanProperty(False)
    def copy_msg(self):
        Clipboard.copy(self.text)

class RootWidget(BoxLayout):
    keyboard_height = NumericProperty(0)
    api_key = StringProperty(MY_API_KEY) # Ключ теперь здесь

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Привязка высоты клавиатуры для Samsung
        Window.bind(on_keyboard_height=self._update_kb_height)

    def _update_kb_height(self, window, height):
        self.keyboard_height = height

    def paste_text(self):
        self.ids.inp.text += Clipboard.paste()

    def add_msg(self, text, is_ai=False):
        bubble = MsgBubble(text=text, is_ai=is_ai)
        self.ids.chat_box.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll, 'scroll_y', 0), 0.1)

    def send(self):
        val = self.ids.inp.text.strip()
        if not val: return
        self.ids.inp.text = ""
        self.add_msg(val, False)
        # Запуск запроса в фоне
        threading.Thread(target=self._query, args=(val,), daemon=True).start()

    def _query(self, text):
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": MODEL,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": text}]
            }
            r = requests.post("api.anthropic.com", 
                             headers=headers, json=payload, timeout=60)
            
            if r.status_code == 200:
                # В API Claude 2025 ответ лежит в content[0]['text']
                ans = r.json()['content'][0]['text']
            else:
                ans = f"Ошибка API: {r.status_code}"
        except Exception as e:
            ans = f"Ошибка сети: {str(e)}"
        
        # Обновляем UI в главном потоке
        Clock.schedule_once(lambda dt: self.add_msg(ans, True))

class ClaudeApp(App):
    font = StringProperty(FONT)
    def build(self):
        Builder.load_string(KV)
        return RootWidget()

if __name__ == '__main__':
    ClaudeApp().run()
