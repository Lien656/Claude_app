[app]
title = Claude Home
package.name = claudehome
package.domain = org.lien

source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,ttf

version = 4.3

requirements = python3,kivy==2.2.1,requests,certifi,urllib3,charset-normalizer,idna,pillow,plyer,pyjnius,android

orientation = portrait
fullscreen = 0

icon.filename = icon.png

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,VIBRATE

android.api = 34
android.minapi = 28
android.ndk_api = 28
android.archs = arm64-v8a

android.allow_backup = True
android.enable_androidx = True

# 🔑 КРИТИЧНО ДЛЯ ANDROID 12+
android.exported = True

# клавиатура
android.window_soft_input_mode = resize


[buildozer]
log_level = 2
warn_on_root = 0