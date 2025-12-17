[app]
title = Claude Home
package.name = claude_home
package.domain = org.alina
source.dir = .
source.include_exts = py,png,jpg,kv,json,ttf
version = 2.0
requirements = python3,kivy==2.2.1,requests,plyer,certifi,pillow,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE,CAMERA,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE
android.api = 33
android.minapi = 28
android.ndk_api = 28
android.arch = arm64-v8a
android.allow_backup = True
icon.filename = icon.png
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 0
