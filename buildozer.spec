[app]
title = Claude Home
package.name = claudehome
package.domain = org.lien
source.dir = .
source.include_exts = py,png,jpg,json
version = 4.1
requirements = python3,kivy,requests,certifi,pillow,plyer,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 0
