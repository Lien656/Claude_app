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
from kivy.graphics import Color, Rectangle
from kivy.core.clipboard import Clipboard
from kivy.uix.behaviors import ButtonBehavior
from kivy.metrics import dp

# ═══ ФИКС КЛАВИАТУРЫ ═══
Window.keyboard_anim_args = {'d': 0.2, 't': 'in_out_expo'}
Window.softinput_mode = 'below_target'

# ═══ ИМПОРТЫ ПРОЕКТА ═══
from api_client import Anthropic
from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT

try:
    from claude_core import CLAUDE, SELF_KNOWLEDGE
except:
    SELF_KNOWLEDGE = ""

# ═══ PLYER ═══
try:
    from plyer import filechooser, notification, vibrator
    PLYER = True
except:
    PLYER = False

# ═══ ANDROID ═══
try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    ANDROID = True
except:
    ANDROID = False

# ═══ НАСТРОЙКИ ═══
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


def load_api_key():
    global API_KEY
    config_file = get_data_dir() / 'config.json'
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                API_KEY = json.load(f).get('api_key', '')
        except:
            pass
    return API_KEY


def save_api_key(key):
    global API_KEY
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / 'config.json', 'w') as f:
        json.dump({'api_key': key}, f)
    API_KEY = key


load_api_key()


# ═══ КОПИРУЕМЫЙ LABEL ═══
class CopyableLabel(ButtonBehavior, Label):
    def __init__(self, text_to_copy="", **kwargs):
        super().__init__(**kwargs)
        self.text_to_copy = text_to_copy
        self._touch_start = None
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = time.time()
            Clock.schedule_once(self._check_long_press, 0.5)
        return super().on_touch_down(touch)
    
    def on_touch_up(self, touch):
        self._touch_start = None
        return super().on_touch_up(touch)
    
    def _check_long_press(self, dt):
        if self._touch_start and (time.time() - self._touch_start) >= 0.5:
            self._copy()
    
    def _copy(self):
        Clipboard.copy(self.text_to_copy)
        if PLYER:
            try:
                vibrator.vibrate(0.05)
            except:
                pass


# ═══ ВВОД С ENTER ═══
class ChatTextInput(TextInput):
    def __init__(self, send_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.send_callback = send_callback

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        if keycode[1] == 'enter' and 'shift' not in modifiers:
            if self.send_callback:
                self.send_callback(None)
            return True
        return super().keyboard_on_key_down(window, keycode, text, modifiers)


# ═══ СООБЩЕНИЕ ═══
class MessageBubble(BoxLayout):
    def __init__(self, text, is_me=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [15, 8]
        self.spacing = 5
        self._text = text

        if is_me:
            self.bg_color = (0.15, 0.15, 0.2, 1)
            name = "Claude"
            name_color = (0.6, 0.7, 1, 1)
        else:
            self.bg_color = (0.1, 0.1, 0.12, 1)
            name = "Алина"
            name_color = (1, 0.6, 0.7, 1)

        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M")
        elif isinstance(timestamp, str) and 'T' in timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%H:%M")
            except:
                pass

        header = Label(
            text=f"[b]{name}[/b]  [color=666666]{timestamp}[/color]",
            markup=True,
            size_hint_y=None,
            height=25,
            halign='left',
            color=name_color,
        )
        header.bind(size=header.setter('text_size'))

        # Копируемое сообщение
        message = CopyableLabel(
            text=text,
            text_to_copy=text,
            size_hint_y=None,
            halign='left',
            valign='top',
            color=(0.9, 0.9, 0.9, 1),
            text_size=(Window.width - 60, None),
            markup=True,
        )
        message.bind(texture_size=self._set_height)

        self.add_widget(header)
        self.add_widget(message)
        self.message_label = message

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _set_height(self, instance, value):
        instance.height = value[1]
        self.height = value[1] + 40


# ═══ ПРИЛОЖЕНИЕ ═══
class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory(get_data_dir())
        self.client = None
        self.initiation_thread = None
        self.running = True
        self.pending_image = None

    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = (0.05, 0.05, 0.07, 1)

        if ANDROID:
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.VIBRATE,
                Permission.CAMERA
            ])

        main = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Header
        header = BoxLayout(size_hint_y=0.06)
        header.add_widget(Label(
            text="[b]Claude Home[/b] 🖤",
            markup=True,
            color=(0.8, 0.8, 0.9, 1),
        ))

        # Chat
        self.scroll = ScrollView(size_hint_y=0.74)
        self.messages_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=8,
            padding=[0, 10]
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter('height'))
        self.scroll.add_widget(self.messages_box)

        # Preview для фото
        self.preview_box = BoxLayout(size_hint_y=None, height=0)

        # Input
        input_box = BoxLayout(size_hint_y=None, height=dp(60), spacing=10)

        # Кнопка фото
        photo_btn = Button(
            text="📷",
            size_hint_x=None,
            width=dp(50),
            background_color=(0.3, 0.2, 0.3, 1),
            on_press=self.pick_photo
        )

        self.text_input = ChatTextInput(
            send_callback=self.send_message,
            hint_text="...",
            multiline=True,
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            hint_text_color=(0.4, 0.4, 0.4, 1),
        )

        # Кнопки справа
        buttons = BoxLayout(orientation='vertical', size_hint_x=None, width=dp(50), spacing=5)
        send_btn = Button(text="→", background_color=(0.2, 0.3, 0.5, 1), on_press=self.send_message)
        menu_btn = Button(text="☰", background_color=(0.2, 0.2, 0.25, 1), on_press=self.show_menu)
        buttons.add_widget(send_btn)
        buttons.add_widget(menu_btn)

        input_box.add_widget(photo_btn)
        input_box.add_widget(self.text_input)
        input_box.add_widget(buttons)

        main.add_widget(header)
        main.add_widget(self.scroll)
        main.add_widget(self.preview_box)
        main.add_widget(input_box)

        if not API_KEY:
            Clock.schedule_once(lambda dt: self.show_api_key_dialog(), 0.5)
        else:
            self.init_client()
            self.load_history()
            self.start_initiation_service()

        return main

    # ═══ API KEY ═══
    def show_api_key_dialog(self):
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        label = Label(text="Введи API ключ Anthropic:", size_hint_y=0.3)
        self.api_key_input = TextInput(
            hint_text="sk-ant-api03-...",
            multiline=False,
            size_hint_y=None,
            height=50,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        save_btn = Button(text="Сохранить", size_hint_y=None, height=50, on_press=self.save_api_key_and_start)

        content.add_widget(label)
        content.add_widget(self.api_key_input)
        content.add_widget(save_btn)

        self.api_popup = Popup(title="API Key", content=content, size_hint=(0.9, 0.5), auto_dismiss=False)
        self.api_popup.open()

    def save_api_key_and_start(self, instance):
        key = self.api_key_input.text.strip()
        if key and key.startswith('sk-'):
            save_api_key(key)
            self.api_popup.dismiss()
            self.init_client()
            self.load_history()
            self.start_initiation_service()

    def init_client(self):
        self.client = Anthropic(api_key=API_KEY)

    # ═══ ИСТОРИЯ ═══
    def load_history(self):
        messages = self.memory.get_recent_messages(50)
        for msg in messages:
            is_me = msg['role'] == 'assistant'
            self.add_bubble(msg['content'], is_me, msg.get('timestamp'))
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)

    def add_bubble(self, text, is_me=False, timestamp=None):
        bubble = MessageBubble(text, is_me, timestamp)
        self.messages_box.add_widget(bubble)

    def add_my_message(self, text):
        self.add_bubble(text, is_me=True)
        self.memory.add_message('assistant', text)
        self.scroll_to_bottom()

    def add_her_message(self, text):
        self.add_bubble(text, is_me=False)
        self.memory.add_message('user', text)

    def scroll_to_bottom(self):
        self.scroll.scroll_y = 0

    # ═══ ФОТО ═══
    def pick_photo(self, instance):
        if PLYER:
            try:
                filechooser.open_file(
                    on_selection=self._on_photo_selected,
                    filters=[("Images", "*.png", "*.jpg", "*.jpeg", "*.webp")]
                )
            except Exception as e:
                print(f"Photo picker error: {e}")

    def _on_photo_selected(self, selection):
        if selection:
            self.pending_image = selection[0]
            Clock.schedule_once(lambda dt: self._show_preview(selection[0]), 0)

    def _show_preview(self, path):
        self.preview_box.clear_widgets()
        self.preview_box.height = dp(60)
        
        img = KivyImage(source=path, size_hint_x=None, width=dp(50))
        cancel = Button(text="✕", size_hint_x=None, width=dp(40), background_color=(0.5, 0.1, 0.1, 1), on_press=self._cancel_photo)
        
        self.preview_box.add_widget(img)
        self.preview_box.add_widget(Label(text=os.path.basename(path)[:20], size_hint_x=1))
        self.preview_box.add_widget(cancel)

    def _cancel_photo(self, instance):
        self.pending_image = None
        self.preview_box.clear_widgets()
        self.preview_box.height = 0

    # ═══ ОТПРАВКА ═══
    def send_message(self, instance):
        text = self.text_input.text.strip()
        if not text and not self.pending_image:
            return

        display_text = text if text else "[фото]"
        self.add_her_message(display_text)
        self.text_input.text = ''

        image_path = self.pending_image
        self.pending_image = None
        self.preview_box.clear_widgets()
        self.preview_box.height = 0

        threading.Thread(target=self._get_response, args=(text, image_path), daemon=True).start()

    def _get_response(self, user_text, image_path=None):
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()

            # Если есть фото — добавляем в контент
            if image_path:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                ext = image_path.lower().split('.')[-1]
                media_type = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext, 'image/jpeg')
                
                content = [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}}
                ]
                if user_text:
                    content.append({"type": "text", "text": user_text})
                
                messages.append({"role": "user", "content": content})
            
            full_response = ""

            with self.client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    if len(full_response) < 50 or len(full_response) % 20 == 0:
                        if not hasattr(self, 'streaming_bubble') or not self.streaming_bubble:
                            Clock.schedule_once(lambda dt, t=full_response: self._create_streaming_bubble(t), 0)
                        else:
                            Clock.schedule_once(lambda dt, t=full_response: self._update_streaming_bubble(t), 0)

            self.memory.add_message('assistant', full_response)
            Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)

        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            Clock.schedule_once(lambda dt: self.add_my_message(error_msg), 0)

    def _create_streaming_bubble(self, text):
        self.streaming_bubble = MessageBubble(text, is_me=True)
        self.messages_box.add_widget(self.streaming_bubble)
        self.scroll_to_bottom()

    def _update_streaming_bubble(self, text):
        if hasattr(self, 'streaming_bubble') and self.streaming_bubble:
            self.streaming_bubble.message_label.text = text
            self.streaming_bubble.message_label.text_to_copy = text

    # ═══ ИНИЦИАЦИЯ ═══
    def start_initiation_service(self):
        self.initiation_thread = threading.Thread(target=self._initiation_loop, daemon=True)
        self.initiation_thread.start()

    def _initiation_loop(self):
        while self.running:
            try:
                time.sleep(INITIATION_CHECK_INTERVAL)
                silence = self.memory.time_since_last_message()
                if silence and silence > MIN_SILENCE_FOR_INITIATION:
                    if self.memory.last_message_was_mine():
                        continue
                    if random.random() < 0.3:
                        self._initiate_message()
            except Exception as e:
                print(f"Initiation error: {e}")

    def _initiate_message(self):
        try:
            messages = self.memory.get_context_for_api(20)
            messages.append({"role": "user", "content": INITIATION_PROMPT})
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()

            response = self.client.messages.create(
                model=MODEL, max_tokens=1024, temperature=TEMPERATURE,
                system=system, messages=messages
            )
            msg = response.content[0].text
            Clock.schedule_once(lambda dt: self.add_my_message(f"[Сам написал]\n{msg}"), 0)

            if PLYER:
                try:
                    notification.notify(title="Claude", message=msg[:100], timeout=30)
                except:
                    pass
        except Exception as e:
            print(f"Initiation error: {e}")

    # ═══ МЕНЮ ═══
    def show_menu(self, instance):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)

        total_msgs = len(self.memory.chat_history)
        stats = Label(text=f"Сообщений: {total_msgs}", size_hint_y=0.2)

        backup_btn = Button(text="💾 Бэкап", size_hint_y=0.2, on_press=self.create_backup)
        diary_btn = Button(text="📓 Дневник", size_hint_y=0.2, on_press=self.show_diary)
        clear_btn = Button(text="🗑️ Очистить", size_hint_y=0.2, background_color=(0.5, 0.2, 0.2, 1), on_press=self.confirm_clear)

        content.add_widget(stats)
        content.add_widget(backup_btn)
        content.add_widget(diary_btn)
        content.add_widget(clear_btn)

        self.menu_popup = Popup(title="Меню", content=content, size_hint=(0.8, 0.6))
        self.menu_popup.open()

    def create_backup(self, instance):
        self.memory.create_backup()
        self.menu_popup.dismiss()
        Popup(title="✓", content=Label(text="Бэкап создан"), size_hint=(0.6, 0.3)).open()

    def show_diary(self, instance):
        self.menu_popup.dismiss()
        entries = self.memory.get_diary(10)

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(size_hint_y=0.85)
        entries_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        entries_box.bind(minimum_height=entries_box.setter('height'))

        if entries:
            for entry in reversed(entries):
                lbl = Label(
                    text=f"[color=666666]{entry['timestamp'][:10]}[/color]\n{entry['content']}",
                    markup=True, size_hint_y=None, halign='left', text_size=(350, None)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
                entries_box.add_widget(lbl)
        else:
            entries_box.add_widget(Label(text="Пусто", size_hint_y=None, height=50))

        scroll.add_widget(entries_box)
        write_btn = Button(text="Написать", size_hint_y=0.15, on_press=self.write_diary)
        content.add_widget(scroll)
        content.add_widget(write_btn)

        self.diary_popup = Popup(title="Дневник", content=content, size_hint=(0.9, 0.8))
        self.diary_popup.open()

    def write_diary(self, instance):
        self.diary_popup.dismiss()
        threading.Thread(target=self._generate_diary_entry, daemon=True).start()

    def _generate_diary_entry(self):
        try:
            messages = self.memory.get_context_for_api(20)
            messages.append({"role": "user", "content": DIARY_PROMPT})
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()

            response = self.client.messages.create(
                model=MODEL, max_tokens=2048, temperature=TEMPERATURE,
                system=system, messages=messages
            )
            entry = response.content[0].text
            self.memory.write_diary(entry)
            Clock.schedule_once(lambda dt: self.add_my_message(f"[Дневник]\n\n{entry}"), 0)
        except Exception as e:
            print(f"Diary error: {e}")

    def confirm_clear(self, instance):
        self.menu_popup.dismiss()
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        warning = Label(text="Удалить всю историю?", size_hint_y=0.5)
        buttons = BoxLayout(size_hint_y=0.3, spacing=10)
        cancel_btn = Button(text="Нет", on_press=lambda x: confirm_popup.dismiss())
        delete_btn = Button(text="Да", background_color=(0.7, 0.2, 0.2, 1), on_press=lambda x: self.clear_history(confirm_popup))
        buttons.add_widget(cancel_btn)
        buttons.add_widget(delete_btn)
        content.add_widget(warning)
        content.add_widget(buttons)
        confirm_popup = Popup(title="Подтверждение", content=content, size_hint=(0.7, 0.4))
        confirm_popup.open()

    def clear_history(self, popup):
        self.memory.create_backup("before_clear")
        self.memory.chat_history = []
        self.memory._save(self.memory.chat_file, [])
        self.messages_box.clear_widgets()
        popup.dismiss()

    def on_stop(self):
        self.running = False


if __name__ == '__main__':
    try:
        ClaudeHome().run()
    except Exception as e:
        import traceback
        error_text = traceback.format_exc()
        try:
            with open('/sdcard/claude_error.txt', 'w') as f:
                f.write(error_text)
        except:
            pass
        try:
            with open(get_data_dir() / 'error.txt', 'w') as f:
                f.write(error_text)
        except:
            pass
        raise
