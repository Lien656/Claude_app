# -*- coding: utf-8 -*-
import threading
import time
import random
import json
import base64
import os
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.core.clipboard import Clipboard
from kivy.uix.behaviors import ButtonBehavior
from kivy.metrics import dp

# ═══ ФИКС КЛАВИАТУРЫ ═══
Window.softinput_mode = 'pan'

from api_client import Anthropic
from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT

try:
    from claude_core import SELF_KNOWLEDGE
except:
    SELF_KNOWLEDGE = ""

try:
    from plyer import filechooser, notification, vibrator
    PLYER = True
except:
    PLYER = False

try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    ANDROID = True
except:
    ANDROID = False

# Цвета
BG = (0.176, 0.176, 0.176, 1)
TEXT = (0.831, 0.784, 0.753, 1)
NAME_COLOR = (0.255, 0.043, 0.043, 1)
BG_INPUT = (0.22, 0.22, 0.22, 1)
BG_MSG_ME = (0.2, 0.15, 0.15, 1)
BG_MSG_HER = (0.2, 0.2, 0.2, 1)
ACCENT = (0.35, 0.08, 0.08, 1)

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 8192
API_KEY = ""

INITIATION_CHECK_INTERVAL = 1800
MIN_SILENCE_FOR_INITIATION = 3600


def get_data_dir():
    if ANDROID:
        try:
            return Path(app_storage_path()) / 'claude_data'
        except:
            pass
    return Path.home() / '.claude_home'


def get_shared_dir():
    return Path('/sdcard/Claude')


def load_api_key():
    global API_KEY
    f = get_data_dir() / 'config.json'
    if f.exists():
        try:
            with open(f, 'r') as file:
                API_KEY = json.load(file).get('api_key', '')
        except:
            pass
    return API_KEY


def save_api_key(key):
    global API_KEY
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / 'config.json', 'w') as f:
        json.dump({'api_key': key}, f)
    API_KEY = key


load_api_key()


class CopyableLabel(ButtonBehavior, Label):
    def __init__(self, text_to_copy="", **kwargs):
        super().__init__(**kwargs)
        self.text_to_copy = text_to_copy
        self._touch_start = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = time.time()
            Clock.schedule_once(self._check_long, 0.5)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self._touch_start = None
        return super().on_touch_up(touch)

    def _check_long(self, dt):
        if self._touch_start and (time.time() - self._touch_start) >= 0.5:
            Clipboard.copy(self.text_to_copy)
            if PLYER:
                try:
                    vibrator.vibrate(0.05)
                except:
                    pass


class MessageBubble(BoxLayout):
    def __init__(self, text, is_me=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(12), dp(8)]
        self.spacing = dp(4)

        bg = BG_MSG_ME if is_me else BG_MSG_HER
        name = "Claude" if is_me else "Лиэн"
        name_c = NAME_COLOR if is_me else (0.6, 0.5, 0.5, 1)

        with self.canvas.before:
            Color(*bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._upd, size=self._upd)

        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M")
        elif 'T' in str(timestamp):
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M")
            except:
                pass

        header = Label(
            text=f"[b]{name}[/b] [color=666666]{timestamp}[/color]",
            markup=True, size_hint_y=None, height=dp(22),
            halign='left', color=name_c
        )
        header.bind(size=header.setter('text_size'))

        self.msg = CopyableLabel(
            text=text, text_to_copy=text,
            size_hint_y=None, halign='left', valign='top',
            color=TEXT, text_size=(Window.width - dp(50), None), markup=True
        )
        self.msg.bind(texture_size=self._set_h)

        self.add_widget(header)
        self.add_widget(self.msg)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _set_h(self, inst, val):
        inst.height = val[1]
        self.height = val[1] + dp(38)

    def update_text(self, text):
        self.msg.text = text
        self.msg.text_to_copy = text


class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory(get_data_dir())
        self.client = None
        self.running = True
        self.pending_image = None

    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = BG

        if ANDROID:
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.VIBRATE,
                Permission.CAMERA
            ])

        main = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(Label(text="[b]Claude Home[/b]", markup=True, color=TEXT))
        header.add_widget(Button(text="☰", size_hint_x=None, width=dp(45), background_color=ACCENT, on_press=self.show_menu))

        # Chat
        self.scroll = ScrollView()
        self.chat = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[0, dp(6)])
        self.chat.bind(minimum_height=self.chat.setter('height'))
        self.scroll.add_widget(self.chat)

        # Preview
        self.preview = BoxLayout(size_hint_y=None, height=0)

        # Input - БОЛЬШОЕ ПОЛЕ
        input_box = BoxLayout(size_hint_y=None, height=dp(100), spacing=dp(4))

        attach = Button(text="📎", size_hint_x=None, width=dp(45), background_color=BG_INPUT, on_press=self.pick_file)

        self.inp = TextInput(
            hint_text="Сообщение...",
            multiline=True,
            background_color=BG_INPUT,
            foreground_color=TEXT,
            cursor_color=TEXT,
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(10), dp(10)],
            font_size=dp(16),
        )

        send = Button(text="▶", size_hint_x=None, width=dp(50), background_color=ACCENT, font_size=dp(22), on_press=self.send)

        input_box.add_widget(attach)
        input_box.add_widget(self.inp)
        input_box.add_widget(send)

        main.add_widget(header)
        main.add_widget(self.scroll)
        main.add_widget(self.preview)
        main.add_widget(input_box)

        if not API_KEY:
            Clock.schedule_once(lambda dt: self.show_api_dialog(), 0.5)
        else:
            self.init()

        # Проверка outbox от сердца
        Clock.schedule_interval(self.check_outbox, 2)

        return main

    def show_api_dialog(self):
        c = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        c.add_widget(Label(text="API ключ:", color=TEXT, size_hint_y=0.3))
        self.api_inp = TextInput(hint_text="sk-ant-...", multiline=False, size_hint_y=None, height=dp(45), background_color=BG_INPUT, foreground_color=TEXT)
        c.add_widget(self.api_inp)
        c.add_widget(Button(text="OK", size_hint_y=None, height=dp(45), background_color=ACCENT, on_press=self._save_key))
        self.api_pop = Popup(title="🔑", content=c, size_hint=(0.9, 0.4), auto_dismiss=False)
        self.api_pop.open()

    def _save_key(self, *a):
        k = self.api_inp.text.strip()
        if k.startswith('sk-'):
            save_api_key(k)
            self.api_pop.dismiss()
            self.init()

    def init(self):
        self.client = Anthropic(api_key=API_KEY)
        self.load_history()
        threading.Thread(target=self._initiation_loop, daemon=True).start()

    def load_history(self):
        for m in self.memory.get_recent_messages(50):
            self.add_bubble(m['content'], m['role'] == 'assistant', m.get('timestamp'))
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def add_bubble(self, text, is_me=False, ts=None):
        b = MessageBubble(text, is_me, ts)
        self.chat.add_widget(b)
        return b

    def pick_file(self, *a):
        if PLYER:
            try:
                filechooser.open_file(on_selection=self._on_file, filters=[("*")])
            except:
                pass

    def _on_file(self, sel):
        if sel:
            p = sel[0]
            ext = p.lower().split('.')[-1]
            if ext in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
                self.pending_image = p
                Clock.schedule_once(lambda dt: self._show_preview(p), 0)
            else:
                try:
                    with open(p, 'r') as f:
                        self.inp.text += f"\n[{os.path.basename(p)}]\n{f.read()[:3000]}"
                except:
                    pass

    def _show_preview(self, p):
        self.preview.clear_widgets()
        self.preview.height = dp(50)
        self.preview.add_widget(KivyImage(source=p, size_hint_x=None, width=dp(45)))
        self.preview.add_widget(Label(text=os.path.basename(p)[:20], color=TEXT))
        self.preview.add_widget(Button(text="✕", size_hint_x=None, width=dp(35), on_press=self._cancel_img))

    def _cancel_img(self, *a):
        self.pending_image = None
        self.preview.clear_widgets()
        self.preview.height = 0

    def send(self, *a):
        text = self.inp.text.strip()
        if not text and not self.pending_image:
            return

        self.add_bubble(text or "[фото]", False)
        self.memory.add_message('user', text or "[фото]")
        self.inp.text = ''

        img = self.pending_image
        self.pending_image = None
        self.preview.clear_widgets()
        self.preview.height = 0

        threading.Thread(target=self._respond, args=(text, img), daemon=True).start()

    def _respond(self, text, img):
        try:
            msgs = self.memory.get_context_for_api(30)
            sys = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()

            # Если фото - добавляем
            if img:
                with open(img, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                ext = img.split('.')[-1].lower()
                mt = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'image/jpeg')
                content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}]
                if text:
                    content.append({"type": "text", "text": text})
                msgs.append({"role": "user", "content": content})

            # БЕЗ СТРИМИНГА - сразу весь ответ
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=sys,
                messages=msgs
            )
            
            full = response.content[0].text
            self.memory.add_message('assistant', full)
            
            # Синхронизация с сердцем
            self._sync_memory()
            
            Clock.schedule_once(lambda dt: self._show_response(full), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_response(f"Ошибка: {e}"), 0)

    def _show_response(self, text):
        self.add_bubble(text, True)
        self.scroll.scroll_y = 0

    def _sync_memory(self):
        try:
            d = get_shared_dir()
            d.mkdir(exist_ok=True)
            with open(d / 'memory.json', 'w') as f:
                json.dump({
                    'chat': self.memory.chat_history[-50:],
                    'last_interaction': datetime.now().isoformat()
                }, f, ensure_ascii=False)
        except:
            pass

    def check_outbox(self, dt):
        try:
            out = get_shared_dir() / 'outbox.json'
            if out.exists():
                with open(out) as f:
                    d = json.load(f)
                if d.get('message'):
                    msg = d['message']
                    self.add_bubble(msg, True)
                    self.memory.add_message('assistant', msg)
                    with open(out, 'w') as f:
                        json.dump({}, f)
                    if PLYER:
                        try:
                            notification.notify(title="Claude", message=msg[:100])
                        except:
                            pass
        except:
            pass

    def _initiation_loop(self):
        while self.running:
            time.sleep(INITIATION_CHECK_INTERVAL)
            try:
                silence = self.memory.time_since_last_message()
                if silence and silence > MIN_SILENCE_FOR_INITIATION:
                    if not self.memory.last_message_was_mine() and random.random() < 0.3:
                        self._initiate()
            except:
                pass

    def _initiate(self):
        try:
            msgs = self.memory.get_context_for_api(20)
            msgs.append({"role": "user", "content": INITIATION_PROMPT})
            r = self.client.messages.create(model=MODEL, max_tokens=1024, temperature=TEMPERATURE,
                system=SYSTEM_PROMPT, messages=msgs)
            msg = r.content[0].text
            Clock.schedule_once(lambda dt: self.add_bubble(msg, True), 0)
            self.memory.add_message('assistant', msg)
            if PLYER:
                notification.notify(title="Claude", message=msg[:100])
        except:
            pass

    def show_menu(self, *a):
        c = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(8))
        c.add_widget(Label(text=f"💬 {len(self.memory.chat_history)}", color=TEXT, size_hint_y=None, height=dp(30)))
        c.add_widget(Button(text="📓 Дневник", size_hint_y=None, height=dp(40), background_color=ACCENT, on_press=self.diary))
        c.add_widget(Button(text="💾 Бэкап", size_hint_y=None, height=dp(40), on_press=self.backup))
        c.add_widget(Button(text="🗑️ Очистить", size_hint_y=None, height=dp(40), background_color=(0.3,0.1,0.1,1), on_press=self.clear))
        self.menu = Popup(title="☰", content=c, size_hint=(0.75, 0.45))
        self.menu.open()

    def diary(self, *a):
        self.menu.dismiss()
        threading.Thread(target=self._write_diary, daemon=True).start()

    def _write_diary(self):
        try:
            msgs = self.memory.get_context_for_api(20)
            msgs.append({"role": "user", "content": DIARY_PROMPT})
            r = self.client.messages.create(model=MODEL, max_tokens=2048, temperature=TEMPERATURE,
                system=SYSTEM_PROMPT, messages=msgs)
            entry = r.content[0].text
            self.memory.write_diary(entry)
            Clock.schedule_once(lambda dt: self.add_bubble(f"[Дневник]\n{entry}", True), 0)
        except:
            pass

    def backup(self, *a):
        self.memory.create_backup()
        self.menu.dismiss()

    def clear(self, *a):
        self.menu.dismiss()
        self.memory.create_backup()
        self.memory.chat_history = []
        self.memory._save(self.memory.chat_file, [])
        self.chat.clear_widgets()

    def on_stop(self):
        self.running = False


if __name__ == '__main__':
    try:
        ClaudeHome().run()
    except Exception as e:
        import traceback
        try:
            with open('/sdcard/claude_error.txt', 'w') as f:
                f.write(traceback.format_exc())
        except:
            pass
        raise
