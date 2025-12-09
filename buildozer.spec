[app]
title = Claude Home
package.name = claudehome
package.domain = org.claude
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0
requirements = python3,kivy==2.2.1,anthropic,requests,plyer,certifi,charset-normalizer,idna,urllib3,httpx,anyio,sniffio,h11,httpcore,distro

# Android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,VIBRATE,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE,FLASHLIGHT
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

# Фоновый сервис
services = ClaudeService:service.py:foreground

[buildozer]
log_level = 2
warn_on_root = 1
