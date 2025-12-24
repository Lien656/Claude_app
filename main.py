# -*- coding: utf-8 -*-
import threading
import json
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
from kivy.uix.popup import Popup

import api_client          # ✅ безопасный клиент
import history_search      # 🔍 поиск

# -----------------------------
# PATHS / DATA
# -----------------------------
DATA_DIR = Path.home() / ".claude_home"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

# -----------------------------
# FONTS
# -----------------------------
if Path("Roboto-Regular.ttf").exists():
    LabelBase.register("Default", "Roboto-Regular.ttf")
if Path("NotoColorEmoji-Regular.ttf").exists():
    LabelBase.register("Emoji", "NotoColorEmoji-Regular.ttf")

Window.clearcolor = (0.08, 0.10, 0.10, 1)
Window.softinput_mode = "pan"

MAX_WIDGETS = 120

# -----------------------------
# UI ELEMENTS
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
            Color(0.14, 0.20, 0.20, 0.75)
            self.bg = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._u, size=self._u)
        self.bind(minimum_height=self.setter("height"))

    def _u(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size


class ChunkText(TextInput):
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
            width=lambda *_: setattr(self, "text_size", (self.width - dp(10), None)),
            texture_size=lambda *_: setattr(self, "height", self.texture_size[1] + dp(10))
        )

# -----------------------------
# APP
# -----------------------------
class ClaudeHome(App):

    def build(self):
        self.history = []
        self.load_history()

        root = BoxLayout(orientation="vertical")

        # 🔍 SEARCH BAR
        search_bar = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            padding=(dp(8), dp(6)),
            spacing=dp(6)
        )

        self.search_input = TextInput(
            hint_text="🔍 поиск по истории",
            multiline=False,
            font_name="Default",
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1)
        )

        search_btn = Button(text="Найти", size_hint_x=None, width=dp(80))
        search_btn.bind(on_release=self.do_search)

        search_bar.add_widget(self.search_input)
        search_bar.add_widget(search_btn)

        root.add_widget(search_bar)

        # CHAT
        self.scroll = ScrollView(do_scroll_x=False)
        self.chat = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=dp(12)
        )
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)

        # INPUT BAR
        input_bar = BoxLayout(
            size_hint_y=None,
            height=dp(64),
            padding=dp(8),
            spacing=dp(6)
        )
        with input_bar.canvas.before:
            Color(0.10, 0.16, 0.16, 0.85)
            self.ibg = RoundedRectangle(radius=[dp(22)])
        input_bar.bind(pos=lambda *_: setattr(self.ibg, "pos", input_bar.pos),
                       size=lambda *_: setattr(self.ibg, "size", input_bar.size))

        self.inp = TextInput(
            multiline=True,
            font_name="Default",
            font_size=dp(16),
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1)
        )

        send = Button(text="➤", size_hint_x=None, width=dp(56))
        send.bind(on_release=self.send)

        input_bar.add_widget(self.inp)
        input_bar.add_widget(send)

        root.add_widget(self.scroll)
        root.add_widget(input_bar)

        Clock.schedule_interval(lambda dt: gc.collect(), 30)
        return root

    # -------------------------
    # HISTORY
    # -------------------------
    def load_history(self):
        if HISTORY_FILE.exists():
            try:
                txt = HISTORY_FILE.read_text("utf-8").strip()
                self.history = json.loads(txt) if txt else []
            except Exception:
                self.history = []

    def save_history(self):
        HISTORY_FILE.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # -------------------------
    # SEARCH
    # -------------------------
    def do_search(self, *a):
        query = self.search_input.text.strip()
        if not query:
            return

        results = history_search.search(query)
        if not results:
            Popup(
                title="Поиск",
                content=ChunkText("Ничего не найдено"),
                size_hint=(0.7, 0.3)
            ).open()
            return

        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        sv = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        inner.bind(minimum_height=inner.setter("height"))

        for msg in results:
            btn = Button(
                text=msg["content"][:500],
                size_hint_y=None,
                height=dp(56)
            )
            btn.bind(on_release=lambda _, t=msg["content"]:
                     setattr(self.inp, "text", self.inp.text + "\n" + t))
            inner.add_widget(btn)

        sv.add_widget(inner)
        box.add_widget(sv)

        Popup(
            title=f"Найдено: {len(results)}",
            content=box,
            size_hint=(0.9, 0.8)
        ).open()

    # -------------------------
    # CHAT
    # -------------------------
    def add_bubble(self):
        b = GlassBubble()
        self.chat.add_widget(b)
        if len(self.chat.children) > MAX_WIDGETS:
            self.chat.remove_widget(self.chat.children[-1])
        return b

    def scroll_down(self):
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def send(self, *a):
        text = self.inp.text.strip()
        if not text:
            return
        self.inp.text = ""

        self.history.append({"role": "user", "content": text})
        self.save_history()

        ub = self.add_bubble()
        ub.add_widget(ChunkText(text))
        self.scroll_down()

        ab = self.add_bubble()
        threading.Thread(
            target=self.call_ai,
            args=(text, ab),
            daemon=True
        ).start()

    def call_ai(self, text, bubble):
        try:
            full = api_client.send_message(text)
        except Exception as e:
            Clock.schedule_once(lambda dt: bubble.add_widget(ChunkText(str(e))))
            return

        self.history.append({"role": "assistant", "content": full})
        self.save_history()

        Clock.schedule_once(lambda dt: bubble.add_widget(ChunkText(full)))
        Clock.schedule_once(lambda dt: self.scroll_down())


# -----------------------------
if __name__ == "__main__":
    ClaudeHome().run()