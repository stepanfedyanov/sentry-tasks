import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator


TASK_OUTPUT_FORMAT = """
Описание
[A description of the error. Mention how critical it is based on the count ({count} times) and user impact. Mention the frequency.]

[Describe the context. Where does it happen? What is the likely cause based on the 'culprit' or 'metadata'?]

Предлагаемое решение
[Propose a technical solution or investigation steps. Be specific.]

Из Sentry
{permalink}
""".strip()

TASK_PROMPT_TEMPLATE = """
You are a Senior Technical Lead. Your goal is to create a clear, actionable task for a developer based on a Sentry error report.

Here is the error data from Sentry:
{issue_json}

Generate a task in Russian. Keep headers in plain text (not HTML):

{output_format}

Tone: Professional, slightly informal, direct.
""".strip()

TITLE_PROMPT_TEMPLATE = """
You are a Senior Technical Lead.

Based on this Sentry issue, generate a short and clear task title in Russian.

Rules:
- Maximum 80 characters.
- One line only.
- No trailing punctuation.
- Keep close to issue meaning when already clear.

Sentry issue data:
{issue_json}
""".strip()


@dataclass
class SlidingWindowRateLimiter:
    max_requests: int
    window_seconds: int
    state: dict[str, list[float]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, key: str) -> bool:
        now = time.time()
        min_ts = now - self.window_seconds
        with self.lock:
            entries = [ts for ts in self.state.get(key, []) if ts >= min_ts]
            if len(entries) >= self.max_requests:
                self.state[key] = entries
                return False
            entries.append(now)
            self.state[key] = entries
            return True


class GenerateTasksRequest(BaseModel):
    openai_api_key: str = Field(min_length=10, max_length=512)
    model: str = Field(default="gpt-5.4-mini", min_length=2, max_length=80)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    issues: list[dict[str, Any]] = Field(min_length=1, max_length=20)

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("sk-"):
            raise ValueError("OpenAI key must start with 'sk-'")
        return value


class TaskResult(BaseModel):
    title: str
    description: str


class GenerateTasksResponse(BaseModel):
    tasks: list[TaskResult]


app = FastAPI(title="Sentry Tasks API", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8088").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

rate_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
)

REQUEST_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "40"))


def is_unclear_title(title: str) -> bool:
    normalized = title.strip().lower()
    if len(normalized) < 10:
        return True
    unclear_patterns = {
        "unknown error",
        "unknownexception",
        "error",
        "exception",
        "internal server error",
        "something went wrong",
        "request failed",
    }
    return normalized in unclear_patterns


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": issue.get("title"),
        "culprit": issue.get("culprit"),
        "shortId": issue.get("shortId"),
        "permalink": issue.get("permalink"),
        "count": issue.get("count"),
        "userCount": issue.get("userCount"),
        "firstSeen": issue.get("firstSeen"),
        "lastSeen": issue.get("lastSeen"),
        "metadata": issue.get("metadata", {}),
    }


def sanitize_text(text: str) -> str:
    # Plain text output to avoid accidental HTML/script rendering in UI.
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()


def generate_task_title(client: OpenAI, issue: dict[str, Any], model: str, temperature: float) -> str:
    issue_title = (issue.get("title") or "").strip()
    if issue_title and not is_unclear_title(issue_title):
        return issue_title[:80]

    prompt = TITLE_PROMPT_TEMPLATE.format(issue_json=json.dumps(issue, ensure_ascii=False, indent=2))
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You write concise and clear bug-fix task titles."},
            {"role": "user", "content": prompt},
        ],
        temperature=min(temperature, 0.7),
        timeout=REQUEST_TIMEOUT,
    )
    generated = (response.choices[0].message.content or "").strip().replace("\n", " ")
    if generated:
        return generated[:80]
    return issue_title[:80] if issue_title else "Исправить ошибку из Sentry"


def generate_task_description(client: OpenAI, issue: dict[str, Any], model: str, temperature: float) -> str:
    prompt = TASK_PROMPT_TEMPLATE.format(
        issue_json=json.dumps(issue, ensure_ascii=False, indent=2),
        output_format=TASK_OUTPUT_FORMAT.format(
            count=issue.get("count", "N/A"),
            permalink=issue.get("permalink", "N/A"),
        ),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that parses error logs and creates Jira-style tickets.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        timeout=REQUEST_TIMEOUT,
    )
    return sanitize_text(response.choices[0].message.content or "")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/tasks/generate", response_model=GenerateTasksResponse)
def generate_tasks(request: Request, payload: GenerateTasksRequest) -> GenerateTasksResponse:
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    if not rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    total_payload_size = len(json.dumps(payload.model_dump(), ensure_ascii=False))
    if total_payload_size > 500_000:
        raise HTTPException(status_code=413, detail="Payload too large")

    try:
        client = OpenAI(api_key=payload.openai_api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid OpenAI client setup: {exc}") from exc

    tasks: list[TaskResult] = []
    try:
        for issue in payload.issues:
            normalized = normalize_issue(issue)
            title = sanitize_text(generate_task_title(client, normalized, payload.model, payload.temperature))
            description = generate_task_description(client, normalized, payload.model, payload.temperature)
            tasks.append(TaskResult(title=title, description=description))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Validation error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    return GenerateTasksResponse(tasks=tasks)
