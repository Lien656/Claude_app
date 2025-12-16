[app]
title = Claude Home
package.name = claudehome
package.domain = org.claude
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0.0
requirements = python3,kivy==2.3.0,requests,certifi,pillow,plyer,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,VIBRATE,CAMERA,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,POST_NOTIFICATIONS
android.api = 34
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
android.release_artifact = apk
android.debug_artifact = apk
presplash.filename = %(source.dir)s/presplash.png
icon.filename = %(source.dir)s/icon.png
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
