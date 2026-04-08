# Sentry Task Generator

Это приложение на Python + Vue (Vite), которое автоматизирует процесс создания задач для разработчиков на основе ошибок из Sentry. Оно анализирует топ критичных инцидентов и с помощью LLM генерирует подробное описание задачи с контекстом и предлагаемым решением.

## Архитектура (текущая)

- `web` сервис: nginx, который отдает собранный Vue + Vite frontend (`frontend/src/*`).
- `api` сервис: FastAPI (`backend/api.py`) для вызовов OpenAI.
- Поток запросов:
    1. Браузер напрямую запрашивает Sentry API (по введенным пользователем настройкам).
    2. Ответ Sentry хранится в браузере.
    3. Браузер отправляет payload Sentry + ключ OpenAI в backend через nginx-прокси (`POST /api/tasks/generate`).
    4. Backend возвращает готовые задачи.

## 🚀 Функциональность

*   **Интеграция с Sentry (клиентская):** Браузер напрямую подключается к вашему Self-hosted (или Cloud) Sentry API.
*   **Анализ ошибок:** Выбирает самые критичные ошибки (сортировка по частоте событий) за последние 2 недели.
*   **AI-генерация задач:** Backend API использует OpenAI для формирования описания.
*   **Шифрование настроек в браузере:** Чувствительные данные можно сохранять в localStorage в зашифрованном виде (PBKDF2 + AES-GCM).
*   **Ограничение нагрузки:** В backend добавлен базовый rate limiting.
*   **Docker Compose:** Запуск в двух сервисах (`web` + `api`).

## 🛠 Требования

*   Docker и Docker Compose
*   Доступ к Sentry (Auth Token)
*   API ключ OpenAI

## ⚙️ Установка и настройка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone <repository-url>
    cd sentry-tasks
    ```

2.  **Опционально настройте `.env` для инфраструктурных параметров:**
    Ключи Sentry/OpenAI теперь вводятся через UI.

## ▶️ Запуск

Запустите приложение с помощью Docker Compose:

```bash
docker compose up
```

После успешного запуска откройте браузер по адресу:
**[http://localhost:8088](http://localhost:8088)**

Healthcheck API через nginx:
**[http://localhost:8088/api-health](http://localhost:8088/api-health)**

## 🧪 Docker Compose для разработки

Для режима разработки (монтирование исходников + авто-перезапуск backend):

```bash
docker compose -f docker-compose.dev.yml up
```

Поведение dev-режима:

- Frontend запускается через Vite dev server (HMR) на `http://localhost:8088`.
- Backend запускается с `uvicorn --reload` и отслеживает `backend/`.
- API также доступен на **[http://localhost:8000](http://localhost:8000)** для отладки.

## 💻 Локальная разработка (без Docker)

Если вы хотите запустить приложение локально без Docker:

1.  Создайте виртуальное окружение:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```

3.  Запустите API:
    ```bash
    uvicorn backend.api:app --host 0.0.0.0 --port 8000
    ```

4.  Запустите Vue frontend через Vite:
    ```bash
        cd frontend
        npm install
        npm run dev -- --host 0.0.0.0 --port 8088
    ```

