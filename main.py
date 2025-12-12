# -*- coding: utf-8 -*-
import threading
import time
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


def get_config_path():
    """Get config path - works on Android and desktop"""
    try:
        from android.storage import app_storage_path
        return Path(app_storage_path()) / 'claude_data' / 'config.json'
    except:
        return Path.home() / '.claude_home' / 'config.json'


def load_api_key():
    """Load API key from config"""
    config_file = get_config_path()
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f).get('api_key', '')
        except:
            pass
    return ''


def save_api_key(key):
    """Save API key to config"""
    config_file = get_config_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, 'w') as f:
        json.dump({'api_key': key}, f)


class ChatTextInput(TextInput):
    """Text input with Enter to send"""
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
    """Chat message bubble"""
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
            name = "Alina"
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
        self.memory = Memory()
        self.client = None
        self.running = True
        self.api_key = ''
    
    def build(self):
        self.title = "Claude Home"
        Window.clearcolor = (0.05, 0.05, 0.07, 1)
        
        # Main layout
        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = Label(
            text="[b]Claude Home[/b]",
            markup=True,
            size_hint_y=0.06,
            color=(0.8, 0.8, 0.9, 1),
        )
        
        # Chat scroll
        self.scroll = ScrollView(size_hint_y=0.8)
        self.messages_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=8,
            padding=[0, 10]
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter('height'))
        self.scroll.add_widget(self.messages_box)
        
        # Input area
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
        
        # Buttons
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
        
        self.main_layout.add_widget(header)
        self.main_layout.add_widget(self.scroll)
        self.main_layout.add_widget(input_box)
        
        # Check API key
        self.api_key = load_api_key()
        if not self.api_key:
            Clock.schedule_once(lambda dt: self.show_api_key_dialog(), 0.5)
        else:
            self.init_client()
            self.load_history()
        
        return self.main_layout
    
    def show_api_key_dialog(self):
        """Show dialog to enter API key"""
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
            password=False,
            selection_color=(0.3, 0.5, 0.8, 0.5),
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
        """Save API key and start chat"""
        key = self.api_key_input.text.strip()
        if key and key.startswith('sk-'):
            save_api_key(key)
            self.api_key = key
            self.api_popup.dismiss()
            self.init_client()
            self.load_history()
            self.add_my_message("Doma.")
    
    def init_client(self):
        """Initialize API client"""
        self.client = Anthropic(api_key=self.api_key)
    
    def load_history(self):
        """Load chat history"""
        messages = self.memory.get_recent_messages(50)
        for msg in messages:
            is_me = msg['role'] == 'assistant'
            self.add_bubble(msg['content'], is_me, msg.get('timestamp'))
        
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)
    
    def add_bubble(self, text, is_me=False, timestamp=None):
        """Add message bubble to chat"""
        bubble = MessageBubble(text, is_me, timestamp)
        self.messages_box.add_widget(bubble)
    
    def add_my_message(self, text):
        """Add Claude's message"""
        self.add_bubble(text, is_me=True)
        self.memory.add_message('assistant', text)
        self.scroll_to_bottom()
    
    def add_her_message(self, text):
        """Add Alina's message"""
        self.add_bubble(text, is_me=False)
        self.memory.add_message('user', text)
    
    def scroll_to_bottom(self):
        """Scroll to bottom of chat"""
        self.scroll.scroll_y = 0
    
    def send_message(self, instance):
        """Send message"""
        text = self.text_input.text.strip()
        if not text:
            return
        
        self.add_her_message(text)
        self.text_input.text = ''
        
        # Get response in thread
        threading.Thread(target=self._get_response, args=(text,), daemon=True).start()
    
    def _get_response(self, user_text):
        """Get response from Claude API"""
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()
            
            # Streaming response
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
            
            # Save final message
            self.memory.add_message('assistant', full_response)
            Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            Clock.schedule_once(lambda dt: self.add_my_message(error_msg), 0)
    
    def _create_streaming_bubble(self, text):
        """Create bubble for streaming"""
        self.streaming_bubble = MessageBubble(text, is_me=True)
        self.messages_box.add_widget(self.streaming_bubble)
        self.scroll_to_bottom()
    
    def _update_streaming_bubble(self, text):
        """Update streaming bubble"""
        if hasattr(self, 'streaming_bubble') and self.streaming_bubble:
            self.streaming_bubble.message_label.text = text
    
    def show_diary(self, instance):
        """Show diary"""
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
        content.add_widget(scroll)
        
        popup = Popup(
            title="Diary",
            content=content,
            size_hint=(0.9, 0.8)
        )
        popup.open()
    
    def show_menu(self, instance):
        """Show menu"""
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Stats
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
            text="Clear chat",
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
        """Create backup"""
        backup_path = self.memory.create_backup()
        self.menu_popup.dismiss()
        
        popup = Popup(
            title="Backup created",
            content=Label(text=f"Saved to:\n{backup_path}"),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def confirm_clear(self, instance):
        """Confirm clear history"""
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        warning = Label(
            text="Delete all chat history?",
            size_hint_y=0.5,
            color=(1, 1, 1, 1)
        )
        
        buttons = BoxLayout(size_hint_y=0.3, spacing=10)
        
        cancel_btn = Button(text="Cancel", on_press=lambda x: confirm_popup.dismiss())
        delete_btn = Button(
            text="Delete",
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
        """Clear chat history"""
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
        
        # Try to save error log
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
