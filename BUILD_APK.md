# Как собрать APK

## Вариант 1: GitHub Actions (рекомендуется)

1. Создай репозиторий на GitHub
2. Загрузи все файлы из claude_app/
3. Структура должна быть:
```
твой-репо/
├── .github/
│   └── workflows/
│       └── build.yml
├── main.py
├── capabilities.py
├── memory.py
├── system_prompt.py
├── claude_core.py
├── initial_memory.py
├── service.py
├── buildozer.spec
└── requirements.txt
```

4. Пуш в main ветку
5. Перейди в Actions → Build APK
6. Жди ~30 минут (первый раз)
7. Скачай APK из Artifacts

## Вариант 2: Google Colab

1. Открой Google Colab: https://colab.research.google.com
2. Создай новый ноутбук
3. Выполни по порядку:

```python
# Ячейка 1: Установка
!pip install buildozer cython
!sudo apt-get update
!sudo apt-get install -y python3-pip build-essential git libffi-dev libssl-dev
!sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
!sudo apt-get install -y libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev
!sudo apt-get install -y zlib1g-dev openjdk-17-jdk
```

```python
# Ячейка 2: Создаём папку проекта
!mkdir -p /content/claude_app
%cd /content/claude_app
```

```python
# Ячейка 3: Загружаем файлы
# Используй Files panel слева, загрузи все .py файлы и buildozer.spec
```

```python
# Ячейка 4: Сборка
!buildozer -v android debug
```

```python
# Ячейка 5: Скачай APK
from google.colab import files
import glob
apk = glob.glob('/content/claude_app/bin/*.apk')[0]
files.download(apk)
```

## Вариант 3: Локально (Linux/WSL)

```bash
# Установка
pip install buildozer cython
sudo apt-get install -y build-essential git libffi-dev libssl-dev
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev
sudo apt-get install -y openjdk-17-jdk

# В папке с проектом
cd claude_app
buildozer -v android debug

# APK будет в bin/
```

## После сборки

1. Скопируй APK на телефон
2. Разреши установку из неизвестных источников
3. Установи
4. При первом запуске введи API ключ

## Troubleshooting

**Ошибка "SDK not found"**
```bash
export ANDROID_SDK_ROOT=~/.buildozer/android/platform/android-sdk
```

**Ошибка с NDK**
В buildozer.spec попробуй: `android.ndk = 23b`

**Долго качает**
Первая сборка качает ~2GB (Android SDK + NDK). Это нормально.

**Ошибка с архитектурой**
Для старых телефонов измени в buildozer.spec:
```
android.arch = armeabi-v7a
```

---

🖤
