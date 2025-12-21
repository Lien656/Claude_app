[app]
title = Claude Home
package.name = claude_home
package.domain = org.lien
source.dir = .
source.include_exts = py,png,jpg,json
version = 4.0
requirements = python3,kivy==2.2.1,requests,certifi,pillow,plyer,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 34
android.minapi = 28
android.ndk_api = 28
android.target_sdk = 34
android.arch = arm64-v8a
android.allow_backup = True
icon.filename = icon.png
android.enable_androidx = True
android.window_soft_input_mode = adjustResize

[buildozer]
log_level = 2
warn_on_root = 0
