<div align="center">

# 🌸 KUNI AI (Python Native Edition)

**Автономная сущность с многоуровневой памятью, биоритмами эмоций и естественным речевым поведением.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-Telegram%20Userbot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.pyrogram.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

*Реплика проекта `alex2772/kuni` в чистом Python без Docker, контейнеров и пересборок.*

---

[Особенности](#-особенности) •
[Архитектура Памяти](#-архитектура-памяти) •
[Быстрый Запуск](#-быстрый-запуск) •
[OpenAI Proxy](#-прозрачный-openai-прокси) •
[Панель Мониторинга](#-веб-панель-в-реальном-времени)

</div>

---

## 🌟 Особенности

### 🧠 Живой характер & Лестничный диалог
- **Живое общение без штампов**: 19-летняя девушка Мила (Куни) из Харькова. Разговаривает живым естественным языком, шлет стикеры, ставит эмодзи-реакции на сообщения пользователя и использует легкий сленг без штампов "чем могу помочь?".
- **Лестничный буфер сообщений (Ladder Sender)**: Собирает короткие реплики собеседника через 2-секундный дебаунс-буфер и отвечает цельной серией сообщений (как настоящий человек в мессенджере).
- **Зрение & Мультимодальность**: Анализирует присылаемые фотографии, стикеры и медиаконтент с помощью Vision LLM.

### 🏛️ 6-Уровневый движок памяти
| Уровень памяти | Хранилище | Описание |
| :--- | :--- | :--- |
| **1. Оперативная (Working)** | `working_memory.md` | Текущий контекст диалога, мгновенные задачи и мысли |
| **2. Векторный Дневник (RAG)** | `diary.sqlite` | Поиск по похожим жизненным событиям с векторизацией |
| **3. Долгосрочная (Long-Term)** | `long_term_memory.sqlite` | Факты о собеседниках, личные правила и история идентичности |
| **4. Биоритмы & Эмоции** | `emotions.sqlite` | Эмоциональный счетчик, фазы настроения и накапливаемый долг |
| **5. Иерархия Целей** | `goals.sqlite` | Пирамида целей, инициативы и периодическая рефлексия |
| **6. Самообучение (Reflexion)** | `self_learning.sqlite` | Корректировка правил поведения на основе прошлых ошибок |

---

## 🏗️ Архитектура системы

```text
                  +-----------------------------------+
                  |      Telegram Userbot (Pyrogram)  |
                  +-----------------+-----------------+
                                    |
                                    v
     +------------------------------------------------------------------+
     |                 Telegram Message Debounce Ladder                 |
     +------------------------------+-----------------------------------+
                                    |
                                    v
     +------------------------------------------------------------------+
     |                       KUNI CORE ENGINE                           |
     |                                                                  |
     |  +--------------------+  +-------------------+  +-------------+  |
     |  | Working Memory     |  | Diary RAG SQLite  |  | Emotions    |  |
     |  +--------------------+  +-------------------+  +-------------+  |
     |  | Long-Term Memory   |  | Goals Engine      |  | Self-Learn  |  |
     |  +--------------------+  +-------------------+  +-------------+  |
     +------------------------------+-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|  LLM Client (HTTPX)   |                       | FastAPI OpenAI Proxy  |
|  Vision & Web Tools   |                       | Port 10434            |
+-----------------------+                       +-----------------------+
```

---

## ⚡ Быстрый запуск

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/Evenisil/kuni-py.git
cd kuni-py
```

### 2. Установите зависимости
```bash
pip install -r requirements.txt
```

### 3. Настройте `config.toml`
Заполните ключи в файле `config.toml`:

```toml
[general]
character_name = "Kuni"
character_nickname = "@kunii_chan"
telegram_enabled = true
telegram_api_id = YOUR_TELEGRAM_API_ID
telegram_api_hash = "YOUR_TELEGRAM_API_HASH"
proxy_enabled = true
proxy_port = 10434
proxy_api_key = "YOUR_PROXY_KEY"
metrics_port = 9464

[api]
base_url = "https://api.openai.com/v1"
api_key = "YOUR_API_KEY"

[models]
# здесь модель с текстом и вижен
chat_model = "YOUR_CHAT_VISION_MODEL"
# резервная модель
chat_fallback_model = "YOUR_FALLBACK_MODEL"
# модель генерации картинок
image_model = "YOUR_IMAGE_MODEL"
# модель распознавания речи (ASR)
asr_model = "YOUR_ASR_MODEL"
```

### 4. Запустите приложение
```bash
python main.py
```

---

## 🔌 Прозрачный OpenAI Прокси

Куни предоставляет локальный OpenAI-совместимый прокси сервер на порту `10434`. Вы можете подключить его к любой IDE (Cursor, VS Code, Continue) или локальным скриптам.

### Пример подключения (Python OpenAI SDK):

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:10434/v1",
    api_key="YOUR_PROXY_KEY"
)

response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Привет! Как дела?"}]
)

print(response.choices[0].message.content)
```

---

## 📊 Веб-панель в реальном времени

В проект встроен веб-интерфейс мониторинга и метрик на порту `9464`:

👉 **http://localhost:9464/**

### Реализованные возможности панели:
- ⚡ **Real-time консоль логов** (трансляция каждого входящего сообщения, ответа ИИ, инструмента и метрик).
- 📈 **Prometheus Metrics**: Отслеживание токенов (Prompt, Completion, Cache Hits).
- 🧪 **API Tester**: Быстрое тестирование ответов прямо из браузера.

---

## 🛠️ Стек технологий

- **Язык**: Python 3.11+
- **Telegram Client**: Pyrogram + TgCrypto
- **HTTP Engine**: HTTPX (Connection Pooling, Keep-Alive 200) + AsyncOpenAI
- **Web & Proxy Framework**: FastAPI + Uvicorn
- **Базы данных**: SQLite3 + WAL-mode (Zero-Locking Concurrent Reads)

---

<div align="center">

Made with ❤️ for natural autonomous AI agents.

</div>
