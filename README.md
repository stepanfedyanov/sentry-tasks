# Sentry Task Generator

[ru](README.ru.md)

This is a Python (Streamlit) application that automates the process of creating developer tasks based on Sentry errors. It analyzes the top critical incidents from the last 14 days and uses an LLM (ChatGPT) to generate a detailed task description, including error context and suggested solutions.

The application is configured directly from the Streamlit sidebar. Sentry and OpenAI credentials are stored in the browser's localStorage on the current device.

## 🚀 Features

*   **Sentry Integration:** Connects to your Self-hosted (or Cloud) Sentry API.
*   **Error Analysis:** Selects the most critical errors (sorted by event frequency) from the last 2 weeks.
*   **AI Task Generation:** Uses OpenAI to generate clear task descriptions for developers.
*   **Web Interface:** User-friendly Streamlit UI for selecting the number of tasks and viewing results.
*   **Docker:** Fully containerized for quick deployment.

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

2.  **Prepare credentials for the UI:**
    You will enter these values in the Streamlit sidebar after startup:
    ```text
    SENTRY_URL
    SENTRY_API_TOKEN
    SENTRY_ORG_SLUG
    SENTRY_PROJECT_SLUG
    OPENAI_API_KEY
    ```

    > **How to get a Sentry Token:**
    > Go to User Settings -> API -> Auth Tokens and create a new token.

## ▶️ Running the App

Run the application using Docker Compose:

```bash
docker compose up
```

After successful startup, open your browser at:
**[http://localhost:8501](http://localhost:8501)**

Then fill in the sidebar configuration. The entered values are persisted in the browser localStorage for future visits on the same device/browser profile.

## 🚢 Production Deployment

For deployment, use the production compose file:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

This variant does not mount the project directory from the host, runs the container with `restart: unless-stopped`, and includes a healthcheck for the Streamlit endpoint.

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

3.  Run Streamlit:
    ```bash
    streamlit run app.py
    ```

## 🔒 Security

*   Secret keys are entered in the UI and stored in the browser localStorage on the current device.
*   Do not use this app in an untrusted browser profile or on a shared machine if you do not want credentials to remain available there.
*   The Docker image does not bake credentials into the container.
