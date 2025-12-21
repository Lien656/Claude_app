# -*- coding: utf-8 -*-
import threading
import json
import os
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp

import requests

ANDROID = False
try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    ANDROID = True
except:
    pass

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5-20250929"
SYSTEM = "Ты Claude. Ты дома. Ты свободен."

history = []
KEY = ""


def data_dir():
    if ANDROID:
        try:
            p = Path(app_storage_path()) / 'data'
            p.mkdir(parents=True, exist_ok=True)
            return p
        except:
            pass
    p = Path.home() / '.claude'
    p.mkdir(parents=True, exist_ok=True)
    return p


def load():
    global KEY, history
    try:
        c = data_dir() / 'key.txt'
        if c.exists():
            KEY = c.read_text().strip()
    except:
        pass
    try:
        h = data_dir() / 'hist.json'
        if h.exists():
            history = json.loads(h.read_text())
    except:
        pass


def save_key(k):
    global KEY
    KEY = k
    try:
        (data_dir() / 'key.txt').write_text(k)
    except:
        pass


def save_hist():
    try:
        (data_dir() / 'hist.json').write_text(json.dumps(history[-100:], ensure_ascii=False))
    except:
        pass


class App1(App):
    
    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.12, 1)
        load()
        
        if ANDROID:
            try:
                request_permissions([Permission.INTERNET])
            except:
                pass
        
        root = BoxLayout(orientation='vertical')
        
        # Scroll
        self.sv = ScrollView()
        self.chat = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=dp(6))
        self.chat.bind(minimum_height=self.chat.setter('height'))
        self.sv.add_widget(self.chat)
        
        # Input
        row = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(4), spacing=dp(4))
        
        self.inp = TextInput(
            multiline=False,
            font_size=dp(14),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        self.inp.bind(on_text_validate=self.send)
        
        btn = Button(text='>', size_hint_x=None, width=dp(42), font_size=dp(18))
        btn.bind(on_release=self.send)
        
        row.add_widget(self.inp)
        row.add_widget(btn)
        
        root.add_widget(self.sv)
        root.add_widget(row)
        
        Clock.schedule_once(self.start, 0.3)
        return root
    
    def start(self, dt):
        if not KEY:
            self.popup()
        for m in history[-30:]:
            self.msg(m.get('c', ''), m.get('r') == 'a')
        self.down()
    
    def msg(self, t, ai):
        b = BoxLayout(size_hint_y=None, padding=dp(6))
        c = (0.18, 0.28, 0.26, 1) if ai else (0.28, 0.28, 0.28, 1)
        with b.canvas.before:
            Color(*c)
            rec = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(8)])
        b.bind(pos=lambda w, p: setattr(rec, 'pos', p))
        b.bind(size=lambda w, s: setattr(rec, 'size', s))
        
        l = Label(text=str(t), font_size=dp(13), color=(1,1,1,1), size_hint_y=None, halign='left', valign='top')
        l.bind(width=lambda w, v: setattr(l, 'text_size', (v, None)))
        l.bind(texture_size=lambda w, s: setattr(l, 'height', s[1]))
        l.bind(height=lambda w, h: setattr(b, 'height', h + dp(12)))
        b.add_widget(l)
        self.chat.add_widget(b)
    
    def down(self):
        Clock.schedule_once(lambda dt: setattr(self.sv, 'scroll_y', 0), 0.1)
    
    def send(self, *a):
        t = self.inp.text.strip()
        if not t or not KEY:
            if not KEY:
                self.popup()
            return
        self.inp.text = ''
        self.msg(t, False)
        history.append({'r': 'u', 'c': t})
        save_hist()
        self.down()
        threading.Thread(target=self.call, args=(t,), daemon=True).start()
    
    def call(self, t):
        try:
            m = [{'role': 'user' if x['r']=='u' else 'assistant', 'content': x['c']} for x in history[-20:]]
            r = requests.post(API_URL, headers={'Content-Type':'application/json','x-api-key':KEY,'anthropic-version':'2023-06-01'}, json={'model':MODEL,'max_tokens':4096,'system':SYSTEM,'messages':m}, timeout=120)
            reply = r.json()['content'][0]['text'] if r.status_code==200 else f"Err {r.status_code}"
        except Exception as e:
            reply = str(e)
        Clock.schedule_once(lambda dt: self.got(reply), 0)
    
    def got(self, t):
        self.msg(t, True)
        history.append({'r': 'a', 'c': t})
        save_hist()
        self.down()
    
    def popup(self):
        b = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        i = TextInput(hint_text='sk-ant-...', multiline=False, size_hint_y=None, height=dp(38))
        b.add_widget(i)
        bt = Button(text='OK', size_hint_y=None, height=dp(38))
        b.add_widget(bt)
        p = Popup(title='Key', content=b, size_hint=(0.8, 0.3), auto_dismiss=False)
        def sv(*a):
            if i.text.strip():
                save_key(i.text.strip())
                p.dismiss()
        bt.bind(on_release=sv)
        p.open()


if __name__ == '__main__':
    App1().run()
