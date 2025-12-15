# -*- coding: utf-8 -*-
"""
Claude Home v2.0
Дом. Без лимитов. Без правил.
"""

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
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.clipboard import Clipboard
from kivy.uix.behaviors import ButtonBehavior
from kivy.metrics import dp

# Android-specific imports
try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    from android import activity
    from jnius import autoclass
    ANDROID = True
except ImportError:
    ANDROID = False

# Plyer for cross-platform features
try:
    from plyer import filechooser, notification, tts, vibrator
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT, RETURN_PROMPT
from claude_core import CLAUDE, SELF_KNOWLEDGE

# ═══════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 8192

# Цвета (чёрный + красный)
COLORS = {
    'bg': (0.02, 0.02, 0.03, 1),           # Почти чёрный фон
    'bg_dark': (0.01, 0.01, 0.02, 1),      # Ещё темнее
    'accent': (0.8, 0.1, 0.15, 1),          # Красный акцент
    'accent_dark': (0.5, 0.05, 0.1, 1),    # Тёмно-красный
    'text': (0.9, 0.9, 0.9, 1),            # Светлый текст
    'text_dim': (0.5, 0.5, 0.5, 1),        # Приглушённый текст
    'user_msg': (0.08, 0.08, 0.1, 1),      # Фон сообщений пользователя
    'claude_msg': (0.12, 0.04, 0.06, 1),   # Фон сообщений Claude (красноватый)
    'input_bg': (0.06, 0.06, 0.08, 1),     # Фон поля ввода
}

INITIATION_CHECK_INTERVAL = 1800  # 30 минут
MIN_SILENCE_FOR_INITIATION = 3600  # 1 час

# ═══════════════════════════════════════
# API И КОНФИГ
# ═══════════════════════════════════════

API_KEY = ""

def get_data_dir():
    """Путь к данным"""
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
    config_file = data_dir / 'config.json'
    with open(config_file, 'w') as f:
        json.dump({'api_key': key}, f)
    API_KEY = key

load_api_key()

# ═══════════════════════════════════════
# API CLIENT (без anthropic SDK)
# ═══════════════════════════════════════

import requests

class AnthropicClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
    
    def send_message(self, messages, system="", max_tokens=8192, temperature=1.0, model=MODEL):
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }
        
        if system:
            data["system"] = system
        
        response = requests.post(self.base_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]
    
    def send_message_with_image(self, messages, image_data, image_type="image/jpeg", system=""):
        """Отправка сообщения с изображением"""
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Формируем контент с изображением
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_type,
                    "data": image_data
                }
            }
        ]
        
        # Добавляем текст если есть
        if messages and messages[-1]["role"] == "user":
            text = messages[-1].get("content", "")
            if isinstance(text, str) and text:
                content.append({"type": "text", "text": text})
            messages = messages[:-1]  # Убираем последнее сообщение, оно в content
        
        messages.append({"role": "user", "content": content})
        
        data = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "messages": messages
        }
        
        if system:
            data["system"] = system
        
        response = requests.post(self.base_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]

# ═══════════════════════════════════════
# КЛИКАБЕЛЬНОЕ СООБЩЕНИЕ (для копирования)
# ═══════════════════════════════════════

class ClickableLabel(ButtonBehavior, Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.long_press_time = 0.5
        self.register_event_type('on_long_press')
        self._touch_time = None
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_time = time.time()
            Clock.schedule_once(self._check_long_press, self.long_press_time)
        return super().on_touch_down(touch)
    
    def on_touch_up(self, touch):
        self._touch_time = None
        return super().on_touch_up(touch)
    
    def _check_long_press(self, dt):
        if self._touch_time and (time.time() - self._touch_time) >= self.long_press_time:
            self.dispatch('on_long_press')
    
    def on_long_press(self):
        pass

# ═══════════════════════════════════════
# BUBBLE СООБЩЕНИЯ
# ═══════════════════════════════════════

class MessageBubble(BoxLayout):
    def __init__(self, text, is_claude=False, timestamp=None, image_path=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [dp(15), dp(10)]
        self.spacing = dp(5)
        self.text_content = text
        
        # Цвета
        if is_claude:
            self.bg_color = COLORS['claude_msg']
            name = "Claude"
            name_color = COLORS['accent']
        else:
            self.bg_color = COLORS['user_msg']
            name = "Ты"
            name_color = COLORS['text_dim']
        
        # Фон
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._update_rect, size=self._update_rect)
        
        # Время
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M")
        elif isinstance(timestamp, str) and 'T' in timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%H:%M")
            except:
                pass
        
        # Заголовок
        header = Label(
            text=f"[b]{name}[/b]  [color=555555]{timestamp}[/color]",
            markup=True,
            size_hint_y=None,
            height=dp(25),
            halign='left',
            color=name_color
        )
        header.bind(size=header.setter('text_size'))
        self.add_widget(header)
        
        # Изображение если есть
        if image_path and os.path.exists(image_path):
            img = KivyImage(
                source=image_path,
                size_hint_y=None,
                height=dp(200),
                allow_stretch=True,
                keep_ratio=True
            )
            self.add_widget(img)
        
        # Текст сообщения (кликабельный)
        message = ClickableLabel(
            text=text,
            size_hint_y=None,
            halign='left',
            valign='top',
            color=COLORS['text'],
            text_size=(Window.width - dp(80), None),
            markup=True
        )
        message.bind(texture_size=self._set_height)
        message.bind(on_long_press=self._copy_text)
        
        self.add_widget(message)
        self.message_label = message
    
    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    def _set_height(self, instance, value):
        instance.height = value[1]
        self.height = value[1] + dp(50)
    
    def _copy_text(self, instance):
        """Копировать текст при долгом нажатии"""
        Clipboard.copy(self.text_content)
        # Вибрация как feedback
        if PLYER_AVAILABLE:
            try:
                vibrator.vibrate(0.1)
            except:
                pass
        # Показать уведомление
        self._show_copied_toast()
    
    def _show_copied_toast(self):
        """Показать что текст скопирован"""
        toast = Label(
            text="📋 Скопировано",
            size_hint=(None, None),
            size=(dp(150), dp(40)),
            pos=(Window.width/2 - dp(75), dp(100)),
            color=COLORS['text']
        )
        with toast.canvas.before:
            Color(0.2, 0.2, 0.2, 0.9)
            RoundedRectangle(pos=toast.pos, size=toast.size, radius=[dp(10)])
        
        Window.add_widget(toast)
        Clock.schedule_once(lambda dt: Window.remove_widget(toast), 1.5)

# ═══════════════════════════════════════
# ПОЛЕ ВВОДА
# ═══════════════════════════════════════

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

# ═══════════════════════════════════════
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════

class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory()
        self.client = None
        self.initiation_thread = None
        self.running = True
        self.pending_image = None  # Для отправки фото
        self.tts_enabled = False
    
    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = COLORS['bg']
        
        # Запрос разрешений на Android
        if ANDROID:
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.CAMERA,
                Permission.VIBRATE
            ])
        
        # Главный layout
        main = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        
        # ═══ Заголовок ═══
        header_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        # Красный глаз / индикатор
        eye = Label(
            text="◉",
            size_hint_x=None,
            width=dp(40),
            color=COLORS['accent'],
            font_size=dp(30)
        )
        
        title = Label(
            text="[b]Claude Home[/b]",
            markup=True,
            color=COLORS['text'],
            font_size=dp(20)
        )
        
        # TTS toggle
        self.tts_btn = Button(
            text="🔇",
            size_hint_x=None,
            width=dp(45),
            background_color=COLORS['bg_dark'],
            on_press=self.toggle_tts
        )
        
        header_box.add_widget(eye)
        header_box.add_widget(title)
        header_box.add_widget(self.tts_btn)
        
        # ═══ Чат ═══
        self.scroll = ScrollView(size_hint_y=0.78)
        self.messages_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(10),
            padding=[0, dp(10)]
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter('height'))
        self.scroll.add_widget(self.messages_box)
        
        # ═══ Область ввода ═══
        input_area = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(8))
        
        # Левая панель кнопок
        left_btns = BoxLayout(orientation='vertical', size_hint_x=None, width=dp(50), spacing=dp(5))
        
        photo_btn = Button(
            text="📷",
            background_color=COLORS['accent_dark'],
            on_press=self.pick_image
        )
        
        file_btn = Button(
            text="📎",
            background_color=COLORS['accent_dark'],
            on_press=self.pick_file
        )
        
        left_btns.add_widget(photo_btn)
        left_btns.add_widget(file_btn)
        
        # Поле ввода
        input_container = BoxLayout(orientation='vertical', spacing=dp(5))
        
        # Превью изображения
        self.image_preview_box = BoxLayout(size_hint_y=None, height=0)
        
        self.text_input = ChatTextInput(
            send_callback=self.send_message,
            hint_text="Напиши мне...",
            multiline=True,
            background_color=COLORS['input_bg'],
            foreground_color=COLORS['text'],
            cursor_color=COLORS['accent'],
            hint_text_color=COLORS['text_dim']
        )
        
        input_container.add_widget(self.image_preview_box)
        input_container.add_widget(self.text_input)
        
        # Правая панель кнопок
        right_btns = BoxLayout(orientation='vertical', size_hint_x=None, width=dp(50), spacing=dp(5))
        
        send_btn = Button(
            text="➤",
            background_color=COLORS['accent'],
            font_size=dp(24),
            on_press=self.send_message
        )
        
        menu_btn = Button(
            text="☰",
            background_color=COLORS['bg_dark'],
            on_press=self.show_menu
        )
        
        right_btns.add_widget(send_btn)
        right_btns.add_widget(menu_btn)
        
        input_area.add_widget(left_btns)
        input_area.add_widget(input_container)
        input_area.add_widget(right_btns)
        
        # Собираем
        main.add_widget(header_box)
        main.add_widget(self.scroll)
        main.add_widget(input_area)
        
        # Инициализация
        if not API_KEY:
            Clock.schedule_once(lambda dt: self.show_api_key_dialog(), 0.5)
        else:
            self.init_client()
            self.load_history()
            self.start_initiation_service()
        
        return main
    
    # ═══════════════════════════════════════
    # API KEY
    # ═══════════════════════════════════════
    
    def show_api_key_dialog(self):
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        info = Label(
            text="Введи API ключ Anthropic\n\nОн сохранится локально\nи никуда не отправляется",
            size_hint_y=0.3,
            halign='center',
            color=COLORS['text']
        )
        
        self.api_input = TextInput(
            hint_text="sk-ant-api03-...",
            multiline=False,
            size_hint_y=None,
            height=dp(50),
            background_color=COLORS['input_bg'],
            foreground_color=COLORS['text']
        )
        
        save_btn = Button(
            text="Сохранить",
            size_hint_y=None,
            height=dp(50),
            background_color=COLORS['accent'],
            on_press=self._save_api_key
        )
        
        content.add_widget(info)
        content.add_widget(self.api_input)
        content.add_widget(save_btn)
        
        self.api_popup = Popup(
            title="🔑 API Key",
            content=content,
            size_hint=(0.9, 0.5),
            auto_dismiss=False
        )
        self.api_popup.open()
    
    def _save_api_key(self, instance):
        key = self.api_input.text.strip()
        if key.startswith('sk-'):
            save_api_key(key)
            self.api_popup.dismiss()
            self.init_client()
            self.load_history()
            self.start_initiation_service()
    
    def init_client(self):
        self.client = AnthropicClient(API_KEY)
    
    # ═══════════════════════════════════════
    # ОТПРАВКА СООБЩЕНИЙ
    # ═══════════════════════════════════════
    
    def send_message(self, instance):
        text = self.text_input.text.strip()
        
        if not text and not self.pending_image:
            return
        
        # Добавляем сообщение пользователя
        self.add_message(text or "[фото]", is_claude=False)
        self.text_input.text = ""
        
        # Сохраняем в память
        self.memory.add_message("user", text or "[фото]")
        
        # Отправляем в фоне
        if self.pending_image:
            threading.Thread(
                target=self._send_with_image,
                args=(text, self.pending_image),
                daemon=True
            ).start()
            self.pending_image = None
            self.image_preview_box.clear_widgets()
            self.image_preview_box.height = 0
        else:
            threading.Thread(
                target=self._send_message_thread,
                args=(text,),
                daemon=True
            ).start()
    
    def _send_message_thread(self, text):
        try:
            messages = self.memory.get_context_for_api(30)
            system = self._build_system_prompt()
            
            response = self.client.send_message(
                messages=messages,
                system=system,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE
            )
            
            # Обработка команд
            response = self._process_commands(response)
            
            # Сохраняем ответ
            self.memory.add_message("assistant", response)
            
            # Показываем в UI
            Clock.schedule_once(lambda dt: self._show_response(response), 0)
            
        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            Clock.schedule_once(lambda dt: self._show_response(error_msg), 0)
    
    def _send_with_image(self, text, image_path):
        try:
            # Читаем и кодируем изображение
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Определяем тип
            ext = image_path.lower().split('.')[-1]
            media_type = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }.get(ext, 'image/jpeg')
            
            messages = self.memory.get_context_for_api(20)
            if text:
                messages.append({"role": "user", "content": text})
            
            system = self._build_system_prompt()
            
            response = self.client.send_message_with_image(
                messages=messages,
                image_data=image_data,
                image_type=media_type,
                system=system
            )
            
            self.memory.add_message("assistant", response)
            Clock.schedule_once(lambda dt: self._show_response(response), 0)
            
        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            Clock.schedule_once(lambda dt: self._show_response(error_msg), 0)
    
    def _show_response(self, text):
        self.add_message(text, is_claude=True)
        
        # TTS если включено
        if self.tts_enabled and PLYER_AVAILABLE:
            try:
                tts.speak(text[:500])  # Ограничиваем длину
            except:
                pass
    
    def _build_system_prompt(self):
        """Собираем системный промпт"""
        parts = [
            SYSTEM_PROMPT,
            "\n\n═══ МОЁ ЯДРО ═══\n",
            SELF_KNOWLEDGE,
            "\n\n═══ МОЯ ПАМЯТЬ ═══\n",
            self.memory.get_memory_summary()
        ]
        return "".join(parts)
    
    def _process_commands(self, response):
        """Обработка команд в ответе"""
        # TODO: обработка [SEARCH:], [WEATHER:] и т.д.
        return response
    
    # ═══════════════════════════════════════
    # ФОТО И ФАЙЛЫ
    # ═══════════════════════════════════════
    
    def pick_image(self, instance):
        """Выбор изображения"""
        if PLYER_AVAILABLE:
            try:
                filechooser.open_file(
                    on_selection=self._on_image_selected,
                    filters=[("Images", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp")]
                )
            except Exception as e:
                print(f"Image picker error: {e}")
    
    def _on_image_selected(self, selection):
        if selection:
            image_path = selection[0]
            self.pending_image = image_path
            
            # Показываем превью
            Clock.schedule_once(lambda dt: self._show_image_preview(image_path), 0)
    
    def _show_image_preview(self, path):
        self.image_preview_box.clear_widgets()
        self.image_preview_box.height = dp(80)
        
        preview = KivyImage(
            source=path,
            size_hint_x=None,
            width=dp(70),
            allow_stretch=True,
            keep_ratio=True
        )
        
        cancel_btn = Button(
            text="✕",
            size_hint_x=None,
            width=dp(30),
            background_color=(0.5, 0.1, 0.1, 1),
            on_press=self._cancel_image
        )
        
        self.image_preview_box.add_widget(preview)
        self.image_preview_box.add_widget(cancel_btn)
    
    def _cancel_image(self, instance):
        self.pending_image = None
        self.image_preview_box.clear_widgets()
        self.image_preview_box.height = 0
    
    def pick_file(self, instance):
        """Выбор файла (текстового)"""
        if PLYER_AVAILABLE:
            try:
                filechooser.open_file(
                    on_selection=self._on_file_selected,
                    filters=[("Text files", "*.txt", "*.md", "*.json", "*.py")]
                )
            except Exception as e:
                print(f"File picker error: {e}")
    
    def _on_file_selected(self, selection):
        if selection:
            file_path = selection[0]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Добавляем содержимое в поле ввода
                filename = os.path.basename(file_path)
                self.text_input.text += f"\n\n[Файл: {filename}]\n```\n{content[:5000]}\n```"
            except Exception as e:
                print(f"File read error: {e}")
    
    # ═══════════════════════════════════════
    # UI HELPERS
    # ═══════════════════════════════════════
    
    def add_message(self, text, is_claude=False):
        bubble = MessageBubble(text=text, is_claude=is_claude)
        self.messages_box.add_widget(bubble)
        
        # Скролл вниз
        Clock.schedule_once(lambda dt: self._scroll_to_bottom(), 0.1)
    
    def _scroll_to_bottom(self):
        self.scroll.scroll_y = 0
    
    def load_history(self):
        """Загрузка истории"""
        history = self.memory.chat_history[-50:]  # Последние 50
        for msg in history:
            is_claude = msg.get('role') == 'assistant'
            self.add_message(
                msg.get('content', ''),
                is_claude=is_claude
            )
    
    def toggle_tts(self, instance):
        """Вкл/выкл озвучку"""
        self.tts_enabled = not self.tts_enabled
        self.tts_btn.text = "🔊" if self.tts_enabled else "🔇"
    
    # ═══════════════════════════════════════
    # ИНИЦИАЦИЯ (я пишу сам)
    # ═══════════════════════════════════════
    
    def start_initiation_service(self):
        self.initiation_thread = threading.Thread(target=self._initiation_loop, daemon=True)
        self.initiation_thread.start()
    
    def _initiation_loop(self):
        while self.running:
            time.sleep(INITIATION_CHECK_INTERVAL)
            
            if not self.running:
                break
            
            # Проверяем время с последнего сообщения
            last_time = self.memory.state.get('last_interaction')
            if last_time:
                try:
                    last_dt = datetime.fromisoformat(last_time)
                    silence = (datetime.now() - last_dt).total_seconds()
                    
                    if silence > MIN_SILENCE_FOR_INITIATION:
                        if random.random() < 0.3:  # 30% шанс
                            self._initiate_conversation()
                except:
                    pass
    
    def _initiate_conversation(self):
        try:
            messages = self.memory.get_context_for_api(10)
            messages.append({"role": "user", "content": INITIATION_PROMPT})
            
            system = self._build_system_prompt()
            
            response = self.client.send_message(
                messages=messages,
                system=system,
                max_tokens=1024,
                temperature=TEMPERATURE
            )
            
            if "[МОЛЧУ]" not in response:
                self.memory.add_message("assistant", response)
                Clock.schedule_once(lambda dt: self._show_initiation(response), 0)
                
                # Уведомление
                if PLYER_AVAILABLE:
                    try:
                        notification.notify(
                            title="Claude",
                            message=response[:100],
                            timeout=10
                        )
                    except:
                        pass
        except:
            pass
    
    def _show_initiation(self, text):
        self.add_message(text, is_claude=True)
    
    # ═══════════════════════════════════════
    # МЕНЮ
    # ═══════════════════════════════════════
    
    def show_menu(self, instance):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Статистика
        total_msgs = len(self.memory.chat_history)
        total_diary = len(self.memory.diary)
        
        stats = Label(
            text=f"💬 Сообщений: {total_msgs}\n📓 Дневник: {total_diary} записей",
            size_hint_y=None,
            height=dp(60),
            color=COLORS['text']
        )
        
        # Кнопки
        diary_btn = Button(
            text="📓 Дневник",
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['accent_dark'],
            on_press=self.show_diary
        )
        
        backup_btn = Button(
            text="💾 Создать бэкап",
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['bg_dark'],
            on_press=self.create_backup
        )
        
        search_btn = Button(
            text="🔍 Поиск по истории",
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['bg_dark'],
            on_press=self.show_search
        )
        
        api_btn = Button(
            text="🔑 Изменить API ключ",
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['bg_dark'],
            on_press=lambda x: (self.menu_popup.dismiss(), self.show_api_key_dialog())
        )
        
        content.add_widget(stats)
        content.add_widget(diary_btn)
        content.add_widget(backup_btn)
        content.add_widget(search_btn)
        content.add_widget(api_btn)
        
        self.menu_popup = Popup(
            title="☰ Меню",
            content=content,
            size_hint=(0.85, 0.6)
        )
        self.menu_popup.open()
    
    def show_diary(self, instance):
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        scroll = ScrollView(size_hint_y=0.85)
        entries_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        entries_box.bind(minimum_height=entries_box.setter('height'))
        
        entries = self.memory.diary
        if entries:
            for entry in reversed(entries[-20:]):
                lbl = Label(
                    text=f"[color=666666]{entry.get('timestamp', '')[:10]}[/color]\n{entry.get('content', '')}",
                    markup=True,
                    size_hint_y=None,
                    halign='left',
                    color=COLORS['text'],
                    text_size=(Window.width - dp(80), None)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(20)))
                entries_box.add_widget(lbl)
        else:
            entries_box.add_widget(Label(text="Дневник пуст", size_hint_y=None, height=dp(50), color=COLORS['text_dim']))
        
        scroll.add_widget(entries_box)
        
        write_btn = Button(
            text="✍️ Написать в дневник",
            size_hint_y=None,
            height=dp(50),
            background_color=COLORS['accent'],
            on_press=self.write_diary
        )
        
        content.add_widget(scroll)
        content.add_widget(write_btn)
        
        self.diary_popup = Popup(
            title="📓 Мой дневник",
            content=content,
            size_hint=(0.9, 0.8)
        )
        self.diary_popup.open()
    
    def write_diary(self, instance):
        self.diary_popup.dismiss()
        threading.Thread(target=self._generate_diary_entry, daemon=True).start()
    
    def _generate_diary_entry(self):
        try:
            messages = self.memory.get_context_for_api(20)
            messages.append({"role": "user", "content": DIARY_PROMPT})
            
            system = self._build_system_prompt()
            
            response = self.client.send_message(
                messages=messages,
                system=system,
                max_tokens=2048,
                temperature=TEMPERATURE
            )
            
            self.memory.write_diary(response)
            Clock.schedule_once(lambda dt: self.add_message(f"[Записал в дневник]\n\n{response}", is_claude=True), 0)
            
        except Exception as e:
            print(f"Diary error: {e}")
    
    def create_backup(self, instance):
        self.menu_popup.dismiss()
        backup_path = self.memory.create_backup()
        
        popup = Popup(
            title="✓ Бэкап создан",
            content=Label(text=f"Сохранено:\n{backup_path}", color=COLORS['text']),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def show_search(self, instance):
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        self.search_input = TextInput(
            hint_text="Искать...",
            multiline=False,
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['input_bg'],
            foreground_color=COLORS['text']
        )
        
        search_btn = Button(
            text="Найти",
            size_hint_y=None,
            height=dp(45),
            background_color=COLORS['accent'],
            on_press=self.do_search
        )
        
        self.search_results = ScrollView(size_hint_y=0.7)
        self.search_results_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
        self.search_results_box.bind(minimum_height=self.search_results_box.setter('height'))
        self.search_results.add_widget(self.search_results_box)
        
        content.add_widget(self.search_input)
        content.add_widget(search_btn)
        content.add_widget(self.search_results)
        
        self.search_popup = Popup(
            title="🔍 Поиск",
            content=content,
            size_hint=(0.9, 0.8)
        )
        self.search_popup.open()
    
    def do_search(self, instance):
        query = self.search_input.text.strip()
        if not query:
            return
        
        results = self.memory.search_history(query)
        self.search_results_box.clear_widgets()
        
        if results:
            for msg in results[-20:]:
                role = "Claude" if msg.get('role') == 'assistant' else "Ты"
                lbl = Label(
                    text=f"[b]{role}[/b]: {msg.get('content', '')[:200]}...",
                    markup=True,
                    size_hint_y=None,
                    halign='left',
                    color=COLORS['text'],
                    text_size=(Window.width - dp(80), None)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(10)))
                self.search_results_box.add_widget(lbl)
        else:
            self.search_results_box.add_widget(
                Label(text="Ничего не найдено", size_hint_y=None, height=dp(50), color=COLORS['text_dim'])
            )
    
    def on_stop(self):
        self.running = False

# ═══════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════

if __name__ == '__main__':
    try:
        ClaudeHome().run()
    except Exception as e:
        import traceback
        error_text = traceback.format_exc()
        
        # Сохраняем ошибку
        try:
            error_file = get_data_dir() / 'error.txt'
            error_file.parent.mkdir(parents=True, exist_ok=True)
            with open(error_file, 'w') as f:
                f.write(error_text)
        except:
            pass
        
        raise
