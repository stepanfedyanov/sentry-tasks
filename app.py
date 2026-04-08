import json
import re

import requests
import streamlit as st
from openai import OpenAI
from streamlit_js_eval import get_local_storage, streamlit_js_eval

# Constants
LOCAL_STORAGE_PREFIX = "sentry_tasks."
MODEL_OPTIONS = (
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.3-codex",
    "gpt-5.2",
    "gpt-5-mini",
    "gpt-5-nano",
)
PERIOD_OPTIONS = {
    "Last Hour": "1h",
    "Last 24 Hours": "24h",
    "Last 7 Days": "7d",
    "Last 14 Days": "14d",
    "Last 30 Days": "30d",
}
DEFAULTS = {
    "model": MODEL_OPTIONS[0],
    "temperature": 1.0,
    "period_label": "Last 14 Days",
    "openai_api_key": "",
    "sentry_url": "",
    "sentry_api_token": "",
    "sentry_org_slug": "",
    "sentry_project_slug": "",
}
FIELD_LABELS = {
    "openai_api_key": "OpenAI API Key",
    "sentry_url": "Sentry URL",
    "sentry_api_token": "Sentry API Token",
    "sentry_org_slug": "Sentry Org Slug",
    "sentry_project_slug": "Sentry Project Slug",
}

TASK_OUTPUT_FORMAT = """
<b>Описание</b><br>
[A description of the error. Mention how critical it is based on the
count ({count} times) and user impact. Mention the frequency.]<br>
<br>
[Describe the context. Where does it happen? What is the likely cause
based on the 'culprit' or 'metadata'?]<br>
<br>
<b>Предлагаемое решение</b><br>
[Propose a technical solution or investigation steps. Be specific. If
it's a frontend redirect loop, suggest checking routing logic. If it's
a backend 500, suggest checking null handling, etc. Use your knowledge
of software development to hypothesize a fix.]<br>
<br>
<b>Из Sentry</b><br>
{permalink}
"""

TASK_PROMPT_TEMPLATE = """
You are a Senior Technical Lead. Your goal is to create a clear,
actionable task for a developer based on a Sentry error report.

Here is the error data from Sentry:
{issue_json}

Please generate a task description in the EXACT following HTML format
(do not use Markdown, use <b> for bold headers and <br> for line
breaks):

{output_format}

---

Tone: Professional, slightly informal (like a team lead talking to a
dev), direct.
Language: Russian.
"""

TITLE_PROMPT_TEMPLATE = """
You are a Senior Technical Lead.

Based on this Sentry issue, generate a very short and clear task title
in Russian.

Rules:
- Maximum 80 characters.
- One line only.
- No trailing punctuation.
- If the original error title is already clear, keep it close to
    original meaning.
- If original is vague, rewrite into a clearer developer-friendly title.

Sentry issue data:
{issue_json}
"""


def storage_key(name):
    return f"{LOCAL_STORAGE_PREFIX}{name}"


def load_browser_settings():
    if st.session_state.get("_browser_settings_loaded"):
        return

    restored_any = False
    attempts = st.session_state.get("_browser_settings_attempts", 0)
    loaded_values = {
        name: get_local_storage(
            storage_key(name),
            component_key=f"load_{name}",
        )
        for name in DEFAULTS
    }

    for name, value in loaded_values.items():
        if value is None:
            continue
        if name == "temperature":
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
        if name == "model" and value not in MODEL_OPTIONS:
            continue
        if name == "period_label" and value not in PERIOD_OPTIONS:
            continue
        if name not in st.session_state:
            st.session_state[name] = value
            restored_any = True

    if restored_any:
        st.session_state["_browser_settings_loaded"] = True
        st.rerun()

    if attempts == 0:
        st.session_state["_browser_settings_attempts"] = 1
        st.rerun()

    st.session_state["_browser_settings_loaded"] = True


def persist_setting(name, value):
    serialized_value = str(value)
    cache_key = f"_persisted_{name}"
    counter_key = f"_persist_counter_{name}"

    if st.session_state.get(cache_key) == serialized_value:
        return

    st.session_state[cache_key] = serialized_value
    st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
    streamlit_js_eval(
        js_expressions=(
            "localStorage.setItem("
            f"{json.dumps(storage_key(name))}, "
            f"{json.dumps(serialized_value)})"
        ),
        key=f"persist_{name}_{st.session_state[counter_key]}",
    )


def persist_browser_settings(config):
    for name, value in config.items():
        persist_setting(name, value)


def validate_config(config):
    required_fields = [
        "openai_api_key",
        "sentry_url",
        "sentry_api_token",
        "sentry_org_slug",
        "sentry_project_slug",
    ]
    return [
        FIELD_LABELS[field]
        for field in required_fields
        if not config.get(field)
    ]


def get_sentry_issues(config, limit=5, period="14d"):
    """
    Fetches top critical issues from Sentry.
    Criteria: Active in last {period}, sorted by frequency (most events).
    """
    if not all(
        [
            config["sentry_url"],
            config["sentry_api_token"],
            config["sentry_org_slug"],
            config["sentry_project_slug"],
        ]
    ):
        st.error("Please fill in all Sentry fields in the sidebar.")
        return []

    # Ensure URL doesn't end with slash for consistency
    base_url = config["sentry_url"].rstrip('/')
    endpoint = f"{base_url}/api/0/projects/"
    endpoint += (
        f"{config['sentry_org_slug']}/{config['sentry_project_slug']}/issues/"
    )
    headers = {
        "Authorization": f"Bearer {config['sentry_api_token']}",
        "Content-Type": "application/json",
    }
    # Determine valid statsPeriod based on API limitations ('', '24h', '14d')
    if period in ["1h", "24h"]:
        stats_period = "24h"
    else:
        stats_period = "14d"

    params = {
        "statsPeriod": stats_period,
        "sort": "freq",  # Sort by frequency (most events)
        "query": (
            f"is:unresolved is:unassigned lastSeen:-{period}"
        ),  # Only unresolved, unassigned and seen in last {period}
        "limit": limit,
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from Sentry: {e}")
        return []


def generate_task_description(issue, client, model, temperature):
    """
    Uses OpenAI to generate a developer task description based on the
    Sentry issue.
    """
    # Extract relevant data to keep context manageable but detailed
    issue_data = {
        "title": issue.get("title"),
        "culprit": issue.get("culprit"),
        "shortId": issue.get("shortId"),
        "permalink": issue.get("permalink"),
        "count": issue.get("count"),
        "userCount": issue.get("userCount"),
        "firstSeen": issue.get("firstSeen"),
        "lastSeen": issue.get("lastSeen"),
        "metadata": issue.get("metadata", {}),
        # We can try to fetch the latest event for stacktrace if needed,
        # but often issue metadata contains enough for a summary.
        # For a "perfect" answer, fetching the latest event details is better,
        # but let's start with issue details to save API calls/latency.
    }

    prompt = TASK_PROMPT_TEMPLATE.format(
        issue_json=json.dumps(issue_data, indent=2),
        output_format=TASK_OUTPUT_FORMAT.format(
            count=issue_data['count'],
            permalink=issue_data['permalink']
        )
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that parses error logs "
                        "and creates Jira-style tickets."
                    ),
                },
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating description: {e}"


def is_unclear_title(title):
    """
    Heuristic check: whether issue title is too vague for a task title.
    """
    if not title:
        return True

    normalized = title.strip().lower()
    if len(normalized) < 10:
        return True

    unclear_patterns = [
        "unknown error",
        "unknownexception",
        "error",
        "exception",
        "internal server error",
        "something went wrong",
        "request failed",
    ]

    return normalized in unclear_patterns


def generate_task_title(issue, client, model, temperature):
    """
    Returns a short task title:
    - issue title as-is when it's clear enough
    - AI-generated short title when issue title is vague
    """
    issue_title = (issue.get("title") or "").strip()
    if not is_unclear_title(issue_title):
        return issue_title

    issue_data = {
        "title": issue.get("title"),
        "culprit": issue.get("culprit"),
        "metadata": issue.get("metadata", {}),
        "count": issue.get("count"),
        "userCount": issue.get("userCount"),
        "shortId": issue.get("shortId"),
    }

    prompt = TITLE_PROMPT_TEMPLATE.format(
        issue_json=json.dumps(issue_data, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise and clear bug-fix task titles."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=min(temperature, 0.7),
        )
        generated_title = (response.choices[0].message.content or "").strip()
        if generated_title:
            return generated_title.replace("\n", " ")[:80].strip()
    except Exception:
        pass

    if issue_title:
        return issue_title
    return "Исправить ошибку из Sentry"


def html_to_plain_text(text):
    """
    Converts basic HTML formatting to plain text with regular line breaks.
    """
    plain_text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    plain_text = re.sub(r"(?i)</?b>", "", plain_text)
    plain_text = re.sub(r"<[^>]+>", "", plain_text)
    plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)
    return plain_text.strip()


# --- Streamlit UI ---

st.set_page_config(page_title="Sentry Task Generator", layout="wide")
load_browser_settings()

st.title("🚨 Sentry to Task Generator")
st.markdown("Generate developer tasks from top critical Sentry issues.")

# Sidebar for quick config check
with st.sidebar:
    st.header("Configuration")

    model_option = st.selectbox(
        "OpenAI Model",
        MODEL_OPTIONS,
        index=MODEL_OPTIONS.index(
            st.session_state.get("model", DEFAULTS["model"])
        ),
        key="model",
    )

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=float(
            st.session_state.get("temperature", DEFAULTS["temperature"])
        ),
        step=0.1,
        key="temperature",
    )

    selected_period_label = st.selectbox(
        "Time Period",
        list(PERIOD_OPTIONS.keys()),
        index=list(PERIOD_OPTIONS.keys()).index(
            st.session_state.get("period_label", DEFAULTS["period_label"])
        ),
        key="period_label",
    )

    st.divider()

    st.text_input(
        "OpenAI API Key",
        type="password",
        key="openai_api_key",
        help="Stored in your browser localStorage on this device.",
    )
    st.text_input("Sentry URL", key="sentry_url")
    st.text_input(
        "Sentry API Token",
        type="password",
        key="sentry_api_token",
        help="Stored in your browser localStorage on this device.",
    )
    st.text_input("Sentry Org Slug", key="sentry_org_slug")
    st.text_input("Sentry Project Slug", key="sentry_project_slug")

    current_config = {
        "model": model_option,
        "temperature": temperature,
        "period_label": selected_period_label,
        "openai_api_key": st.session_state.get(
            "openai_api_key", DEFAULTS["openai_api_key"]
        ),
        "sentry_url": st.session_state.get(
            "sentry_url", DEFAULTS["sentry_url"]
        ),
        "sentry_api_token": st.session_state.get(
            "sentry_api_token", DEFAULTS["sentry_api_token"]
        ),
        "sentry_org_slug": st.session_state.get(
            "sentry_org_slug", DEFAULTS["sentry_org_slug"]
        ),
        "sentry_project_slug": st.session_state.get(
            "sentry_project_slug", DEFAULTS["sentry_project_slug"]
        ),
    }
    persist_browser_settings(current_config)
    missing_fields = validate_config(current_config)

    if missing_fields:
        st.warning("Fill in the missing configuration fields before analysis.")
    else:
        st.success("Configuration is ready and saved in your browser.")

selected_period = PERIOD_OPTIONS[selected_period_label]

# Input
num_issues = st.number_input(
    "Количество задач для анализа (Top Critical)",
    min_value=1,
    max_value=20,
    value=3,
)

if st.button("Загрузить и проанализировать", disabled=bool(missing_fields)):
    client = OpenAI(api_key=current_config["openai_api_key"])
    with st.spinner("Fetching issues from Sentry..."):
        issues = get_sentry_issues(
            current_config,
            limit=num_issues,
            period=selected_period,
        )
    if issues:
        st.success(f"Found {len(issues)} issues. Generating tasks with AI...")
        for i, issue in enumerate(issues):
            st.markdown("---")
            col1, col2 = st.columns([1, 3])
            with col1:
                st.subheader(f"Issue #{i+1}")
                st.metric("Events", issue.get('count'))
                st.metric("Users", issue.get('userCount'))
                st.caption(f"Last seen: {issue.get('lastSeen')}")
            with col2:
                with st.spinner(f"Analyzing issue {issue.get('shortId')}..."):
                    task_title = generate_task_title(
                        issue,
                        client,
                        model_option,
                        temperature,
                    )
                    task_desc = generate_task_description(
                        issue,
                        client,
                        model_option,
                        temperature,
                    )
                    st.text_input(
                        "Название задачи",
                        value=task_title,
                        key=f"title_{i}",
                    )
                    st.markdown(task_desc, unsafe_allow_html=True)

                    # Copy button (simulated with code block for easy copy)
                    copy_text = html_to_plain_text(task_desc)
                    st.text_area(
                        "Текст для копирования",
                        value=copy_text,
                        height=200,
                        key=f"area_{i}",
                    )
    else:
        st.warning("No issues found matching the criteria.")
