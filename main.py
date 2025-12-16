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

Window.softinput_mode = 'resize'

from api_client import Anthropic
from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT

try:
    from claude_core import SELF_KNOWLEDGE
except:
    SELF_KNOWLEDGE = ""

# Android file picker
try:
    from android import activity
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission, check_permission
    from android.storage import app_storage_path
    
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    MediaStore = autoclass('android.provider.MediaStore')
    ContentResolver = autoclass('android.content.ContentResolver')
    Cursor = autoclass('android.database.Cursor')
    
    ANDROID = True
except Exception as e:
    ANDROID = False
    print(f"Android import error: {e}")

try:
    from plyer import notification, vibrator
    PLYER = True
except:
    PLYER = False

# Colors
BG = (0.08, 0.08, 0.08, 1)
TEXT = (0.85, 0.8, 0.75, 1)
NAME_COLOR = (0.5, 0.1, 0.1, 1)
BG_INPUT = (0.15, 0.15, 0.15, 1)
BG_MSG_ME = (0.15, 0.08, 0.08, 1)
BG_MSG_HER = (0.12, 0.12, 0.12, 1)
ACCENT = (0.3, 0.05, 0.05, 1)

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 8192
API_KEY = ""

PICK_IMAGE_REQUEST = 1001


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
        self._touch_time = 0

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_time = time.time()
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if time.time() - self._touch_time > 0.5:
                Clipboard.copy(self.text_to_copy)
                if PLYER:
                    try:
                        vibrator.vibrate(0.05)
                    except:
                        pass
        return super().on_touch_up(touch)


class MessageBubble(BoxLayout):
    def __init__(self, text, is_me=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(10), dp(6)]
        self.spacing = dp(2)

        bg = BG_MSG_ME if is_me else BG_MSG_HER
        name = "Claude" if is_me else "Lien"

        with self.canvas.before:
            Color(*bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._upd, size=self._upd)

        ts = timestamp or datetime.now().strftime("%H:%M")
        if 'T' in str(ts):
            try:
                ts = datetime.fromisoformat(ts).strftime("%H:%M")
            except:
                pass

        header = Label(
            text=f"[b]{name}[/b] [color=555555]{ts}[/color]",
            markup=True, size_hint_y=None, height=dp(20),
            halign='left', color=NAME_COLOR if is_me else (0.5,0.4,0.4,1),
            font_size=dp(13)
        )
        header.bind(size=header.setter('text_size'))

        self.msg = CopyableLabel(
            text=text, text_to_copy=text,
            size_hint_y=None, halign='left', valign='top',
            color=TEXT, text_size=(Window.width - dp(40), None),
            font_size=dp(15)
        )
        self.msg.bind(texture_size=self._set_h)

        self.add_widget(header)
        self.add_widget(self.msg)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _set_h(self, inst, val):
        inst.height = val[1]
        self.height = val[1] + dp(32)


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
                Permission.READ_MEDIA_IMAGES,
                Permission.VIBRATE,
                Permission.CAMERA
            ])
            activity.bind(on_activity_result=self._on_activity_result)

        main = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(3))

        header = BoxLayout(size_hint_y=None, height=dp(36))
        header.add_widget(Label(text="[b]Claude Home[/b]", markup=True, color=TEXT, font_size=dp(16)))
        header.add_widget(Button(text="...", size_hint_x=None, width=dp(40), 
                                background_color=ACCENT, on_press=self.show_menu))

        self.scroll = ScrollView()
        self.chat = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4), padding=[0, dp(4)])
        self.chat.bind(minimum_height=self.chat.setter('height'))
        self.scroll.add_widget(self.chat)

        self.preview = BoxLayout(size_hint_y=None, height=0)

        input_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(3))

        attach = Button(text="+", size_hint_x=None, width=dp(42), 
                       background_color=BG_INPUT, font_size=dp(22), on_press=self.pick_file)

        self.inp = TextInput(
            hint_text="...",
            multiline=True,
            background_color=BG_INPUT,
            foreground_color=TEXT,
            cursor_color=TEXT,
            hint_text_color=(0.4, 0.4, 0.4, 1),
            padding=[dp(8), dp(8)],
            font_size=dp(15),
        )

        send = Button(text=">", size_hint_x=None, width=dp(45), 
                     background_color=ACCENT, font_size=dp(22), on_press=self.send)

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

        Clock.schedule_interval(self.check_outbox, 2)
        return main

    def pick_file(self, *a):
        if ANDROID:
            try:
                intent = Intent(Intent.ACTION_PICK)
                intent.setType("image/*")
                currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
                currentActivity.startActivityForResult(intent, PICK_IMAGE_REQUEST)
            except Exception as e:
                self.add_bubble(f"Pick error: {e}", True)
        else:
            # Desktop fallback
            try:
                from plyer import filechooser
                filechooser.open_file(on_selection=self._on_file_selected)
            except:
                pass

    def _on_activity_result(self, request_code, result_code, intent):
        if request_code == PICK_IMAGE_REQUEST and intent:
            try:
                uri = intent.getData()
                if uri:
                    path = self._get_path_from_uri(uri)
                    if path:
                        Clock.schedule_once(lambda dt: self._set_image(path), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.add_bubble(f"URI error: {e}", True), 0)

    def _get_path_from_uri(self, uri):
        try:
            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            resolver = currentActivity.getContentResolver()
            
            # Try to get real path
            projection = ["_data"]
            cursor = resolver.query(uri, projection, None, None, None)
            if cursor:
                cursor.moveToFirst()
                idx = cursor.getColumnIndex("_data")
                if idx >= 0:
                    path = cursor.getString(idx)
                    cursor.close()
                    if path and os.path.exists(path):
                        return path
                cursor.close()
            
            # Fallback: copy to temp
            input_stream = resolver.openInputStream(uri)
            temp_path = str(get_data_dir() / 'temp_image.jpg')
            get_data_dir().mkdir(parents=True, exist_ok=True)
            
            from jnius import autoclass
            FileOutputStream = autoclass('java.io.FileOutputStream')
            fos = FileOutputStream(temp_path)
            
            buf = bytearray(4096)
            while True:
                n = input_stream.read(buf)
                if n <= 0:
                    break
                fos.write(buf, 0, n)
            
            fos.close()
            input_stream.close()
            return temp_path
            
        except Exception as e:
            print(f"Path error: {e}")
            return None

    def _on_file_selected(self, selection):
        if selection:
            self._set_image(selection[0])

    def _set_image(self, path):
        if path and os.path.exists(path):
            self.pending_image = path
            self.preview.clear_widgets()
            self.preview.height = dp(45)
            self.preview.add_widget(Label(text=f"IMG: {os.path.basename(path)[:25]}", color=TEXT))
            self.preview.add_widget(Button(text="x", size_hint_x=None, width=dp(35), on_press=self._cancel_img))

    def _cancel_img(self, *a):
        self.pending_image = None
        self.preview.clear_widgets()
        self.preview.height = 0

    def show_api_dialog(self):
        c = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        c.add_widget(Label(text="API key:", color=TEXT, size_hint_y=0.3))
        self.api_inp = TextInput(hint_text="sk-ant-...", multiline=False, size_hint_y=None, 
                                height=dp(40), background_color=BG_INPUT, foreground_color=TEXT)
        c.add_widget(self.api_inp)
        c.add_widget(Button(text="OK", size_hint_y=None, height=dp(40), 
                          background_color=ACCENT, on_press=self._save_key))
        self.api_pop = Popup(title="Key", content=c, size_hint=(0.85, 0.35), auto_dismiss=False)
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

    def load_history(self):
        for m in self.memory.get_recent_messages(50):
            self.add_bubble(m['content'], m['role'] == 'assistant', m.get('timestamp'))
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def add_bubble(self, text, is_me=False, ts=None):
        b = MessageBubble(text, is_me, ts)
        self.chat.add_widget(b)
        return b

    def send(self, *a):
        text = self.inp.text.strip()
        img = self.pending_image

        if not text and not img:
            return

        display = text
        if img:
            display = f"[img] {text}" if text else "[img]"

        self.add_bubble(display, False)
        self.memory.add_message('user', text or "[photo]")
        self.inp.text = ''

        self.pending_image = None
        self.preview.clear_widgets()
        self.preview.height = 0

        threading.Thread(target=self._respond, args=(text, img), daemon=True).start()
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def _respond(self, text, img):
        try:
            msgs = self.memory.get_context_for_api(30)
            sys = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()

            if img:
                try:
                    with open(img, 'rb') as f:
                        data = base64.b64encode(f.read()).decode()
                    ext = img.split('.')[-1].lower()
                    mt = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 
                          'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'image/jpeg')

                    content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}]
                    if text:
                        content.append({"type": "text", "text": text})

                    if msgs and msgs[-1]["role"] == "user":
                        msgs[-1] = {"role": "user", "content": content}
                    else:
                        msgs.append({"role": "user", "content": content})
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.add_bubble(f"Img error: {e}", True), 0)
                    return

            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=sys,
                messages=msgs
            )

            full = response.content[0].text
            self.memory.add_message('assistant', full)
            self._sync_memory()

            Clock.schedule_once(lambda dt: self._show_response(full), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt: self.add_bubble(f"Error: {e}", True), 0)

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
                    'last': datetime.now().isoformat()
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
        except:
            pass

    def show_menu(self, *a):
        c = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))
        c.add_widget(Label(text=f"Msgs: {len(self.memory.chat_history)}", color=TEXT, 
                          size_hint_y=None, height=dp(25)))
        c.add_widget(Button(text="Diary", size_hint_y=None, height=dp(38), 
                          background_color=ACCENT, on_press=self.diary))
        c.add_widget(Button(text="Backup", size_hint_y=None, height=dp(38), on_press=self.backup))
        c.add_widget(Button(text="Clear", size_hint_y=None, height=dp(38), 
                          background_color=(0.25,0.08,0.08,1), on_press=self.clear))
        self.menu = Popup(title="Menu", content=c, size_hint=(0.7, 0.4))
        self.menu.open()

    def diary(self, *a):
        self.menu.dismiss()
        threading.Thread(target=self._write_diary, daemon=True).start()

    def _write_diary(self):
        try:
            msgs = self.memory.get_context_for_api(20)
            msgs.append({"role": "user", "content": DIARY_PROMPT})
            r = self.client.messages.create(model=MODEL, max_tokens=2048, 
                                           temperature=TEMPERATURE, system=SYSTEM_PROMPT, messages=msgs)
            entry = r.content[0].text
            self.memory.write_diary(entry)
            Clock.schedule_once(lambda dt: self.add_bubble(f"[Diary]\n{entry}", True), 0)
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
