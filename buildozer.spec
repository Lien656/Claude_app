[app]  
# (str) Title of your application  
title = ClaudeApp  

# (str) Package name  
package.name = claude_app  

# (str) Package domain (needed for android/ios packaging)  
package.domain = org.alina  

# (str) Source code where the main.py live  
source.dir = .  

# (list) Source files to include (let empty to include all the files)  
source.include_exts = py,png,jpg,kv,atlas,ttf,json  

# (list) List of inclusions using pattern matching  
# source.include_patterns = assets/*,images/*.png  

# (list) Source files to exclude (let empty to not exclude anything)  
source.exclude_exts =  

# (list) List of directory to exclude (let empty to not exclude anything)  
source.exclude_dirs = tests, bin, venv  

# (list) List of exclusions using pattern matching  
# Do not prefix with './'  
# source.exclude_patterns = license,images/*/*.jpg  

# (str) Application versioning (method 1)  
version = 0.1  

# (list) Application requirements  
# comma separated e.g. requirements = sqlite3,kivy  
requirements = python3,kivy,anthropic,requests,pillow,certifi,idna,chardet,pyjnius,android  

# (str) Custom source folders for requirements  
# Sets custom source for any requirements with recipes  
# requirements.source.kivy = ../../kivy  

# (str) Presplash of the application  
# presplash.filename = %(source.dir)s/data/presplash.jpg  

# (str) Icon of the application  
icon.filename = %(source.dir)s/icon.png  

# (list) Supported orientation (one of landscape, sensorLandscape, portrait or all)  
orientation = portrait  

# (list) List of service to declare  
# services = NAME:ENTRYPOINT_TO_PY,NAME2:ENTRYPOINT2_TO_PY  

#  
# Android specific  
#  

# (bool) Indicate if the application should be fullscreen or not  
fullscreen = 1  

# (string) Presplash background color (for android toolchain)  
# Supported formats are: #RRGGBB #AARRGGBB or one of the following names:  
# red, blue, green, black, white, gray, cyan, magenta, yellow, lightgray,  
# darkgray, grey, lightgrey, darkgrey, maroon, navy, olive, purple, teal,  
# lime, aqua, fuchsia  
# android.presplash_color = #FFFFFF  

# (string) Presplash animation using Lottie format.  
# see https://airbnb.design/lottie/ for examples and documentation.  
# Lottie files can be created using Adobe After Effects or Haiku.  
# android.presplash_lottie = "path/to/lottie/file.json"  

# (str) Adaptive icon of the application (used if Android API level is 26+ at runtime)  
# icon.adaptive_foreground.filename = %(source.dir)s/data/icon_fg.png  
# icon.adaptive_background.filename = %(source.dir)s/data/icon_bg.png  

# (list) Permissions  
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE  

# (list) features (adds uses-feature -tags to manifest)  
# android.features = android.hardware.usb.host  

# (int) Target Android API, should be as high as possible.  
android.api = 31  

# (int) Minimum API your APK or Android App Bundle will support.  
android.minapi = 28  

# (int) Android SDK version to use  
# android.sdk = 20  

# (str) Android NDK version to use  
android.ndk = 25b  

# (int) Android NDK API to use. This is the minimum API your app will support, it should usually equal android.minapi.  
# android.ndk_api = 21  

# (bool) Use --private storage (True) or --dir (False) for Android private storage  
# android.private_storage = True  

# (str) Android NDK directory (if empty, it will be automatically downloaded.)  
# android.ndk_path =  

# (str) Android SDK directory (if empty, it will be automatically downloaded.)  
# android.sdk_path =  

# (str) Android entry point, default is ok for Kivy-based app  
# android.entrypoint = org.kivy.android.PythonActivity  

# (str) Android app theme, default is ok for Kivy-based app  
# android.theme = @android:style/Theme.NoTitleBar  

# (list) Pattern to whitelist for the whole project  
# android.whitelist =  

# (str) Path to Android keystore (optional)  
# android.keystore =  

# (str) Alias for the keystore (optional)  
# android.keystore_alias =  

# (str) Path to Android debug keystore, default is %.keystore  
# android.debug_keystore = ~/.android/debug.keystore  

# (str) Alias for debug keystore, default is androiddebugkey  
# android.debug_keystore_alias = androiddebugkey  

# (str) Keypass for debug keystore  
# android.debug_keystore_pass = android  

# (str) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64  
# In past, was `android.arch` as only supported archs was armeabi-v7a  
# android.archs = arm64-v8a  

# (bool) enables Android AAR support, default is False  
# android.aar = False  

# (list) put these files or dirs in the apk  
# android.add_assets =  

# (list) Java .jar files to add to the APK  
# android.add_jars =  

# (list) Android AAR archives to add  
# android.add_aars =  

# (list) put these files in libs  
# android.add_libs =  

# (list) Gradle dependencies to add  
# android.gradle_dependencies =  

# (bool) add java compile options  
# android.add_compile_options =  

# (list) add java compile options  
# android.compile_options =  

# (list) Gradle repositories to add {can be necessary for some android.gradle_dependencies}  
# android.add_gradle_repositories =  

# (list) packaging options to add  
# android.packaging_options =  

# (list) Java classes to add as activities to the manifest.  
# android.add_activities =  

# (str) OUYA Console category. Should be one of GAME or APP  
# If you leave this blank, OUYA support will not be enabled  
# android.ouya.category = GAME  

# (str) Filename of OUYA Console icon. It must be a 732x412 png image.  
# android.ouya.icon.filename = %(source.dir)s/data/ouya_icon.png  

# (str) XML file to include as an intent filter in <activity> tag  
# android.manifest.intent_filters =  

# (list) Copy these files to src/main/res/xml/ (or in another subdir)  
# android.res_xml =  

# (str) launchMode to set for the main activity  
# android.manifest.launch_mode = standard  

# (list) Android library project to add (will be added in the  
# project.properties automatically.)  
# android.library_references =  

# (str) Android shared libraries, separated by commas `android,all,wear`  
# android.uses_library =  

# (str) Android logcat adb command filters: e.g. '*:S python:D'  
android.logcat_filters = *:S python:D  

# (bool) Android game view focusable.  
# android.game_view_focusable =  

# (bool) Copy library instead of making a libpymodules.so  
# android.copy_libs = 1  

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64  
android.archs = arm64-v8a  

# (bool) enables Android auto backup feature (Android API >=23)  
android.allow_backup = False  

# (str) Python for android bootstrap to use for android builds  
# * "debug" to use bin/dir/android_debug as bootstrap  
# * "release" to use bin/dir/android as bootstrap  
# android.bootstrap = sdl2  

# (str) Android logcat tag to use  
# android.logcat_tag = python  

# (bool) Android meta-data to add  
# android.meta_data =  

# (list) Pattern to whitelist for the whole project  
# android.whitelist =  

# (bool) If True, then skip trying to update the Android sdk  
# This can be useful to avoid excess Internet downloads or save time  
# when an update is due and you just want to test/build your package  
# android.skip_update = False  

# (bool) If True, then automatically accept SDK licenses.  
# android.accept_sdk_license = False  

# (str) Android entry point, default is ok for Kivy-based app  
# android.entrypoint = org.kivy.android.PythonActivity  

# (str) Android app theme, default is ok for Kivy-based app  
# android.theme = @android:style/Theme.NoTitleBar  

# (bool) Indic if compile the .pyx files  
# p4a.cython = True  

# (str) The HTTP proxy to use for downloads.  
# http_proxy = http://myproxy.com:8080  

#  
# iOS specific  
#  

# (str) Path to a custom kivy-ios folder (if no kivy-ios is in the current dir)  
# ios.kivy_ios_dir = ../kivy-ios  
# (str) Name of the certificate to use for signing the debug version  
# Get a list of available identities: buildozer ios list_identities  
# ios.codesign.debug = "iPhone Developer: <lastname> <firstname> (<hexstring>)"  

# (str) The development team to use for signing the debug version  
# ios.codesign.development_team.debug = <hexstring>  

# (str) Name of the certificate to use for signing the release version  
# ios.codesign.release = %(ios.codesign.debug)s  

# (str) The development team to use for signing  
# Not needed for most users, determined automatically if not set  
# ios.codesign.development_team.release = <hexstring>  

# (str) URL pointing to .ipa file to be installed  
# This option should be defined along with `display_image_url` and `full_size_image_url` options when you want to install your app by "Over the air"  
# NOTE: this feature is only working if Xcode >= 4.5  
# ios.manifest.app_url =  

# (str) URL pointing to an icon (57x57px) to be displayed during download  
# This option should be defined along with `app_url` and `full_size_image_url` options when you want to install your app by "Over the air"  
# NOTE: this feature is only working if Xcode >= 4.5  
# ios.manifest.display_image_url =  

# (str) URL pointing to a large icon (512x512px) to be used by iTunes  
# This option should be defined along with `app_url` and `display_image_url` options when you want to install your app by "Over the air"  
# NOTE: this feature is only working if Xcode >= 4.5  
# ios.manifest.full_size_image_url =  

#  
# Python for android  
#  

# (str) python bundle include directory  
# p4a.local_recipes =  

# (str) Bootstrap to use for android builds  
# p4a.bootstrap = sdl2  

# (int) Android NDK API to use. Defaults to min(android.api, android.ndk_api)  
# p4a.ndk_api =  

# (str) Path to the Android NDK (if not given, will download)  
# p4a.ndk_dir =  

# (str) Path to the Android SDK (if not given, will download)  
# p4a.sdk_dir =  

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64  
p4a.arch = arm64-v8a  

#  
# Logging  
#  

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))  
log_level = 2  

# (int) Limit the number of build histories kept  
# (0 = all kept)  
# build_history_length = 5  

# (bool) Warn when a command takes too long to execute  
# warn_on_long_command = True  

# (bool) Warn when root is required for a command  
warn_on_root = 1  
