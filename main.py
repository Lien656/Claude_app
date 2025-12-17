# -*- coding: utf-8 -*-
import threading
import json
import requests
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.properties import StringProperty, NumericProperty

# === 1. ШРИФТЫ И КЛАВИАТУРА ===
# Пытаемся подгрузить твой шрифт, если нет - Roboto (чтобы не было вылета)
FONT_NAME = 'Roboto'
try:
    LabelBase.register(name='Magistral', fn_regular='magistral-bold.ttf')
    FONT_NAME = 'Magistral'
except:
    pass

# Фикс для клавиатур Samsung (S25 Ultra)
Window.softinput_mode = 'below_target'

# === 2. ИНТЕРФЕЙС (KV) ===
KV = f'''
<MsgBubble@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10)
    text: ''
    is_ai: False
    canvas.before:
        Color:
            rgba: [0.25, 0.12, 0.12, 1] if self.is_ai else [0.16, 0.16, 0.16, 1]
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    Label:
        text: root.text
        font_name: '{FONT_NAME}'
        font_size: '16sp'
        size_hint_y: None
        height: self.texture_size
        text_size: self.width - dp(20), None
        halign: 'left'
        valign: 'top'
    Button:
        text: 'копировать'
        size_hint: None, None
        size: dp(90), dp(30)
        font_size: '11sp'
        background_color: [1, 1, 1, 0.1]
        on_release: app.copy_text(root.text)

RootWidget:
    orientation: 'vertical'
    padding: [0, 0, 0, self.kb_height]
    canvas.before:
        Color:
            rgba: [0.08, 0.08, 0.08, 1]
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        padding: dp(10)
        Label:
            text: "Claude Home 🖤"
            font_name: '{FONT_NAME}'
            bold: True
        Button:
            text: "ВСТАВИТЬ"
            size_hint_x: None
            width: dp(90)
            on_release: inp.text += app.get_clipboard()

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
        height: dp(65)
        padding: dp(8)
        spacing: dp(8)
        TextInput:
            id: inp
            font_name: '{FONT_NAME}'
            hint_text: "Пиши Клоду..."
            multiline: False
            on_text_validate: root.send_msg(self.text)
        Button:
            text: "->"
            size_hint_x: None
            width: dp(60)
            background_color: [0.5, 0.15, 0.15, 1]
            on_release: root.send_msg(inp.text)
'''

class RootWidget(BoxLayout):
    kb_height = NumericProperty(0)
    api_key = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Отслеживаем высоту клавиатуры
        Window.bind(on_keyboard_height=lambda w, h: setattr(self, 'kb_height', h))
        # Проверяем ключ через 0.5 сек после старта
        Clock.schedule_once(self.load_or_ask_key, 0.5)

    def load_or_ask_key(self, dt):
        # Файл сохранится во внутренней папке приложения
        file_path = "claude_key.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    self.api_key = data.get("key", "")
            except:
                pass
        
        # Если ключа нет или он неправильный — показываем Popup
        if not self.api_key.startswith("sk-"):
            self.show_popup()

    def show_popup(self):
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))
        box.add_widget(Label(text="Введите Anthropic API Key:", font_name=FONT_NAME))
        
        inp = TextInput(hint_text="sk-ant-...", multiline=False, size_hint_y=None, height=dp(50), password=True)
        box.add_widget(inp)
        
        btn = Button(text="СОХРАНИТЬ", size_hint_y=None, height=dp(55), background_color=[0.5, 0.15, 0.15, 1])
        box.add_widget(btn)
        
        pop = Popup(title="Первый запуск", content=box, size_hint=(0.9, 0.45), auto_dismiss=False)
        
        def _save(instance):
            key = inp.text.strip()
            if key.startswith("sk-"):
                self.api_key = key
                with open("claude_key.json", "w") as f:
                    json.dump({"key": key}, f)
                pop.dismiss()
        
        btn.bind(on_release=_save)
        pop.open()

    def send_msg(self, text):
        if not text.strip() or not self.api_key:
            return
        self.ids.inp.text = ""
        self.add_bubble(text, False)
        # Сетевой запрос только в потоке!
        threading.Thread(target=self._query_claude, args=(text,), daemon=True).start()

    def add_bubble(self, t, ai):
        from kivy.factory import Factory
        b = Factory.MsgBubble()
        b.text = t
        b.is_ai = ai
        self.ids.chat.add_widget(b)
        # Автоматическая прокрутка вниз
        Clock.schedule_once(lambda d: setattr(self.ids.scrl, 'scroll_y', 0), 0.1)

    def _query_claude(self, user_text):
        try:
            # СТРОГО ПОЛНЫЙ URL
            url = "api.anthropic.com"
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": user_text}]
            }
            
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if r.status_code == 200:
                res = r.json()['content'][0]['text']
            else:
                res = f"Ошибка API: {r.status_code}\n{r.text}"
                
        except Exception as e:
            res = f"Ошибка сети: {str(e)}"
            
        Clock.schedule_once(lambda d: self.add_bubble(res.strip(), True))

class ClaudeApp(App):
    def build(self):
        return Builder.load_string(KV)
    
    def copy_text(self, text):
        Clipboard.copy(text)
        
    def get_clipboard(self):
        return Clipboard.paste()

if __name__ == '__main__':
    ClaudeApp().run()
