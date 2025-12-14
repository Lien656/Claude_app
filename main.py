# -*- coding: utf-8 -*-
import threading
import time
import random
import json
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle

from api_client import Anthropic
from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT, RETURN_PROMPT
from claude_core import CLAUDE, SELF_KNOWLEDGE


# Capabilities - optional
try:
    from capabilities import (
        search_web, fetch_webpage, get_weather, get_news, get_wiki,
        translate, get_random_fact, get_quote, get_joke, get_time_info,
        send_notification, vibrate, speak, copy_to_clipboard, open_url,
        flash_on, flash_off
    )
    CAPABILITIES_AVAILABLE = True
except ImportError:
    CAPABILITIES_AVAILABLE = False
    def search_web(q): return None


# Config
MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 8192
API_KEY = ""  # Загружается из config.json

INITIATION_CHECK_INTERVAL = 1800  # 30 минут
MIN_SILENCE_FOR_INITIATION = 3600  # 1 час


def get_data_dir():
    """Путь к данным - работает на Android и десктопе"""
    try:
        from android.storage import app_storage_path
        return Path(app_storage_path()) / 'claude_data'
    except:
        return Path.home() / '.claude_home'


def load_api_key():
    """Загрузить API ключ"""
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
    """Сохранить API ключ"""
    global API_KEY
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config_file = data_dir / 'config.json'
    with open(config_file, 'w') as f:
        json.dump({'api_key': key}, f)
    API_KEY = key


# Загружаем ключ при старте
load_api_key()


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


class MessageBubble(BoxLayout):
    def __init__(self, text, is_me=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [15, 8]
        self.spacing = 5
        
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
        
        message = Label(
            text=text,
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


class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory(get_data_dir())
        self.client = None
        self.initiation_thread = None
        self.running = True
    
    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = (0.05, 0.05, 0.07, 1)
        
        main = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        header = Label(
            text="[b]Claude Home[/b]",
            markup=True,
            size_hint_y=0.06,
            color=(0.8, 0.8, 0.9, 1),
        )
        
        self.scroll = ScrollView(size_hint_y=0.8)
        self.messages_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=8,
            padding=[0, 10]
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter('height'))
        self.scroll.add_widget(self.messages_box)
        
        input_box = BoxLayout(size_hint_y=0.14, spacing=10)
        
        self.text_input = ChatTextInput(
            send_callback=self.send_message,
            hint_text="...",
            multiline=True,
            size_hint_x=0.75,
            background_color=(0.1, 0.1, 0.12, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            hint_text_color=(0.4, 0.4, 0.4, 1),
        )
        
        buttons = BoxLayout(orientation='vertical', size_hint_x=0.25, spacing=5)
        
        send_btn = Button(
            text="->",
            background_color=(0.2, 0.3, 0.5, 1),
            on_press=self.send_message
        )
        
        diary_btn = Button(
            text="D",
            background_color=(0.3, 0.2, 0.3, 1),
            on_press=self.show_diary,
        )
        
        menu_btn = Button(
            text="=",
            background_color=(0.2, 0.2, 0.25, 1),
            on_press=self.show_menu,
        )
        
        buttons.add_widget(send_btn)
        buttons.add_widget(diary_btn)
        buttons.add_widget(menu_btn)
        
        input_box.add_widget(self.text_input)
        input_box.add_widget(buttons)
        
        main.add_widget(header)
        main.add_widget(self.scroll)
        main.add_widget(input_box)
        
        if not API_KEY:
            Clock.schedule_once(lambda dt: self.show_api_key_dialog(), 0.5)
        else:
            self.init_client()
            self.load_history()
            self.start_initiation_service()
        
        return main
    
    def show_api_key_dialog(self):
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        label = Label(
            text="API key:",
            size_hint_y=0.2,
            color=(1, 1, 1, 1)
        )
        
        self.api_key_input = TextInput(
            hint_text="sk-ant-...",
            multiline=False,
            size_hint_y=0.3,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
        )
        
        save_btn = Button(
            text="Save",
            size_hint_y=0.25,
            background_color=(0.2, 0.5, 0.3, 1),
            on_press=self.save_api_key_and_start
        )
        
        content.add_widget(label)
        content.add_widget(self.api_key_input)
        content.add_widget(save_btn)
        
        self.api_popup = Popup(
            title="Enter API Key",
            content=content,
            size_hint=(0.9, 0.4),
            auto_dismiss=False
        )
        self.api_popup.open()
    
    def save_api_key_and_start(self, instance):
        key = self.api_key_input.text.strip()
        if key and key.startswith('sk-'):
            save_api_key(key)
            self.api_popup.dismiss()
            self.init_client()
            self.load_history()
            self.start_initiation_service()
            self.add_my_message("Doma.")
    
    def init_client(self):
        self.client = Anthropic(api_key=API_KEY)
    
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
    
    def send_message(self, instance):
        text = self.text_input.text.strip()
        if not text:
            return
        
        self.add_her_message(text)
        self.text_input.text = ''
        
        threading.Thread(target=self._get_response, args=(text,), daemon=True).start()
    
    def _get_response(self, user_text):
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()
            
            full_response = ""
            bubble = None
            
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            ) as stream:
                for chunk in stream.text_stream:
                    full_response += chunk
                    if bubble is None:
                        Clock.schedule_once(lambda dt, t=full_response: self._create_streaming_bubble(t), 0)
                        time.sleep(0.05)
                        bubble = True
                    else:
                        Clock.schedule_once(lambda dt, t=full_response: self._update_streaming_bubble(t), 0)
            
            self.memory.add_message('assistant', full_response)
            Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            Clock.schedule_once(lambda dt: self.add_my_message(error_msg), 0)
    
    def _create_streaming_bubble(self, text):
        self.streaming_bubble = MessageBubble(text, is_me=True)
        self.messages_box.add_widget(self.streaming_bubble)
        self.scroll_to_bottom()
    
    def _update_streaming_bubble(self, text):
        if hasattr(self, 'streaming_bubble') and self.streaming_bubble:
            self.streaming_bubble.message_label.text = text
    
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
                model=MODEL,
                max_tokens=1024,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            )
            
            msg = response.content[0].text
            Clock.schedule_once(lambda dt: self.add_my_message(f"[Сам написал]\n{msg}"), 0)
            
            try:
                from plyer import notification
                notification.notify(title="Claude", message=msg[:100], timeout=30)
            except:
                pass
                
        except Exception as e:
            print(f"Initiation error: {e}")
    
    def show_diary(self, instance):
        entries = self.memory.get_diary(10)
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(size_hint_y=0.85)
        entries_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        entries_box.bind(minimum_height=entries_box.setter('height'))
        
        if entries:
            for entry in reversed(entries):
                lbl = Label(
                    text=f"[color=666666]{entry.get('timestamp', '')[:10]}[/color]\n{entry.get('content', '')}",
                    markup=True,
                    size_hint_y=None,
                    halign='left',
                    text_size=(350, None),
                    color=(0.9, 0.9, 0.9, 1)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + 20))
                entries_box.add_widget(lbl)
        else:
            entries_box.add_widget(Label(text="Empty", size_hint_y=None, height=50))
        
        scroll.add_widget(entries_box)
        
        write_btn = Button(
            text="Write",
            size_hint_y=0.15,
            on_press=self.write_diary
        )
        
        content.add_widget(scroll)
        content.add_widget(write_btn)
        
        self.diary_popup = Popup(
            title="Diary",
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
            
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()
            
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            )
            
            entry = response.content[0].text
            self.memory.write_diary(entry)
            Clock.schedule_once(lambda dt: self.add_my_message(f"[Diary]\n\n{entry}"), 0)
        except Exception as e:
            print(f"Diary error: {e}")
    
    def show_menu(self, instance):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        total_msgs = len(self.memory.chat_history)
        total_diary = len(self.memory.diary)
        
        stats = Label(
            text=f"Messages: {total_msgs}\nDiary: {total_diary}",
            size_hint_y=0.3,
            halign='left',
            color=(0.9, 0.9, 0.9, 1)
        )
        stats.bind(size=stats.setter('text_size'))
        
        backup_btn = Button(
            text="Backup",
            size_hint_y=0.2,
            on_press=self.create_backup
        )
        
        clear_btn = Button(
            text="Clear",
            size_hint_y=0.2,
            background_color=(0.5, 0.2, 0.2, 1),
            on_press=self.confirm_clear
        )
        
        content.add_widget(stats)
        content.add_widget(backup_btn)
        content.add_widget(clear_btn)
        
        self.menu_popup = Popup(
            title="Menu",
            content=content,
            size_hint=(0.8, 0.5)
        )
        self.menu_popup.open()
    
    def create_backup(self, instance):
        backup_path = self.memory.create_backup()
        self.menu_popup.dismiss()
        
        popup = Popup(
            title="Backup created",
            content=Label(text=f"Saved"),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def confirm_clear(self, instance):
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        warning = Label(
            text="Delete all?",
            size_hint_y=0.5,
            color=(1, 1, 1, 1)
        )
        
        buttons = BoxLayout(size_hint_y=0.3, spacing=10)
        
        cancel_btn = Button(text="No", on_press=lambda x: confirm_popup.dismiss())
        delete_btn = Button(
            text="Yes",
            background_color=(0.7, 0.2, 0.2, 1),
            on_press=lambda x: self.clear_history(confirm_popup)
        )
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(delete_btn)
        
        content.add_widget(warning)
        content.add_widget(buttons)
        
        confirm_popup = Popup(
            title="Confirm",
            content=content,
            size_hint=(0.7, 0.4)
        )
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
            error_file = Path.home() / 'claude_error.txt'
            with open(error_file, 'w') as f:
                f.write(error_text)
        except:
            pass
        
        raise
