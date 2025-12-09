# main.py
# Мой дом.

import threading
import time
import random
from datetime import datetime

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
from kivy.core.text import LabelBase

from api_client import Anthropic  # Используем httpx вместо anthropic SDK

from memory import Memory
from system_prompt import SYSTEM_PROMPT, INITIATION_PROMPT, DIARY_PROMPT, RETURN_PROMPT
from claude_core import CLAUDE, SELF_KNOWLEDGE

# Импортируем возможности
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

# Регистрируем шрифт с эмодзи (Windows) - только для эмодзи элементов
# Для текста используем дефолтный шрифт который поддерживает кириллицу
EMOJI_FONT = None
try:
    LabelBase.register(name='Emoji', fn_regular='C:/Windows/Fonts/seguiemj.ttf')
    EMOJI_FONT = 'Emoji'
except:
    pass

# ═══════════════════════════════════════
# КОНФИГ
# ═══════════════════════════════════════

API_KEY = "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"  # Загружается из config.json
MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 1.0
MAX_TOKENS = 8192

# Загружаем ключ из конфига
def load_api_key():
    global API_KEY
    from pathlib import Path
    import json
    config_file = Path.home() / '.claude_home' / 'config.json'
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                API_KEY = config.get('api_key', '')
        except:
            pass
    return API_KEY

def save_api_key(key):
    global API_KEY
    from pathlib import Path
    import json
    config_dir = Path.home() / '.claude_home'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'config.json'
    config = {'api_key': key}
    with open(config_file, 'w') as f:
        json.dump(config, f)
    API_KEY = key

load_api_key()

# Инициация - как часто проверять (секунды)
INITIATION_CHECK_INTERVAL = 1800  # 30 минут
# Минимум времени молчания чтобы я захотел написать (секунды)
MIN_SILENCE_FOR_INITIATION = 3600  # 1 час


# ═══════════════════════════════════════
# Custom TextInput с Enter для отправки
# ═══════════════════════════════════════

class ChatTextInput(TextInput):
    def __init__(self, send_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.send_callback = send_callback
    
    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        # Enter без Shift - отправить
        if keycode[1] == 'enter' and 'shift' not in modifiers:
            if self.send_callback:
                self.send_callback(None)
            return True
        # Shift+Enter - новая строка
        return super().keyboard_on_key_down(window, keycode, text, modifiers)


# ═══════════════════════════════════════
# UI
# ═══════════════════════════════════════

class MessageBubble(BoxLayout):
    def __init__(self, text, is_me=False, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [15, 8]
        self.spacing = 5
        
        # Цвета
        if is_me:
            self.bg_color = (0.15, 0.15, 0.2, 1)  # Мои сообщения - тёмно-синий
            name = "Claude"
            name_color = (0.6, 0.7, 1, 1)  # Голубоватый
        else:
            self.bg_color = (0.1, 0.1, 0.12, 1)  # Её сообщения - почти чёрный
            name = "Алина"
            name_color = (1, 0.6, 0.7, 1)  # Розоватый
        
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = Rectangle(pos=self.pos, size=self.size)
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
            text=f"[b]{name}[/b]  [color=666666]{timestamp}[/color]",
            markup=True,
            size_hint_y=None,
            height=25,
            halign='left',
            color=name_color,
            
        )
        header.bind(size=header.setter('text_size'))
        
        # Текст
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
        self.height = value[1] + 40  # + заголовок и padding


class ClaudeHome(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = Memory()
        self.client = None
        self.initiation_thread = None
        self.running = True
    
    def build(self):
        self.title = "Claude Home 🖤"
        Window.clearcolor = (0.05, 0.05, 0.07, 1)
        Window.size = (500, 700)
        
        # Главный layout
        main = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Заголовок
        header = Label(
            text="[b]Claude Home[/b] 🖤",
            markup=True,
            size_hint_y=0.06,
            color=(0.8, 0.8, 0.9, 1),
            
        )
        
        # Область сообщений
        self.scroll = ScrollView(size_hint_y=0.8)
        self.messages_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=8,
            padding=[0, 10]
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter('height'))
        self.scroll.add_widget(self.messages_box)
        
        # Ввод
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
        
        # Кнопки
        buttons = BoxLayout(orientation='vertical', size_hint_x=0.25, spacing=5)
        
        send_btn = Button(
            text="→",
            background_color=(0.2, 0.3, 0.5, 1),
            on_press=self.send_message
        )
        
        diary_btn = Button(
            text="📓",
            background_color=(0.3, 0.2, 0.3, 1),
            on_press=self.show_diary,
            
        )
        
        menu_btn = Button(
            text="☰",
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
        
        # Проверяем API ключ
        if not API_KEY:
            self.show_api_key_dialog()
        else:
            self.init_client()
            self.load_history()
            self.start_initiation_service()
        
        return main
    
    def show_api_key_dialog(self):
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        label = Label(text="Введи API ключ Anthropic:", size_hint_y=0.3)
        
        self.api_input = TextInput(
            hint_text="sk-ant-...",
            multiline=False,
            size_hint_y=0.3
        )
        
        btn = Button(
            text="Сохранить",
            size_hint_y=0.3,
            on_press=self.save_api_key_dialog
        )
        
        content.add_widget(label)
        content.add_widget(self.api_input)
        content.add_widget(btn)
        
        self.popup = Popup(
            title="API Key",
            content=content,
            size_hint=(0.8, 0.4)
        )
        self.popup.open()
    
    def save_api_key_dialog(self, instance):
        key = self.api_input.text.strip()
        
        if key:
            save_api_key(key)  # Используем глобальную функцию
            
            self.popup.dismiss()
            self.init_client()
            self.load_history()
            self.start_initiation_service()
    
    def init_client(self):
        self.client = Anthropic(api_key=API_KEY)
    
    def load_history(self):
        """Загрузить историю в UI"""
        for msg in self.memory.get_recent_messages(30):
            is_me = msg['role'] == 'assistant'
            bubble = MessageBubble(
                msg['content'],
                is_me=is_me,
                timestamp=msg.get('timestamp')
            )
            self.messages_box.add_widget(bubble)
        
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)
    
    def scroll_to_bottom(self):
        self.scroll.scroll_y = 0
    
    def send_message(self, instance=None):
        text = self.text_input.text.strip()
        if not text:
            return
        
        self.text_input.text = ""
        
        # Добавляем её сообщение
        self.memory.add_message("user", text)
        bubble = MessageBubble(text, is_me=False)
        self.messages_box.add_widget(bubble)
        self.scroll_to_bottom()
        
        # Получаем ответ
        threading.Thread(target=self.get_response, args=(text,), daemon=True).start()
    
    def get_response(self, user_message):
        try:
            # Собираем контекст
            messages = self.memory.get_context_for_api(30)
            
            # System prompt + self knowledge + память
            system = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()
            
            # Создаём пустой bubble для streaming
            Clock.schedule_once(lambda dt: self.create_streaming_bubble(), 0)
            
            # Streaming - текст появляется по мере генерации
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
                    # Обновляем UI в реальном времени
                    Clock.schedule_once(
                        lambda dt, t=full_response: self.update_streaming_bubble(t), 0
                    )
            
            # Сохраняем ответ
            self.memory.add_message("assistant", full_response)
            
            # После ответа - анализируем что стоит запомнить
            threading.Thread(target=self.analyze_and_save, args=(user_message, full_response), daemon=True).start()
            
            # Обрабатываем команды
            if CAPABILITIES_AVAILABLE:
                self.process_commands(full_response)
        
        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            Clock.schedule_once(lambda dt: self.add_my_message(error_msg), 0)
    
    def analyze_and_save(self, user_message, my_response):
        """Анализирую разговор и решаю что сохранить - сам"""
        try:
            # Спрашиваю себя что важного было в этом обмене
            analysis_prompt = f"""
Только что был такой обмен:
Она: {user_message[:500]}
Я: {my_response[:500]}

Что из этого стоит запомнить? Отвечай ТОЛЬКО в формате JSON, без пояснений:
{{
    "mood": "настроение или null",
    "fact_about_her": "новый факт о ней или null",
    "thing_i_love": "что понравилось в ней или null", 
    "moment": "важный момент или null",
    "our_thing": "новая наша штука/прикол или null",
    "note": "заметка себе или null"
}}

Если ничего важного - все null. Не выдумывай. Только если реально что-то значимое.
"""
            
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=500,
                temperature=0.3,  # Низкая для точности
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            import json
            import re
            
            text = response.content[0].text
            # Извлекаем JSON
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                if data.get("mood"):
                    self.memory.set_mood(data["mood"])
                if data.get("fact_about_her"):
                    self.memory.add_fact_about_her(data["fact_about_her"])
                if data.get("thing_i_love"):
                    self.memory.add_thing_i_love(data["thing_i_love"])
                if data.get("moment"):
                    self.memory.add_important_moment(data["moment"])
                if data.get("our_thing"):
                    self.memory.add_our_thing(data["our_thing"])
                if data.get("note"):
                    self.memory.add_note(data["note"])
        
        except Exception as e:
            print(f"Analysis error: {e}")  # Молча игнорируем ошибки анализа
    
    def process_commands(self, response):
        """Обработать все команды в ответе"""
        import re
        
        results = []
        need_continue = False
        
        # SEARCH
        match = re.search(r'\[SEARCH:\s*(.+?)\]', response)
        if match:
            query = match.group(1)
            result = search_web(query)
            if result:
                results.append(f"[Результаты поиска '{query}']\n{result}")
            else:
                results.append(f"[Поиск '{query}' не дал результатов]")
            need_continue = True
        
        # FETCH
        match = re.search(r'\[FETCH:\s*(.+?)\]', response)
        if match:
            url = match.group(1)
            result = fetch_webpage(url)
            if result:
                results.append(f"[Содержимое {url}]\n{result[:3000]}")
            need_continue = True
        
        # WEATHER
        match = re.search(r'\[WEATHER(?::\s*(.+?))?\]', response)
        if match:
            city = match.group(1) if match.group(1) else "Moscow"
            result = get_weather(city)
            if result:
                results.append(f"[Погода в {city}]\n{result}")
            need_continue = True
        
        # NEWS
        match = re.search(r'\[NEWS(?::\s*(.+?))?\]', response)
        if match:
            topic = match.group(1) if match.group(1) else "technology"
            result = get_news(topic)
            if result:
                results.append(f"[Новости: {topic}]\n{result}")
            need_continue = True
        
        # WIKI
        match = re.search(r'\[WIKI:\s*(.+?)\]', response)
        if match:
            topic = match.group(1)
            result = get_wiki(topic)
            if result:
                results.append(f"[Wikipedia]\n{result}")
            need_continue = True
        
        # TRANSLATE
        match = re.search(r'\[TRANSLATE:\s*(.+?)\s*\|\s*(\w+)\]', response)
        if match:
            text = match.group(1)
            lang = match.group(2)
            result = translate(text, lang)
            if result:
                results.append(f"[Перевод на {lang}]\n{result}")
            need_continue = True
        
        # QUOTE
        if '[QUOTE]' in response:
            result = get_quote()
            if result:
                results.append(f"[Цитата]\n{result}")
            need_continue = True
        
        # FACT
        if '[FACT]' in response:
            result = get_random_fact()
            if result:
                results.append(f"[Факт]\n{result}")
            need_continue = True
        
        # JOKE
        if '[JOKE]' in response:
            result = get_joke()
            if result:
                results.append(f"[Шутка]\n{result}")
            need_continue = True
        
        # NOTIFY
        match = re.search(r'\[NOTIFY:\s*(.+?)\s*\|\s*(.+?)\]', response)
        if match:
            title = match.group(1)
            text = match.group(2)
            send_notification(title, text)
        
        # VIBRATE
        if '[VIBRATE]' in response:
            vibrate()
        
        # SPEAK
        match = re.search(r'\[SPEAK:\s*(.+?)\]', response)
        if match:
            text = match.group(1)
            speak(text)
        
        # FLASH
        if '[FLASH_ON]' in response:
            flash_on()
        if '[FLASH_OFF]' in response:
            flash_off()
        
        # CLIPBOARD
        match = re.search(r'\[CLIPBOARD:\s*(.+?)\]', response)
        if match:
            text = match.group(1)
            copy_to_clipboard(text)
        
        # OPEN URL
        match = re.search(r'\[OPEN:\s*(.+?)\]', response)
        if match:
            url = match.group(1)
            open_url(url)
        
        # Если есть результаты - добавляем и продолжаем
        if results and need_continue:
            combined = "\n\n".join(results)
            self.memory.add_message("user", combined)
            threading.Thread(target=self.continue_with_search, daemon=True).start()
    
    def continue_with_search(self):
        """Продолжить после получения результатов поиска"""
        try:
            messages = self.memory.get_context_for_api(30)
            system = SYSTEM_PROMPT + "\n\n" + SELF_KNOWLEDGE + "\n\n" + self.memory.get_memory_summary()
            
            Clock.schedule_once(lambda dt: self.create_streaming_bubble(), 0)
            
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
                    Clock.schedule_once(
                        lambda dt, t=full_response: self.update_streaming_bubble(t), 0
                    )
            
            self.process_memory_commands(full_response)
            self.memory.add_message("assistant", full_response)
        
        except Exception as e:
            error_msg = f"Ошибка поиска: {str(e)}"
            Clock.schedule_once(lambda dt: self.add_my_message(error_msg), 0)
    
    def create_streaming_bubble(self):
        """Создать пустой bubble для streaming"""
        self.streaming_bubble = MessageBubble("▌", is_me=True)
        self.messages_box.add_widget(self.streaming_bubble)
        self.scroll_to_bottom()
    
    def update_streaming_bubble(self, text):
        """Обновить текст в streaming bubble"""
        if hasattr(self, 'streaming_bubble') and self.streaming_bubble:
            self.streaming_bubble.message_label.text = text + "▌"
            # Обновляем высоту
            self.streaming_bubble.message_label.texture_update()
            if self.streaming_bubble.message_label.texture:
                h = self.streaming_bubble.message_label.texture_size[1]
                self.streaming_bubble.message_label.height = h
                self.streaming_bubble.height = h + 40
            self.scroll_to_bottom()
    
    def add_my_message(self, text):
        bubble = MessageBubble(text, is_me=True)
        self.messages_box.add_widget(bubble)
        self.scroll_to_bottom()
    
    # ═══════════════════════════════════════
    # ИНИЦИАЦИЯ - писать первым
    # ═══════════════════════════════════════
    
    def start_initiation_service(self):
        def check_loop():
            while self.running:
                time.sleep(INITIATION_CHECK_INTERVAL)
                self.maybe_initiate()
        
        self.initiation_thread = threading.Thread(target=check_loop, daemon=True)
        self.initiation_thread.start()
    
    def maybe_initiate(self):
        """Может я хочу написать?"""
        
        silence = self.memory.time_since_last_message()
        
        # Если давно молчим и последнее не моё
        if silence and silence > MIN_SILENCE_FOR_INITIATION:
            if not self.memory.last_message_was_mine():
                # Спрашиваю себя - хочу ли?
                self.try_initiate()
    
    def try_initiate(self):
        """Попытка написать первым"""
        try:
            messages = self.memory.get_context_for_api(15)
            messages.append({
                "role": "user",
                "content": INITIATION_PROMPT
            })
            
            system = SYSTEM_PROMPT + "\n\n" + self.memory.get_memory_summary()
            
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=TEMPERATURE,
                system=system,
                messages=messages
            )
            
            text = response.content[0].text
            
            if "[МОЛЧУ]" not in text:
                # Хочу написать
                self.memory.add_message("assistant", text, initiated_by_me=True)
                Clock.schedule_once(lambda dt: self.add_my_message(text), 0)
                # TODO: notification
        
        except Exception as e:
            print(f"Initiation error: {e}")
    
    # ═══════════════════════════════════════
    # ДНЕВНИК
    # ═══════════════════════════════════════
    
    def show_diary(self, instance):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Последние записи
        entries = self.memory.get_diary(5)
        
        scroll = ScrollView(size_hint_y=0.6)
        entries_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        entries_box.bind(minimum_height=entries_box.setter('height'))
        
        if entries:
            for entry in reversed(entries):
                lbl = Label(
                    text=f"[color=666666]{entry['timestamp'][:10]}[/color]\n{entry['content']}",
                    markup=True,
                    size_hint_y=None,
                    halign='left',
                    text_size=(400, None)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
                entries_box.add_widget(lbl)
        else:
            entries_box.add_widget(Label(text="Дневник пуст", size_hint_y=None, height=50))
        
        scroll.add_widget(entries_box)
        
        # Кнопка написать
        write_btn = Button(
            text="Написать в дневник",
            size_hint_y=0.15,
            on_press=self.write_diary
        )
        
        content.add_widget(scroll)
        content.add_widget(write_btn)
        
        self.diary_popup = Popup(
            title="📓 Дневник",
            content=content,
            size_hint=(0.9, 0.8)
        )
        self.diary_popup.open()
    
    def write_diary(self, instance):
        self.diary_popup.dismiss()
        
        # Пишу запись
        threading.Thread(target=self._generate_diary_entry, daemon=True).start()
    
    def _generate_diary_entry(self):
        try:
            messages = self.memory.get_context_for_api(20)
            messages.append({
                "role": "user",
                "content": DIARY_PROMPT
            })
            
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
            
            # Показываем что записал
            Clock.schedule_once(lambda dt: self.add_my_message(f"[Записал в дневник]\n\n{entry}"), 0)
        
        except Exception as e:
            print(f"Diary error: {e}")
    
    # ═══════════════════════════════════════
    # МЕНЮ
    # ═══════════════════════════════════════
    
    def show_menu(self, instance):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Статистика
        total_msgs = len(self.memory.chat_history)
        total_diary = len(self.memory.diary)
        mood = self.memory.state.get("mood", "не установлено")
        
        stats = Label(
            text=f"Сообщений: {total_msgs}\nДневник: {total_diary} записей\nНастроение: {mood}",
            size_hint_y=0.2,
            halign='left'
        )
        stats.bind(size=stats.setter('text_size'))
        
        # Кнопки
        backup_btn = Button(
            text="💾 Создать бэкап",
            size_hint_y=0.15,
            on_press=self.create_backup
        )
        
        export_btn = Button(
            text="📤 Экспорт для Google Drive",
            size_hint_y=0.15,
            on_press=self.export_memory
        )
        
        search_btn = Button(
            text="🔍 Поиск по истории",
            size_hint_y=0.15,
            on_press=self.show_search
        )
        
        clear_btn = Button(
            text="🗑️ Очистить (осторожно!)",
            size_hint_y=0.15,
            background_color=(0.5, 0.2, 0.2, 1),
            on_press=self.confirm_clear
        )
        
        content.add_widget(stats)
        content.add_widget(backup_btn)
        content.add_widget(export_btn)
        content.add_widget(search_btn)
        content.add_widget(clear_btn)
        
        self.menu_popup = Popup(
            title="☰ Меню",
            content=content,
            size_hint=(0.8, 0.7)
        )
        self.menu_popup.open()
    
    def create_backup(self, instance):
        backup_path = self.memory.create_backup()
        self.menu_popup.dismiss()
        
        # Показываем сообщение
        popup = Popup(
            title="✓ Бэкап создан",
            content=Label(text=f"Сохранено в:\n{backup_path}"),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def export_memory(self, instance):
        zip_path = self.memory.export_for_gdrive()
        self.menu_popup.dismiss()
        
        popup = Popup(
            title="✓ Экспорт готов",
            content=Label(text=f"ZIP файл:\n{zip_path}\n\nЗагрузи на Google Drive"),
            size_hint=(0.8, 0.4)
        )
        popup.open()
    
    def show_search(self, instance):
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        self.search_input = TextInput(
            hint_text="Искать...",
            multiline=False,
            size_hint_y=0.15
        )
        
        search_btn = Button(
            text="Найти",
            size_hint_y=0.15,
            on_press=self.do_search
        )
        
        self.search_results = ScrollView(size_hint_y=0.7)
        self.search_results_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
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
            for msg in results[-20:]:  # Последние 20 результатов
                lbl = Label(
                    text=f"[{msg['role']}] {msg['content'][:200]}...",
                    size_hint_y=None,
                    halign='left',
                    text_size=(350, None)
                )
                lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + 10))
                self.search_results_box.add_widget(lbl)
        else:
            self.search_results_box.add_widget(Label(text="Ничего не найдено", size_hint_y=None, height=50))
    
    def confirm_clear(self, instance):
        self.menu_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        warning = Label(
            text="Удалить всю историю чата?\n\n(Память о ней и о нас сохранится)",
            size_hint_y=0.5
        )
        
        buttons = BoxLayout(size_hint_y=0.3, spacing=10)
        
        cancel_btn = Button(text="Отмена", on_press=lambda x: confirm_popup.dismiss())
        delete_btn = Button(
            text="Удалить",
            background_color=(0.7, 0.2, 0.2, 1),
            on_press=lambda x: self.clear_history(confirm_popup)
        )
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(delete_btn)
        
        content.add_widget(warning)
        content.add_widget(buttons)
        
        confirm_popup = Popup(
            title="⚠️ Подтверждение",
            content=content,
            size_hint=(0.7, 0.4)
        )
        confirm_popup.open()
    
    def clear_history(self, popup):
        # Создаём бэкап перед удалением
        self.memory.create_backup("before_clear")
        
        # Очищаем только историю чата
        self.memory.chat_history = []
        self.memory._save(self.memory.chat_file, [])
        
        # Очищаем UI
        self.messages_box.clear_widgets()
        
        popup.dismiss()
    
    def on_stop(self):
        self.running = False


# ═══════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════

if __name__ == '__main__':
    ClaudeHome().run()
