# Sentry Task Generator

Это приложение на Python (Streamlit), которое автоматизирует процесс создания задач для разработчиков на основе ошибок из Sentry. Оно анализирует топ критичных инцидентов за последние 14 дней и с помощью LLM (ChatGPT) генерирует подробное описание задачи, включая контекст ошибки и предлагаемое решение.

## 🚀 Функциональность

*   **Интеграция с Sentry:** Подключается к вашему Self-hosted (или Cloud) Sentry API.
*   **Анализ ошибок:** Выбирает самые критичные ошибки (сортировка по частоте событий) за последние 2 недели.
*   **AI-генерация задач:** Использует OpenAI для формирования понятного описания задачи для разработчика.
*   **Веб-интерфейс:** Удобный UI на Streamlit для выбора количества задач и просмотра результатов.
*   **Docker:** Полная контейнеризация для быстрого запуска.

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

2.  **Настройте переменные окружения:**
    Создайте файл `.env` на основе примера:
    ```bash
    cp .env.example .env
    ```

    Откройте файл `.env` и заполните необходимые поля:
    ```ini
    # Sentry Configuration
    SENTRY_URL=https://sentry.your-company.com  # URL вашего Sentry
    SENTRY_API_TOKEN=your_sentry_auth_token     # Токен с правами project:read, event:read, org:read
    SENTRY_ORG_SLUG=sentry                      # Название организации (из URL)
    SENTRY_PROJECT_SLUG=your-project-slug       # Название проекта (из URL)

    # OpenAI Configuration
    OPENAI_API_KEY=sk-your-openai-api-key       # Ваш ключ OpenAI
    ```

    > **Как получить Sentry Token:**
    > Перейдите в User Settings -> API -> Auth Tokens и создайте новый токен.

## ▶️ Запуск

Запустите приложение с помощью Docker Compose:

```bash
docker compose up
```

После успешного запуска откройте браузер по адресу:
**[http://localhost:8501](http://localhost:8501)**

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

3.  Запустите Streamlit:
    ```bash
    streamlit run app.py
    ```

