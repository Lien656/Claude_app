# -*- coding: utf-8 -*-
import json
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import AsyncImage
from kivy.uix.filechooser import FileChooserIconView
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.core.text import LabelBase

from system_prompt import SYSTEM_PROMPT
import api_client

Window.softinput_mode = "resize"
Window.clearcolor = (0.08, 0.1, 0.12, 1)

LabelBase.register(
    name="Emoji",
    fn_regular="NotoColorEmoji-Regular.ttf"
)

DATA = Path.home() / ".claude_home"
DATA.mkdir(exist_ok=True)
HISTORY_FILE = DATA / "history.json"


class Bubble(BoxLayout):
    def __init__(self, is_user=False, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, padding=dp(12))
        with self.canvas.before:
            Color(*(0.25,0.3,0.35,1) if is_user else (0.16,0.18,0.22,1))
            self.bg = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._u, size=self._u)
        self.bind(minimum_height=self.setter("height"))

    def _u(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size


class Msg(Label):
    def __init__(self, text="", **kw):
        super().__init__(
            text=text,
            font_name="Emoji",
            color=(1,1,1,1),
            size_hint_y=None,
            text_size=(Window.width * 0.78, None),
            halign="left",
            valign="top",
        )
        self.bind(texture_size=lambda *_: setattr(self, "height", self.texture_size[1] + dp(8)))


class ClaudeApp(App):

    def build(self):
        self.history = self._load_history()

        root = BoxLayout(orientation="vertical")

        self.scroll = ScrollView()
        self.chat = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10), padding=dp(10))
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)

        bar = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(8))
        with bar.canvas.before:
            Color(0.1,0.14,0.16,1)
            self.bg = RoundedRectangle(radius=[dp(22)])
        bar.bind(pos=lambda *_: setattr(self.bg,"pos",bar.pos),
                 size=lambda *_: setattr(self.bg,"size",bar.size))

        self.inp = TextInput(
            multiline=True,
            font_name="Emoji",
            background_color=(0,0,0,0),
            foreground_color=(1,1,1,1),
            cursor_color=(1,1,1,1),
        )

        send = Button(text="➤", size_hint_x=None, width=dp(56))
        send.bind(on_release=self.send_text)

        attach = Button(text="📎", size_hint_x=None, width=dp(56))
        attach.bind(on_release=self.pick_file)

        bar.add_widget(attach)
        bar.add_widget(self.inp)
        bar.add_widget(send)

        root.add_widget(self.scroll)
        root.add_widget(bar)
        return root

    def _load_history(self):
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text("utf-8"))
        return []

    def _save_history(self):
        HISTORY_FILE.write_text(json.dumps(self.history[-100:], ensure_ascii=False, indent=2), "utf-8")

    def add_bubble(self, is_user):
        row = BoxLayout(size_hint_y=None)
        bubble = Bubble(is_user=is_user)
        if is_user:
            row.add_widget(BoxLayout())
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            row.add_widget(BoxLayout())
        self.chat.add_widget(row)
        bubble.bind(minimum_height=lambda *_: setattr(row,"height",bubble.height))
        Clock.schedule_once(lambda *_: setattr(self.scroll,"scroll_y",0),0.05)
        return bubble

    def send_text(self, *a):
        text = self.inp.text.strip()
        if not text:
            return
        self.inp.text = ""
        self.history.append({"role":"user","content":text})
        self._save_history()

        b = self.add_bubble(True)
        b.add_widget(Msg(text))

        Clock.schedule_once(lambda *_: self.call_ai(text=text), 0.1)

    def pick_file(self, *a):
        chooser = FileChooserIconView(filters=["*.jpg","*.png","*.jpeg","*.pdf","*.mp4"])
        box = BoxLayout(orientation="vertical")
        box.add_widget(chooser)
        ok = Button(text="Отправить", size_hint_y=None, height=dp(48))
        box.add_widget(ok)

        def send_file(*_):
            if chooser.selection:
                path = chooser.selection[0]
                b = self.add_bubble(True)
                if path.lower().endswith((".jpg",".png",".jpeg")):
                    b.add_widget(AsyncImage(source=path, size_hint_y=None, height=dp(160)))
                    self.call_ai("Опиши изображение", image_path=path)
                else:
                    b.add_widget(Msg(f"📎 Файл: {path.split('/')[-1]}"))
                    self.call_ai(f"Пользователь отправил файл {path}")
                self.root.remove_widget(box)

        ok.bind(on_release=send_file)
        self.root.add_widget(box)

    def call_ai(self, text, image_path=None):
        reply = api_client.send_message(
            text,
            history=self.history,
            system_prompt=SYSTEM_PROMPT,
            image_path=image_path,
        )
        self.history.append({"role":"assistant","content":reply})
        self._save_history()
        b = self.add_bubble(False)
        b.add_widget(Msg(reply))


if __name__ == "__main__":
    ClaudeApp().run()