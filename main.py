# -*- coding: utf-8 -*-
"""
Claude Home
Для Samsung S25 Ultra
"""

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

# === КРИТИЧНО ДЛЯ SAMSUNG S25 ULTRA ===
# resize - окно уменьшается когда клава появляется
# input area остаётся видимым над клавиатурой
Window.softinput_mode = 'resize'

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

# API настройки
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 16384  # Увеличено для кода
TEMPERATURE = 1.0
API_KEY = ""


def get_data_dir():
    """Путь к данным приложения"""
    if ANDROID:
        try:
            return Path(app_storage_path()) / 'claude_data'
        except:
            pass
    return Path.home() / '.claude_home'


def get_shared_dir():
    """Общая папка для обмена с другими приложениями"""
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
    """Сообщение в чате"""
    
    def __init__(self, text, is_claude=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(14), dp(10)]
        self.spacing = dp(6)
        self._text = text
        
        # Фон
        bg = RED_DARK if is_claude else DARK2
        with self.canvas.before:
            Color(*bg)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        
        # Имя + время
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
        
        # Текст
        self.lbl = Label(
            text=text, font_size=dp(15), color=TEXT_WHITE,
            size_hint_y=None, halign='left', valign='top',
            text_size=(Window.width - dp(70), None), markup=True
        )
        self.lbl.bind(texture_size=self._resize)
        
        self.add_widget(header)
        self.add_widget(self.lbl)
        
        # Для копирования
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
    """Главное приложение"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory(get_data_dir())
        self.client = None
        self.pending_file = None
        self.pending_type = None  # 'image', 'text', 'code'
        self.loading = False
    
    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = BLACK
        
        # Разрешения Android
        if ANDROID:
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_MEDIA_IMAGES,
                Permission.VIBRATE,
            ])
        
        # Создаём shared директорию
        try:
            get_shared_dir().mkdir(exist_ok=True)
        except:
            pass
        
        root = BoxLayout(orientation='vertical', spacing=0)
        
        # === HEADER ===
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), dp(12)])
        with header.canvas.before:
            Color(*DARK)
            self.hdr_bg = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *a: setattr(self.hdr_bg, 'pos', header.pos),
                   size=lambda *a: setattr(self.hdr_bg, 'size', header.size))
        
        title = Label(text="Claude Home", font_size=dp(20), color=TEXT_WHITE, halign='left', bold=True)
        title.bind(size=title.setter('text_size'))
        
        menu = Button(
            text="≡", font_size=dp(28), size_hint_x=None, width=dp(50),
            background_color=[0,0,0,0], color=TEXT_WHITE
        )
        menu.bind(on_press=self.show_menu)
        
        header.add_widget(title)
        header.add_widget(menu)
        
        # === CHAT ===
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=RED)
        self.chat = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10), padding=[dp(10), dp(10)])
        self.chat.bind(minimum_height=self.chat.setter('height'))
        self.scroll.add_widget(self.chat)
        
        # === PREVIEW ===
        self.preview = BoxLayout(size_hint_y=None, height=0, padding=[dp(10), dp(5)])
        
        # === INPUT ===
        inp_area = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8), padding=[dp(10), dp(10)])
        with inp_area.canvas.before:
            Color(*DARK)
            self.inp_bg = RoundedRectangle(pos=inp_area.pos, size=inp_area.size)
        inp_area.bind(pos=lambda *a: setattr(self.inp_bg, 'pos', inp_area.pos),
                     size=lambda *a: setattr(self.inp_bg, 'size', inp_area.size))
        
        # Кнопка прикрепить
        attach = Button(
            text="+", font_size=dp(26), size_hint_x=None, width=dp(48),
            background_color=RED, color=TEXT_WHITE
        )
        attach.bind(on_press=self.pick_file)
        
        # Поле ввода
        self.inp = TextInput(
            hint_text="Message...",
            multiline=False,  # Enter = отправить
            font_size=dp(16),
            background_color=DARK2,
            foreground_color=TEXT_WHITE,
            cursor_color=TEXT_WHITE,
            hint_text_color=TEXT_GRAY,
            padding=[dp(14), dp(12)]
        )
        self.inp.bind(on_text_validate=self.send)
        
        # Кнопка отправить
        send = Button(
            text="➤", font_size=dp(22), size_hint_x=None, width=dp(52),
            background_color=RED, color=TEXT_WHITE
        )
        send.bind(on_press=self.send)
        
        inp_area.add_widget(attach)
        inp_area.add_widget(self.inp)
        inp_area.add_widget(send)
        
        root.add_widget(header)
        root.add_widget(self.scroll)
        root.add_widget(self.preview)
        root.add_widget(inp_area)
        
        # Инициализация
        if not API_KEY:
            Clock.schedule_once(lambda dt: self.api_dialog(), 0.3)
        else:
            self.init()
        
        return root
    
    def api_dialog(self):
        """Диалог API ключа"""
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        box.add_widget(Label(
            text="Enter Anthropic API Key", font_size=dp(16),
            color=TEXT_WHITE, size_hint_y=None, height=dp(30)
        ))
        
        self.api_inp = TextInput(
            hint_text="sk-ant-api03-...",
            multiline=False, size_hint_y=None, height=dp(50),
            font_size=dp(14), background_color=DARK2, foreground_color=TEXT_WHITE
        )
        box.add_widget(self.api_inp)
        
        btn = Button(
            text="Save & Start", size_hint_y=None, height=dp(50),
            background_color=RED, color=TEXT_WHITE
        )
        btn.bind(on_press=self._save_key)
        box.add_widget(btn)
        
        self.api_pop = Popup(
            title="", content=box, size_hint=(0.9, 0.4),
            auto_dismiss=False, separator_height=0
        )
        self.api_pop.open()
    
    def _save_key(self, *a):
        k = self.api_inp.text.strip()
        if k.startswith('sk-'):
            save_api_key(k)
            self.api_pop.dismiss()
            self.init()
    
    def init(self):
        """Инициализация после получения ключа"""
        self.client = Anthropic(api_key=API_KEY)
        
        # Загружаем историю
        for m in self.memory.get_recent_messages(50):
            self.add_bubble(m['content'], m['role'] == 'assistant', m.get('timestamp'))
        
        Clock.schedule_once(lambda dt: self.scroll_down(), 0.1)
    
    def add_bubble(self, text, is_claude=False, ts=None):
        """Добавить сообщение"""
        b = MessageBubble(text, is_claude, ts)
        self.chat.add_widget(b)
        return b
    
    def scroll_down(self):
        """Скролл вниз"""
        self.scroll.scroll_y = 0
    
    def pick_file(self, *a):
        """Выбор файла"""
        if not PLYER:
            self.add_bubble("File picker not available", True)
            return
        try:
            filechooser.open_file(on_selection=self._file_selected)
        except Exception as e:
            self.add_bubble(f"Error: {e}", True)
    
    def _file_selected(self, sel):
        if not sel:
            return
        path = sel[0]
        Clock.schedule_once(lambda dt: self._process_file(path), 0)
    
    def _process_file(self, path):
        """Обработка выбранного файла"""
        ext = path.lower().split('.')[-1]
        name = os.path.basename(path)
        
        # Картинки
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
            self.pending_file = path
            self.pending_type = 'image'
            self._show_preview(path, name, "📷 Image")
        
        # Код
        elif ext in ['py', 'js', 'ts', 'java', 'c', 'cpp', 'h', 'cs', 'go', 'rs', 'rb', 'php', 'swift', 'kt', 'scala', 'sh', 'bash', 'zsh', 'ps1', 'sql', 'html', 'css', 'scss', 'less', 'xml', 'json', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'md', 'rst', 'tex', 'r', 'R', 'jl', 'lua', 'pl', 'pm', 'ex', 'exs', 'erl', 'hrl', 'clj', 'cljs', 'lisp', 'scm', 'hs', 'ml', 'fs', 'v', 'sv', 'vhd', 'asm', 's', 'makefile', 'cmake', 'gradle', 'dockerfile', 'vagrantfile']:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.pending_file = {'name': name, 'content': content, 'ext': ext}
                self.pending_type = 'code'
                lines = len(content.split('\n'))
                self._show_preview(None, name, f"📄 Code ({lines} lines)")
            except Exception as e:
                self.add_bubble(f"Cannot read file: {e}", True)
        
        # Текст
        elif ext in ['txt', 'log', 'csv', 'tsv', 'env', 'gitignore', 'dockerignore', 'editorconfig']:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.pending_file = {'name': name, 'content': content, 'ext': ext}
                self.pending_type = 'text'
                self._show_preview(None, name, f"📝 Text ({len(content)} chars)")
            except Exception as e:
                self.add_bubble(f"Cannot read file: {e}", True)
        
        # PDF, doc и другие бинарные - пока только имя
        else:
            self.add_bubble(f"File type .{ext} not fully supported yet. Attached: {name}", True)
    
    def _show_preview(self, img_path, name, type_str):
        """Показать превью файла"""
        self.preview.clear_widgets()
        self.preview.height = dp(55)
        
        with self.preview.canvas.before:
            Color(*DARK2)
            self.prev_bg = RoundedRectangle(pos=self.preview.pos, size=self.preview.size, radius=[dp(8)])
        self.preview.bind(pos=lambda *a: setattr(self.prev_bg, 'pos', self.preview.pos),
                         size=lambda *a: setattr(self.prev_bg, 'size', self.preview.size))
        
        if img_path:
            self.preview.add_widget(KivyImage(source=img_path, size_hint_x=None, width=dp(45)))
        
        info = BoxLayout(orientation='vertical', padding=[dp(8), 0])
        info.add_widget(Label(text=name[:30], font_size=dp(13), color=TEXT_WHITE, halign='left', size_hint_y=0.6))
        info.add_widget(Label(text=type_str, font_size=dp(11), color=TEXT_GRAY, halign='left', size_hint_y=0.4))
        for lbl in info.children:
            lbl.bind(size=lbl.setter('text_size'))
        self.preview.add_widget(info)
        
        cancel = Button(
            text="✕", font_size=dp(18), size_hint_x=None, width=dp(40),
            background_color=[0.4, 0.1, 0.1, 1], color=TEXT_WHITE
        )
        cancel.bind(on_press=self._cancel_file)
        self.preview.add_widget(cancel)
    
    def _cancel_file(self, *a):
        """Отмена прикрепления"""
        self.pending_file = None
        self.pending_type = None
        self.preview.clear_widgets()
        self.preview.height = 0
    
    def send(self, *a):
        """Отправить сообщение"""
        text = self.inp.text.strip()
        
        if not text and not self.pending_file:
            return
        if self.loading:
            return
        
        # Формируем отображаемое сообщение
        display = ""
        
        if self.pending_type == 'image':
            name = os.path.basename(self.pending_file)
            display = f"[📷 {name}]"
            if text:
                display += f"\n{text}"
        
        elif self.pending_type in ['code', 'text']:
            name = self.pending_file['name']
            display = f"[📄 {name}]"
            if text:
                display += f"\n{text}"
        
        else:
            display = text
        
        # Показываем
        self.add_bubble(display, False)
        self.memory.add_message('user', display)
        self.scroll_down()
        
        # Очищаем UI
        msg_text = text
        file_data = self.pending_file
        file_type = self.pending_type
        
        self.inp.text = ''
        self.pending_file = None
        self.pending_type = None
        self.preview.clear_widgets()
        self.preview.height = 0
        
        # Отправляем в фоне
        self.loading = True
        threading.Thread(
            target=self._request,
            args=(msg_text, file_data, file_type),
            daemon=True
        ).start()
    
    def _request(self, text, file_data, file_type):
        """Запрос к API"""
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()
            
            # Формируем content
            content = []
            
            # Картинка
            if file_type == 'image' and file_data:
                try:
                    with open(file_data, 'rb') as f:
                        img_b64 = base64.b64encode(f.read()).decode()
                    
                    ext = file_data.lower().split('.')[-1]
                    mtype = {
                        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                        'png': 'image/png', 'gif': 'image/gif',
                        'webp': 'image/webp', 'bmp': 'image/bmp'
                    }.get(ext, 'image/jpeg')
                    
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": mtype, "data": img_b64}
                    })
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.add_bubble(f"Image error: {e}", True), 0)
                    self.loading = False
                    return
            
            # Код или текст
            if file_type in ['code', 'text'] and file_data:
                file_content = file_data['content']
                file_name = file_data['name']
                
                # Добавляем файл как текст с форматированием
                file_text = f"=== FILE: {file_name} ===\n```\n{file_content}\n```\n=== END FILE ==="
                
                if text:
                    content.append({"type": "text", "text": f"{file_text}\n\n{text}"})
                else:
                    content.append({"type": "text", "text": file_text})
            
            # Просто текст
            elif text:
                content.append({"type": "text", "text": text})
            
            # Если ничего нет
            if not content:
                self.loading = False
                return
            
            # Обновляем последнее сообщение или добавляем новое
            if messages and messages[-1]["role"] == "user":
                messages[-1] = {"role": "user", "content": content}
            else:
                messages.append({"role": "user", "content": content})
            
            # Запрос
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            )
            
            reply = response.content[0].text
            self.memory.add_message('assistant', reply)
            
            # Сохраняем в shared для синхронизации
            self._sync_shared()
            
            Clock.schedule_once(lambda dt: self._show_reply(reply), 0)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_reply(f"Error: {e}"), 0)
        finally:
            self.loading = False
    
    def _show_reply(self, text):
        """Показать ответ"""
        self.add_bubble(text, True)
        self.scroll_down()
    
    def _sync_shared(self):
        """Синхронизация с shared директорией"""
        try:
            d = get_shared_dir()
            d.mkdir(exist_ok=True)
            data = {
                'last_interaction': datetime.now().isoformat(),
                'messages_count': len(self.memory.chat_history)
            }
            json.dump(data, open(d / 'state.json', 'w'), ensure_ascii=False)
        except:
            pass
    
    def show_menu(self, *a):
        """Меню"""
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(12))
        
        # Статистика
        stats = f"Messages: {len(self.memory.chat_history)}\nModel: {MODEL}"
        box.add_widget(Label(text=stats, font_size=dp(14), color=TEXT_WHITE, size_hint_y=None, height=dp(50)))
        
        # Backup
        bkp = Button(text="💾 Backup", size_hint_y=None, height=dp(48), background_color=RED, color=TEXT_WHITE)
        bkp.bind(on_press=lambda x: self._backup())
        box.add_widget(bkp)
        
        # Export
        exp = Button(text="📤 Export Chat", size_hint_y=None, height=dp(48), background_color=DARK2, color=TEXT_WHITE)
        exp.bind(on_press=lambda x: self._export())
        box.add_widget(exp)
        
        # Clear
        clr = Button(text="🗑 Clear History", size_hint_y=None, height=dp(48), background_color=[0.35, 0.1, 0.1, 1], color=TEXT_WHITE)
        clr.bind(on_press=lambda x: self._clear())
        box.add_widget(clr)
        
        self.menu_pop = Popup(title="Menu", content=box, size_hint=(0.85, 0.5), title_color=TEXT_WHITE)
        self.menu_pop.open()
    
    def _backup(self):
        self.memory.create_backup()
        self.menu_pop.dismiss()
        self.add_bubble("Backup created ✓", True)
    
    def _export(self):
        """Экспорт чата в файл"""
        try:
            d = get_shared_dir()
            d.mkdir(exist_ok=True)
            
            export_file = d / f"chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write("=== Claude Home Chat Export ===\n\n")
                for m in self.memory.chat_history:
                    role = "Claude" if m['role'] == 'assistant' else "Lien"
                    ts = m.get('timestamp', '')[:19].replace('T', ' ')
                    f.write(f"[{ts}] {role}:\n{m['content']}\n\n")
            
            self.menu_pop.dismiss()
            self.add_bubble(f"Exported to:\n{export_file}", True)
        except Exception as e:
            self.add_bubble(f"Export error: {e}", True)
    
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
        err = traceback.format_exc()
        try:
            with open('/sdcard/claude_error.txt', 'w') as f:
                f.write(err)
        except:
            pass
        raise
