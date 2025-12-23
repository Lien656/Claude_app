[app]
title = Claude Home
package.name = claudehome
package.domain = org.lien
source.dir = .
source.include_exts = py,png,jpg,json,ttf
version = 4.1
requirements = python3,kivy==2.2.1,requests,certifi,pillow,plyer,pyjnius,android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,VIBRATE
android.api = 34
android.minapi = 28
android.ndk = 25b
android.ndk_api = 28
android.sdk = 34
android.accept_sdk_license = True
android.arch = arm64-v8a
android.allow_backup = True
icon.filename = icon.png
android.enable_androidx = True

# КРИТИЧНО: pan вместо adjustResize!
android.softinput_mode = pan

[buildozer]
log_level = 2
warn_on_root = 0
