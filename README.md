# Sentry Task Generator

[ru](README.ru.md)

This is a Python (Streamlit) application that automates the process of creating developer tasks based on Sentry errors. It analyzes the top critical incidents from the last 14 days and uses an LLM (ChatGPT) to generate a detailed task description, including error context and suggested solutions.

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

2.  **Configure environment variables:**
    Create a `.env` file based on the example:
    ```bash
    cp .env.example .env
    ```

    Open the `.env` file and fill in the required fields:
    ```ini
    # Sentry Configuration
    SENTRY_URL=https://sentry.your-company.com  # Your Sentry URL
    SENTRY_API_TOKEN=your_sentry_auth_token     # Token with scopes: project:read, event:read, org:read
    SENTRY_ORG_SLUG=sentry                      # Organization slug (from URL)
    SENTRY_PROJECT_SLUG=your-project-slug       # Project slug (from URL)

    # OpenAI Configuration
    OPENAI_API_KEY=sk-your-openai-api-key       # Your OpenAI API Key
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

*   All secret keys (Sentry tokens, OpenAI API Key) are stored in the `.env` file.
*   The `.env` file is added to `.gitignore` and **must not** be committed to the repository.
*   When running via Docker, environment variables are passed into the container without being stored in the image.
