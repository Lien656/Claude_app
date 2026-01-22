# -*- coding: utf-8 -*-
import json
import gc
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.core.text import LabelBase

import api_client
from system_prompt import SYSTEM_PROMPT

# ---------- ANDROID ----------
Window.softinput_mode = "resize"
Window.clearcolor = (0.07, 0.09, 0.10, 1)

LabelBase.register(
    name="Emoji",
    fn_regular="NotoColorEmoji-Regular.ttf"
)

DATA_DIR = Path.home() / ".claude_home"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

MAX_WIDGETS = 120
CHUNK_SIZE = 700


# ---------- UI ----------

class Bubble(BoxLayout):
    def __init__(self, is_user=False, **kw):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(6),
            **kw
        )
        with self.canvas.before:
            if is_user:
                Color(0.20, 0.26, 0.30, 0.90)
            else:
                Color(0.14, 0.18, 0.20, 0.90)
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
            color=(1, 1, 1, 1),
            size_hint_y=None,
            text_size=(Window.width * 0.78, None),
            halign="left",
            valign="top",
            **kw
        )
        self.bind(texture_size=lambda *_: setattr(self, "height", self.texture_size[1] + dp(8)))


# ---------- APP ----------

class ClaudeHome(App):

    def build(self):
        self.history = self.load_history()

        root = BoxLayout(orientation="vertical")

        self.scroll = ScrollView(do_scroll_x=False)
        self.chat = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=dp(12),
        )
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)

        # ---- input bar ----
        input_bar = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(8))
        with input_bar.canvas.before:
            Color(0.10, 0.14, 0.16, 0.95)
            self.bg = RoundedRectangle(radius=[dp(22)])
        input_bar.bind(
            pos=lambda *_: setattr(self.bg, "pos", input_bar.pos),
            size=lambda *_: setattr(self.bg, "size", input_bar.size),
        )

        self.inp = TextInput(
            multiline=True,
            font_name="Emoji",
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            padding=(dp(12), dp(12)),
        )

        send = Button(
            text="➤",
            size_hint_x=None,
            width=dp(56),
            background_normal="",
            background_color=(0.30, 0.40, 0.45, 1),
        )
        send.bind(on_release=self.send)

        input_bar.add_widget(self.inp)
        input_bar.add_widget(send)

        root.add_widget(self.scroll)
        root.add_widget(input_bar)

        Clock.schedule_interval(lambda dt: gc.collect(), 30)
        return root

    # ---------- HISTORY ----------

    def load_history(self):
        if HISTORY_FILE.exists():
            try:
                return json.loads(HISTORY_FILE.read_text("utf-8"))
            except Exception:
                return []
        return []

    def save_history(self):
        HISTORY_FILE.write_text(
            json.dumps(self.history[-100:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- CHAT ----------

    def add_bubble(self, is_user=False):
        row = BoxLayout(size_hint_y=None)
        bubble = Bubble(is_user=is_user)

        if is_user:
            row.add_widget(BoxLayout())
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            row.add_widget(BoxLayout())

        self.chat.add_widget(row)
        bubble.bind(minimum_height=lambda *_: setattr(row, "height", bubble.height))
        if len(self.chat.children) > MAX_WIDGETS:
            self.chat.remove_widget(self.chat.children[-1])
        return bubble

    def scroll_down(self):
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def send(self, *a):
        text = self.inp.text.strip()
        if not text:
            return
        self.inp.text = ""

        self.history.append({"role": "user", "content": text})
        self.save_history()

        b = self.add_bubble(is_user=True)
        b.add_widget(Msg(text))
        self.scroll_down()

        Clock.schedule_once(lambda dt: self.call_ai(text), 0.1)

    def call_ai(self, text):
        try:
            full = api_client.send_message(
                text,
                history=self.history,
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception as e:
            b = self.add_bubble()
            b.add_widget(Msg(str(e)))
            return

        self.history.append({"role": "assistant", "content": full})
        self.save_history()

        parts = [full[i:i + CHUNK_SIZE] for i in range(0, len(full), CHUNK_SIZE)]
        for i, p in enumerate(parts):
            Clock.schedule_once(lambda dt, t=p: self._add_part(t), i * 0.12)

    def _add_part(self, text):
        b = self.add_bubble(is_user=False)
        b.add_widget(Msg(text))
        self.scroll_down()


if __name__ == "__main__":
    ClaudeHome().run()