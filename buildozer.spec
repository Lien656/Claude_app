   [app]
   title = Claude Home
   package.name = claudehome
   package.domain = org.lien
   source.dir = .
   source.include_exts = py,png,jpg,jpeg,json,txt,ttf
   version = 4.2
   requirements = python3,kivy,requests,certifi
   orientation = portrait
   fullscreen = 0
   icon.filename = icon.png
   android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,VIBRATE
   android.api = 34
   android.minapi = 28
   28
   android.archs = arm64-v8a
   android.allow_backup = True
   android.enable_androidx = True
   android.window_soft_input_mode = adjustResize

   [buildozer
