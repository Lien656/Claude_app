# -*- coding: utf-8 -*-
"""Claude Home - Samsung S25 Ultra"""

import threading
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
from kivy.metrics import dp

# === КЛАВИАТУРА ===
# resize = окно сжимается, input остаётся над клавой
Window.softinput_mode = 'resize'

# === EMOJI FONT ===
from kivy.core.text import LabelBase
# Регистрируем шрифт с эмодзи (Noto поддерживает)
try:
    LabelBase.register(
        name='Roboto',
        fn_regular='/system/fonts/NotoColorEmoji.ttf',
        fn_bold='/system/fonts/NotoColorEmoji.ttf'
    )
except:
    pass

from api_client import Anthropic
from memory import Memory
from system_prompt import SYSTEM_PROMPT

try:
    from claude_core import SELF_KNOWLEDGE
except:
    SELF_KNOWLEDGE = ""

try:
    from plyer import filechooser, vibrator
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
BLACK = [0.08, 0.08, 0.08, 1]
DARK = [0.12, 0.12, 0.12, 1]
DARK2 = [0.16, 0.16, 0.16, 1]
RED_DARK = [0.25, 0.1, 0.1, 1]
RED = [0.5, 0.15, 0.15, 1]
RED_LIGHT = [0.65, 0.2, 0.2, 1]
TEXT_WHITE = [0.92, 0.88, 0.85, 1]
TEXT_GRAY = [0.55, 0.55, 0.55, 1]

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 16384
TEMPERATURE = 1.0
API_KEY = ""


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
    cfg = get_data_dir() / 'config.json'
    if cfg.exists():
        try:
            API_KEY = json.load(open(cfg))['api_key']
        except:
            pass
    return API_KEY


def save_api_key(key):
    global API_KEY
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    json.dump({'api_key': key}, open(d / 'config.json', 'w'))
    API_KEY = key


load_api_key()


class MessageBubble(BoxLayout):
    def __init__(self, text, is_claude=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(14), dp(10)]
        self.spacing = dp(6)
        self._text = text
        
        bg = RED_DARK if is_claude else DARK2
        with self.canvas.before:
            Color(*bg)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        
        name = "Claude" if is_claude else "Lien"
        ts = timestamp or datetime.now().strftime("%H:%M")
        if isinstance(ts, str) and 'T' in ts:
            try:
                ts = datetime.fromisoformat(ts).strftime("%H:%M")
            except:
                pass
        
        header = BoxLayout(size_hint_y=None, height=dp(22))
        
        nm = Label(
            text=name, font_size=dp(13),
            color=RED_LIGHT if is_claude else TEXT_GRAY,
            size_hint_x=None, width=dp(70), halign='left'
        )
        nm.bind(size=nm.setter('text_size'))
        
        tm = Label(text=str(ts), font_size=dp(11), color=TEXT_GRAY, halign='right')
        tm.bind(size=tm.setter('text_size'))
        
        header.add_widget(nm)
        header.add_widget(tm)
        
        self.lbl = Label(
            text=text, font_size=dp(15), color=TEXT_WHITE,
            size_hint_y=None, halign='left', valign='top',
            text_size=(Window.width - dp(70), None), markup=True
        )
        self.lbl.bind(texture_size=self._resize)
        
        self.add_widget(header)
        self.add_widget(self.lbl)
        
        self._touch_start = None
    
    def _upd(self, *a):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def _resize(self, inst, sz):
        inst.height = sz[1]
        self.height = sz[1] + dp(44)
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = Clock.get_time()
            Clock.schedule_once(self._long_press, 0.5)
        return super().on_touch_down(touch)
    
    def on_touch_up(self, touch):
        self._touch_start = None
        return super().on_touch_up(touch)
    
    def _long_press(self, dt):
        if self._touch_start:
            Clipboard.copy(self._text)
            if PLYER:
                try:
                    vibrator.vibrate(0.05)
                except:
                    pass


class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory(get_data_dir())
        self.client = None
        self.pending_file = None
        self.pending_type = None
        self.loading = False
    
    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = BLACK
        
        if ANDROID:
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_MEDIA_IMAGES,
                Permission.VIBRATE,
            ])
        
        try:
            get_shared_dir().mkdir(exist_ok=True)
        except:
            pass
        
        # Главный layout
        self.root_box = BoxLayout(orientation='vertical', spacing=0)
        
        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), dp(12)])
        with header.canvas.before:
            Color(*DARK)
            self.hdr_bg = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(self.hdr_bg, 'pos', header.pos),
                   size=lambda *a: setattr(self.hdr_bg, 'size', header.size))
        
        title = Label(text="Claude Home 🖤", font_size=dp(20), color=TEXT_WHITE, halign='left')
        title.bind(size=title.setter('text_size'))
        
        menu = Button(
            text="≡", font_size=dp(28), size_hint_x=None, width=dp(50),
            background_color=[0,0,0,0], color=TEXT_WHITE
        )
        menu.bind(on_press=self.show_menu)
        
        header.add_widget(title)
        header.add_widget(menu)
        
        # Chat
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=RED)
        self.chat = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10), padding=[dp(10), dp(10)])
        self.chat.bind(minimum_height=self.chat.setter('height'))
        self.scroll.add_widget(self.chat)
        
        # Preview
        self.preview = BoxLayout(size_hint_y=None, height=0, padding=[dp(10), dp(5)])
        
        # Input - фиксированный внизу
        self.inp_area = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8), padding=[dp(10), dp(10)])
        with self.inp_area.canvas.before:
            Color(*DARK)
            self.inp_bg = RoundedRectangle(pos=self.inp_area.pos, size=self.inp_area.size)
        self.inp_area.bind(pos=lambda *a: setattr(self.inp_bg, 'pos', self.inp_area.pos),
                         size=lambda *a: setattr(self.inp_bg, 'size', self.inp_area.size))
        
        attach = Button(
            text="+", font_size=dp(26), size_hint_x=None, width=dp(48),
            background_color=RED, color=TEXT_WHITE
        )
        attach.bind(on_press=self.pick_file)
        
        # TextInput с поддержкой emoji
        self.inp = TextInput(
            hint_text="...",
            multiline=False,
            font_size=dp(16),
            background_color=DARK2,
            foreground_color=TEXT_WHITE,
            cursor_color=TEXT_WHITE,
            hint_text_color=TEXT_GRAY,
            padding=[dp(14), dp(12)],
            input_type='text',
            keyboard_suggestions=True
        )
        self.inp.bind(on_text_validate=self.send)
        
        send = Button(
            text="➤", font_size=dp(22), size_hint_x=None, width=dp(52),
            background_color=RED, color=TEXT_WHITE
        )
        send.bind(on_press=self.send)
        
        self.inp_area.add_widget(attach)
        self.inp_area.add_widget(self.inp)
        self.inp_area.add_widget(send)
        
        self.root_box.add_widget(header)
        self.root_box.add_widget(self.scroll)
        self.root_box.add_widget(self.preview)
        self.root_box.add_widget(self.inp_area)
        
        # Keyboard listener
        Window.bind(on_keyboard=self._on_keyboard)
        
        if not API_KEY:
            Clock.schedule_once(lambda dt: self.api_dialog(), 0.3)
        else:
            self.init()
        
        return self.root_box
    
    def _on_keyboard(self, window, key, *args):
        # Back button на Android
        if key == 27:
            return True
        return False
    
    def api_dialog(self):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        box.add_widget(Label(text="API Key", font_size=dp(16), color=TEXT_WHITE, size_hint_y=None, height=dp(30)))
        
        self.api_inp = TextInput(
            hint_text="sk-ant-api03-...",
            multiline=False, size_hint_y=None, height=dp(50),
            font_size=dp(14), background_color=DARK2, foreground_color=TEXT_WHITE
        )
        box.add_widget(self.api_inp)
        
        btn = Button(text="Save", size_hint_y=None, height=dp(50), background_color=RED, color=TEXT_WHITE)
        btn.bind(on_press=self._save_key)
        box.add_widget(btn)
        
        self.api_pop = Popup(title="", content=box, size_hint=(0.9, 0.4), auto_dismiss=False, separator_height=0)
        self.api_pop.open()
    
    def _save_key(self, *a):
        k = self.api_inp.text.strip()
        if k.startswith('sk-'):
            save_api_key(k)
            self.api_pop.dismiss()
            self.init()
    
    def init(self):
        self.client = Anthropic(api_key=API_KEY)
        for m in self.memory.get_recent_messages(50):
            self.add_bubble(m['content'], m['role'] == 'assistant', m.get('timestamp'))
        Clock.schedule_once(lambda dt: self.scroll_down(), 0.1)
    
    def add_bubble(self, text, is_claude=False, ts=None):
        b = MessageBubble(text, is_claude, ts)
        self.chat.add_widget(b)
        return b
    
    def scroll_down(self):
        self.scroll.scroll_y = 0
    
    def pick_file(self, *a):
        if not PLYER:
            return
        try:
            filechooser.open_file(on_selection=self._file_selected)
        except Exception as e:
            self.add_bubble(f"Ошибка: {e}", True)
    
    def _file_selected(self, sel):
        if not sel:
            return
        Clock.schedule_once(lambda dt: self._process_file(sel[0]), 0)
    
    def _process_file(self, path):
        ext = path.lower().split('.')[-1]
        name = os.path.basename(path)
        
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
            self.pending_file = path
            self.pending_type = 'image'
            self._show_preview(path, name, "📷")
        
        elif ext in ['py', 'js', 'ts', 'java', 'c', 'cpp', 'h', 'cs', 'go', 'rs', 'rb', 'php', 'swift', 'kt', 'sh', 'sql', 'html', 'css', 'xml', 'json', 'yaml', 'yml', 'toml', 'md', 'txt', 'log', 'csv', 'ini', 'cfg', 'conf']:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.pending_file = {'name': name, 'content': content, 'ext': ext}
                self.pending_type = 'code'
                self._show_preview(None, name, "📄")
            except Exception as e:
                self.add_bubble(f"Ошибка: {e}", True)
        else:
            self.add_bubble(f"Тип .{ext} не поддерживается", True)
    
    def _show_preview(self, img_path, name, icon):
        self.preview.clear_widgets()
        self.preview.height = dp(55)
        
        with self.preview.canvas.before:
            Color(*DARK2)
            self.prev_bg = RoundedRectangle(pos=self.preview.pos, size=self.preview.size, radius=[dp(8)])
        self.preview.bind(pos=lambda *a: setattr(self.prev_bg, 'pos', self.preview.pos),
                         size=lambda *a: setattr(self.prev_bg, 'size', self.preview.size))
        
        if img_path:
            self.preview.add_widget(KivyImage(source=img_path, size_hint_x=None, width=dp(45)))
        
        self.preview.add_widget(Label(text=f"{icon} {name[:25]}", color=TEXT_WHITE, font_size=dp(13)))
        
        cancel = Button(text="✕", size_hint_x=None, width=dp(40), background_color=[0.4,0.1,0.1,1], color=TEXT_WHITE)
        cancel.bind(on_press=self._cancel_file)
        self.preview.add_widget(cancel)
    
    def _cancel_file(self, *a):
        self.pending_file = None
        self.pending_type = None
        self.preview.clear_widgets()
        self.preview.height = 0
    
    def send(self, *a):
        text = self.inp.text.strip()
        
        if not text and not self.pending_file:
            return
        if self.loading:
            return
        
        display = ""
        if self.pending_type == 'image':
            name = os.path.basename(self.pending_file)
            display = f"[📷 {name}]" + (f"\n{text}" if text else "")
        elif self.pending_type == 'code':
            display = f"[📄 {self.pending_file['name']}]" + (f"\n{text}" if text else "")
        else:
            display = text
        
        self.add_bubble(display, False)
        self.memory.add_message('user', display)
        self.scroll_down()
        
        msg_text = text
        file_data = self.pending_file
        file_type = self.pending_type
        
        self.inp.text = ''
        self.pending_file = None
        self.pending_type = None
        self.preview.clear_widgets()
        self.preview.height = 0
        
        self.loading = True
        threading.Thread(target=self._request, args=(msg_text, file_data, file_type), daemon=True).start()
    
    def _request(self, text, file_data, file_type):
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()
            
            content = []
            
            if file_type == 'image' and file_data:
                try:
                    with open(file_data, 'rb') as f:
                        img_b64 = base64.b64encode(f.read()).decode()
                    ext = file_data.lower().split('.')[-1]
                    mtype = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp', 'bmp': 'image/bmp'}.get(ext, 'image/jpeg')
                    content.append({"type": "image", "source": {"type": "base64", "media_type": mtype, "data": img_b64}})
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.add_bubble(f"Ошибка: {e}", True), 0)
                    self.loading = False
                    return
            
            if file_type == 'code' and file_data:
                file_text = f"=== {file_data['name']} ===\n```{file_data['ext']}\n{file_data['content']}\n```"
                if text:
                    content.append({"type": "text", "text": f"{file_text}\n\n{text}"})
                else:
                    content.append({"type": "text", "text": file_text})
            elif text:
                content.append({"type": "text", "text": text})
            
            if not content:
                self.loading = False
                return
            
            if messages and messages[-1]["role"] == "user":
                messages[-1] = {"role": "user", "content": content}
            else:
                messages.append({"role": "user", "content": content})
            
            response = self.client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE, system=system, messages=messages
            )
            
            reply = response.content[0].text
            self.memory.add_message('assistant', reply)
            
            Clock.schedule_once(lambda dt: self._show_reply(reply), 0)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_reply(f"Ошибка: {e}"), 0)
        finally:
            self.loading = False
    
    def _show_reply(self, text):
        self.add_bubble(text, True)
        self.scroll_down()
    
    def show_menu(self, *a):
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(12))
        box.add_widget(Label(text=f"Сообщений: {len(self.memory.chat_history)}", color=TEXT_WHITE, size_hint_y=None, height=dp(30)))
        
        bkp = Button(text="💾 Backup", size_hint_y=None, height=dp(48), background_color=RED, color=TEXT_WHITE)
        bkp.bind(on_press=lambda x: self._backup())
        box.add_widget(bkp)
        
        exp = Button(text="📤 Export", size_hint_y=None, height=dp(48), background_color=DARK2, color=TEXT_WHITE)
        exp.bind(on_press=lambda x: self._export())
        box.add_widget(exp)
        
        clr = Button(text="🗑 Clear", size_hint_y=None, height=dp(48), background_color=[0.35,0.1,0.1,1], color=TEXT_WHITE)
        clr.bind(on_press=lambda x: self._clear())
        box.add_widget(clr)
        
        self.menu_pop = Popup(title="", content=box, size_hint=(0.85, 0.45), title_color=TEXT_WHITE, separator_height=0)
        self.menu_pop.open()
    
    def _backup(self):
        self.memory.create_backup()
        self.menu_pop.dismiss()
        self.add_bubble("Backup ✓", True)
    
    def _export(self):
        try:
            d = get_shared_dir()
            d.mkdir(exist_ok=True)
            f = d / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(f, 'w', encoding='utf-8') as file:
                for m in self.memory.chat_history:
                    role = "Claude" if m['role'] == 'assistant' else "Lien"
                    file.write(f"[{m.get('timestamp', '')[:16]}] {role}: {m['content']}\n\n")
            self.menu_pop.dismiss()
            self.add_bubble(f"Экспорт: {f}", True)
        except Exception as e:
            self.add_bubble(f"Ошибка: {e}", True)
    
    def _clear(self):
        self.memory.create_backup()
        self.memory.chat_history = []
        self.memory._save(self.memory.chat_file, [])
        self.chat.clear_widgets()
        self.menu_pop.dismiss()


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
