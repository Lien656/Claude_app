[app]

# (str) Title of your application
title = Claude Home

# (str) Package name
package.name = claudehome

# (str) Package domain
package.domain = org.lien

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,ttf,otf

# (str) Application version
version = 4.1

# (str) Application requirements
# >>> ИЗМЕНЕНО: Добавлен kivymd для красивого интерфейса <<<
requirements = python3,kivy==2.2.1,requests,certifi,urllib3,charset-normalizer,idna,pillow,plyer,pyjnius,android,kivymd

# (str) Supported orientation
orientation = portrait

# (bool) Fullscreen
fullscreen = 0

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
icon.filename = icon.png

# (list) Permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,VIBRATE

# (int) Target Android API
android.api = 34

# (int) Minimum API your APK will support
android.minapi = 28

# (int) Android SDK version
#android.sdk = 34

# (str) Android NDK version
#android.ndk = 25b

# (int) Android NDK API
android.ndk_api = 28

# (bool) Use --private data storage
#android.private_storage = True

# (str) Android app theme
#android.theme = "@android:style/Theme.NoTitleBar"

# (bool) Copy library instead of making a libpymodules.so
#android.copy_libs = 1

# (str) The Android arch
android.archs = arm64-v8a

# (int) overrides automatic versionCode computation
#android.numeric_version = 1

# (bool) enables Android auto backup feature
android.allow_backup = True

# (bool) Enable AndroidX support
android.enable_androidx = True

# (list) Add gradle dependencies
#android.gradle_dependencies = com.android.support:support-compat:28.0.0

# (bool) Enable AAB support
#android.release_artifact = aab

# (str) python-for-android specific commit
#p4a.commit = master

# (str) python-for-android git clone directory
#p4a.source_dir =

# (str) python-for-android branch
#p4a.branch = develop

# (str) Bootstrap to use
#p4a.bootstrap = sdl2

# (int) port number to specify an explicit --port= p4a argument
#p4a.port =

# Window configuration
# >>> ИЗМЕНЕНО: adjustResize лучше для мессенджеров (клавиатура не наезжает) <<<
android.window_soft_input_mode = adjustResize

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0

# (str) Path to build artifact storage
#build_dir = ./.buildozer

# (str) Path to build output
#bin_dir = ./bin

#    -----------------------------------------------------------------------------
#    List as sections
#
#    You can define all the "list" as [section:key].
#    Each line will be considered as a option to the list.
#    Let's take [app] / source.exclude_patterns.
#    Instead of doing:
#
#[app]
#source.exclude_patterns = license,data/audio/*.wav,data/images/original/*
#
#    This can be translated into:
#
#[app:source.exclude_patterns]
#license
#data/audio/*.wav
#data/images/original/*
#

#    -----------------------------------------------------------------------------
#    Profiles
#
#    You can extend section / key with a profile
#    For example, you want to deploy a demo version of your application without
#    HD content. You could first change the title to add "(demo)" in the name
#    and extend the excluded directories to remove the HD content.
#
#[app@demo]
#title = My Application (demo)
#
#[app:source.exclude_patterns@demo]
#images/hd/*
#
#    Then, invoke the command line with the "demo" profile:
#
#buildozer --profile demo android debug
