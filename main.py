# -*- coding: utf-8 -*-
import threading
import time
import gc
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.core.text import LabelBase

# -----------------------------
# ЛИЧНОСТЬ ИИ НЕ ТРОГАЕМ
# -----------------------------
from system_prompt import SYSTEM_PROMPT
import chat_simple

# -----------------------------
# ШРИФТЫ
# -----------------------------
if Path("Roboto-Regular.ttf").exists():
    LabelBase.register("Default", "Roboto-Regular.ttf")

if Path("NotoColorEmoji-Regular.ttf").exists():
    LabelBase.register("Emoji", "NotoColorEmoji-Regular.ttf")

Window.clearcolor = (0.08, 0.10, 0.10, 1)
Window.softinput_mode = "pan"

# -----------------------------
# НАСТРОЙКИ БЕЗОПАСНОСТИ
# -----------------------------
MAX_CHUNK = 500        # маленькие куски = нет чёрных экранов
MAX_WIDGETS = 140      # чистка старых сообщений

# -----------------------------
# UI ЭЛЕМЕНТЫ
# -----------------------------
class GlassBubble(BoxLayout):
    def __init__(self, **kw):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(6),
            **kw
        )
        with self.canvas.before:
            Color(0.14, 0.20, 0.20, 0.75)   # glass
            self.bg = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        self.bind(minimum_height=self.setter("height"))

    def _upd(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size


class ChunkText(TextInput):
    """
    Это КЛЮЧЕВО:
    TextInput(readonly=True) = можно выделять и копировать части текста
    """
    def __init__(self, text="", **kw):
        super().__init__(
            text=text,
            readonly=True,
            multiline=True,
            font_name="Default",
            font_size=dp(15),
            foreground_color=(1, 1, 1, 1),
            background_color=(0, 0, 0, 0),
            cursor_color=(1, 1, 1, 1),
            padding=(dp(6), dp(6)),
            size_hint_y=None,
            **kw
        )

        self.bind(
            width=lambda *_: setattr(
                self, "text_size", (self.width - dp(10), None)
            ),
            texture_size=lambda *_: setattr(
                self, "height", self.texture_size[1] + dp(10)
            )
        )


# -----------------------------
# APP
# -----------------------------
class ClaudeHome(App):

    def build(self):
        root = BoxLayout(orientation="vertical")

        # ---------- CHAT ----------
        self.scroll = ScrollView(do_scroll_x=False)
        self.chat = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=dp(12)
        )
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)

        # ---------- INPUT (GLASS) ----------
        self.input_bar = BoxLayout(
            size_hint_y=None,
            height=dp(64),
            padding=dp(8),
            spacing=dp(6)
        )
        with self.input_bar.canvas.before:
            Color(0.10, 0.16, 0.16, 0.85)
            self.ibg = RoundedRectangle(radius=[dp(22)])
        self.input_bar.bind(pos=self._ibg, size=self._ibg)

        self.inp = TextInput(
            multiline=True,
            font_name="Default",
            font_size=dp(16),
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1)
        )

        send = Button(
            text="➤",
            size_hint_x=None,
            width=dp(56)
        )
        send.bind(on_release=self.send)

        self.input_bar.add_widget(self.inp)
        self.input_bar.add_widget(send)

        root.add_widget(self.scroll)
        root.add_widget(self.input_bar)

        Clock.schedule_interval(lambda dt: gc.collect(), 30)
        return root

    def _ibg(self, *a):
        self.ibg.pos = self.input_bar.pos
        self.ibg.size = self.input_bar.size

    # -------------------------
    # CHAT HELPERS
    # -------------------------
    def add_bubble(self):
        bubble = GlassBubble()
        self.chat.add_widget(bubble)

        # чистка старых сообщений
        if len(self.chat.children) > MAX_WIDGETS:
            self.chat.remove_widget(self.chat.children[-1])

        return bubble

    def scroll_down(self):
        Clock.schedule_once(
            lambda dt: setattr(self.scroll, "scroll_y", 0),
            0.05
        )

    # -------------------------
    # SEND
    # -------------------------
    def send(self, *a):
        text = self.inp.text.strip()
        if not text:
            return

        self.inp.text = ""

        # USER
        user_bubble = self.add_bubble()
        user_bubble.add_widget(ChunkText(text))
        self.scroll_down()

        # AI
        ai_bubble = self.add_bubble()
        threading.Thread(
            target=self.call_ai,
            args=(text, ai_bubble),
            daemon=True
        ).start()

    # -------------------------
    # AI CALL (ЛИЧНОСТЬ НЕ ТРОГАЕМ)
    # -------------------------
    def call_ai(self, text, bubble):
        try:
            full = chat_simple.send_message(
                chat_simple.API_KEY,
                [{"role": "user", "content": text}]
            )
        except Exception as e:
            Clock.schedule_once(
                lambda dt: bubble.add_widget(
                    ChunkText(f"[error] {e}")
                )
            )
            return

        # "живой" вывод маленькими кусками
        buf = ""
        for ch in full:
            buf += ch
            if len(buf) >= MAX_CHUNK:
                part = buf
                buf = ""
                Clock.schedule_once(
                    lambda dt, p=part:
                        bubble.add_widget(ChunkText(p))
                )
                time.sleep(0.01)

        if buf:
            Clock.schedule_once(
                lambda dt:
                    bubble.add_widget(ChunkText(buf))
            )

        Clock.schedule_once(lambda dt: self.scroll_down())


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    ClaudeHome().run()