import streamlit as st
import requests
import os
from dotenv import load_dotenv
from openai import OpenAI
import json

# Load environment variables
load_dotenv()

# Configuration
SENTRY_URL = os.getenv("SENTRY_URL")
SENTRY_TOKEN = os.getenv("SENTRY_API_TOKEN")
SENTRY_ORG = os.getenv("SENTRY_ORG_SLUG")
SENTRY_PROJECT = os.getenv("SENTRY_PROJECT_SLUG")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# Constants
TASK_OUTPUT_FORMAT = """
<b>Описание</b><br>
[A description of the error. Mention how critical it is based on the count ({count} times) and user impact. Mention the frequency.]<br>
<br>
[Describe the context. Where does it happen? What is the likely cause based on the 'culprit' or 'metadata'?]<br>
<br>
<b>Предлагаемое решение</b><br>
[Propose a technical solution or investigation steps. Be specific. If it's a frontend redirect loop, suggest checking routing logic. If it's a backend 500, suggest checking null handling, etc. Use your knowledge of software development to hypothesize a fix.]<br>
<br>
<b>Из Sentry</b><br>
{permalink}
"""

TASK_PROMPT_TEMPLATE = """
You are a Senior Technical Lead. Your goal is to create a clear, actionable task for a developer based on a Sentry error report.

Here is the error data from Sentry:
{issue_json}

Please generate a task description in the EXACT following HTML format (do not use Markdown, use <b> for bold headers and <br> for line breaks):

{output_format}

---

Tone: Professional, slightly informal (like a team lead talking to a dev), direct.
Language: Russian.
"""

def get_sentry_issues(limit=5):
    """
    Fetches top critical issues from Sentry.
    Criteria: Active in last 14 days, sorted by frequency (most events).
    """
    if not all([SENTRY_URL, SENTRY_TOKEN, SENTRY_ORG, SENTRY_PROJECT]):
        st.error("Please configure Sentry credentials in .env file")
        return []

    # Ensure URL doesn't end with slash for consistency
    base_url = SENTRY_URL.rstrip('/')
    endpoint = f"{base_url}/api/0/projects/{SENTRY_ORG}/{SENTRY_PROJECT}/issues/"
    headers = {
        "Authorization": f"Bearer {SENTRY_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {
        "statsPeriod": "14d",      # Active in last 14 days
        "sort": "freq",            # Sort by frequency (most events)
        "query": "is:unresolved is:unassigned", # Only unresolved and unassigned issues
        "limit": limit
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from Sentry: {e}")
        return []


def generate_task_description(issue, model, temperature):
    """
    Uses OpenAI to generate a developer task description based on the Sentry issue.
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
                {"role": "system", "content": "You are a helpful assistant that parses error logs and creates Jira-style tickets."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating description: {e}"

# --- Streamlit UI ---

st.set_page_config(page_title="Sentry Task Generator", layout="wide")

st.title("🚨 Sentry to Task Generator")
st.markdown("Generate developer tasks from top critical Sentry issues.")

# Sidebar for quick config check
with st.sidebar:
    st.header("Configuration")
    
    # Model Selection
    model_option = st.selectbox(
        "OpenAI Model",
        ("gpt-5.2", "gpt-5-mini", "gpt-5-nano"),
        index=0
    )
    
    # Temperature Selection
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=1.0,
        step=0.1
    )
    
    st.divider()
    
    if SENTRY_URL:
        st.success(f"Sentry URL: {SENTRY_URL}")
    else:
        st.error("Sentry URL missing")
    if OPENAI_API_KEY:
        st.success("OpenAI Key loaded")
    else:
        st.error("OpenAI Key missing")

# Input
num_issues = st.number_input("Количество задач для анализа (Top Critical)", min_value=1, max_value=20, value=3)

if st.button("Загрузить и проанализировать"):
    with st.spinner("Fetching issues from Sentry..."):
        issues = get_sentry_issues(limit=num_issues)
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
                    task_desc = generate_task_description(issue, model_option, temperature)
                    st.markdown(task_desc, unsafe_allow_html=True)
                    
                    # Copy button (simulated with code block for easy copy)
                    st.text_area("Raw HTML (Copy for Tracker)", value=task_desc, height=200, key=f"area_{i}")
    else:
        st.warning("No issues found matching the criteria.")
