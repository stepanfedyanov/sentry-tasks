# Sentry Task Generator

[ru](README.ru.md)

This is a Python + Vue (Vite) web application that automates creating developer tasks from Sentry errors. It analyzes top critical incidents and uses an LLM to generate task descriptions with context and proposed solutions.

## Architecture (Current)

- `web` service: Nginx serving built Vue + Vite frontend (`frontend/src/*`).
- `api` service: FastAPI backend (`backend/api.py`) that talks to OpenAI.
- Browser flow:
    1. Browser calls Sentry API directly using user-provided Sentry settings.
    2. Browser stores Sentry response locally.
    3. Browser sends Sentry payload + OpenAI key to backend API via nginx proxy (`POST /api/tasks/generate`).
    4. Backend returns generated tasks.

This design helps when Sentry is reachable from the user's browser (VPN/proxy path) but not from server-side runtime.

## 🚀 Features

*   **Sentry Integration (Client-side):** Browser calls your Self-hosted (or Cloud) Sentry API directly.
*   **Error Analysis:** Selects the most critical errors (sorted by event frequency) from the last 2 weeks.
*   **AI Task Generation:** Backend endpoint uses OpenAI to generate clear task descriptions.
*   **Encrypted Browser Settings:** Sensitive settings can be stored in localStorage encrypted with passphrase (PBKDF2 + AES-GCM).
*   **Rate limiting:** Backend endpoint includes basic anti-abuse limits.
*   **Docker Compose:** Two-service setup (`web` + `api`) for simple deployment.

## 🛠 Requirements

*   Docker and Docker Compose
*   Access to Sentry (Auth Token)
*   OpenAI API Key

## ⚙️ Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd sentry-tasks
    ```

2.  **Optional `.env` setup (mainly for infrastructure settings):**
    Application keys are entered in the UI, not required in `.env`.

## ▶️ Running the App

Run the application using Docker Compose:

```bash
docker compose up
```

After successful startup, open your browser at:
**[http://localhost:8088](http://localhost:8088)**

Nginx proxy health endpoint to API:
**[http://localhost:8088/api-health](http://localhost:8088/api-health)**

## 🧪 Development Compose

For development mode (mounted source + backend auto-reload):

```bash
docker compose -f docker-compose.dev.yml up
```

Dev mode behavior:

- Frontend runs as Vite dev server with HMR on `http://localhost:8088`.
- Backend runs with `uvicorn --reload` and watches `backend/`.
- API is also exposed on **[http://localhost:8000](http://localhost:8000)** for debugging.

## Runtime Environment Variables

Used by the `api` container:

- `CORS_ALLOW_ORIGINS` (default: `http://localhost:8088`)
- `RATE_LIMIT_MAX_REQUESTS` (default: `60`)
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `OPENAI_TIMEOUT_SECONDS` (default: `40`)

## 💻 Local Development (without Docker)

If you want to run the application locally without Docker:

1.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run API:
    ```bash
    uvicorn backend.api:app --host 0.0.0.0 --port 8000
    ```

4.  Run Vue frontend with Vite:
    ```bash
        cd frontend
        npm install
        npm run dev -- --host 0.0.0.0 --port 8088
    ```
