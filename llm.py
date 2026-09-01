"""Call whichever cloud model the user configured. Do not log keys or document text."""

from __future__ import annotations

import tempfile
from pathlib import Path

from config import env
from db import DATA_DIR, logger

# Prefer gemini-3.7-flash; older Flash names 404 for new Google AI Studio keys.
GEMINI_MODEL_FALLBACKS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)


class AnswerModelError(Exception):
    """User-facing model failure. Message is safe to show in the UI."""


def complete(prompt: str, setup: dict) -> str:
    provider = setup["provider"]
    if provider == "gemini":
        text, used = _gemini(prompt, setup["model"])
        setup["model_used"] = used
        return text
    if provider == "openai":
        setup["model_used"] = setup.get("model") or ""
        return _openai_compatible(
            prompt,
            model=setup["model"],
            api_key=env("OPENAI_API_KEY"),
            base_url="https://api.openai.com/v1",
        )
    if provider == "custom":
        setup["model_used"] = setup.get("model") or ""
        return _openai_compatible(
            prompt,
            model=setup["model"],
            api_key=setup.get("api_key") or "",
            base_url=setup.get("base_url") or "https://api.openai.com/v1",
        )
    if provider == "anthropic":
        setup["model_used"] = setup.get("model") or ""
        return _anthropic(prompt, setup["model"])
    if provider == "azure":
        setup["model_used"] = setup.get("model") or env("AZURE_OPENAI_DEPLOYMENT") or ""
        return _azure(prompt)
    if provider == "cursor":
        setup["model_used"] = setup.get("model") or ""
        return _cursor(prompt, setup["model"])
    raise RuntimeError(f"unknown provider {provider}")


def _gemini(prompt: str, model: str) -> tuple[str, str]:
    import httpx

    requested = (model or "").strip()
    names: list[str] = []
    if requested:
        names.append(requested)
    for fallback in GEMINI_MODEL_FALLBACKS:
        if fallback not in names:
            names.append(fallback)

    last_status = 0
    for name in names:
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent",
                headers={
                    "x-goog-api-key": env("GEMINI_API_KEY"),
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
                },
                timeout=90.0,
            )
        except httpx.TimeoutException:
            raise AnswerModelError("Gemini took too long to answer. Please try again.")
        last_status = response.status_code
        if response.status_code == 200:
            text = _gemini_text(response.json())
            if not str(text).strip():
                logger.info("gemini empty response model=%s", name)
                continue
            if name != requested:
                logger.info("gemini using model=%s (requested model was not available)", name)
            return text, name
        google_code = _gemini_status_code(response)
        logger.info("gemini http=%s model=%s google_status=%s", response.status_code, name, google_code)
        if response.status_code in (404, 503) or google_code in (404, 503):
            continue
        raise AnswerModelError(_gemini_user_error(response.status_code, google_code))

    raise AnswerModelError(
        "Google Gemini’s older Flash models are shut down. Set GEMINI_MODEL=gemini-3.7-flash in .env."
        if last_status == 404
        else "Gemini could not write the answer just now. Please try again."
    )


def _gemini_text(data: dict) -> str:
    parts = []
    for candidate in data.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            parts.append(part.get("text") or "")
    return "".join(parts)


def _gemini_status_code(response) -> int:
    try:
        payload = response.json()
    except Exception:
        return 0
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return 0
    try:
        return int(err.get("code") or 0)
    except (TypeError, ValueError):
        return 0


def _gemini_user_error(http_status: int, google_code: int) -> str:
    code = google_code or http_status
    if code in (401, 403):
        return (
            "That Gemini key was refused. Create a new key at https://aistudio.google.com/apikey "
            "and paste it in Auth (or GEMINI_API_KEY in .env)."
        )
    if code == 429:
        return "Gemini’s free limit was reached. Wait a minute, then ask again."
    if code == 404:
        return (
            "That Gemini model name is no longer available. Set GEMINI_MODEL=gemini-3.7-flash in .env."
        )
    return "Gemini could not write the answer just now. Please try again."


def _openai_compatible(prompt: str, *, model: str, api_key: str, base_url: str) -> str:
    import httpx

    root = (base_url or "https://api.openai.com/v1").rstrip("/")
    response = httpx.post(
        f"{root}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90.0,
    )
    response.raise_for_status()
    data = response.json()
    return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def _anthropic(prompt: str, model: str) -> str:
    import httpx

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": env("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 2500,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90.0,
    )
    response.raise_for_status()
    data = response.json()
    parts = []
    for block in data.get("content") or []:
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "".join(parts)


def _azure(prompt: str) -> str:
    import httpx

    endpoint = env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    deployment = env("AZURE_OPENAI_DEPLOYMENT")
    version = env("AZURE_OPENAI_API_VERSION") or "2024-10-21"
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"
    response = httpx.post(
        url,
        params={"api-version": version},
        headers={
            "api-key": env("AZURE_OPENAI_API_KEY"),
            "Content-Type": "application/json",
        },
        json={
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90.0,
    )
    response.raise_for_status()
    data = response.json()
    return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def _cursor(prompt: str, model: str) -> str:
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

    workdir = Path(tempfile.mkdtemp(prefix="ask-", dir=str(DATA_DIR)))
    options_kwargs = {
        "api_key": env("CURSOR_API_KEY"),
        "model": model,
        "local": LocalAgentOptions(cwd=str(workdir)),
    }
    try:
        options = AgentOptions(**options_kwargs, tools=[])
    except TypeError:
        options = AgentOptions(**options_kwargs)

    logger.info("cursor request started")
    result = Agent.prompt(prompt, options)
    status = getattr(result, "status", "")
    text = getattr(result, "result", None) or ""
    if status and status != "finished":
        logger.info("cursor request status=%s", status)
        raise RuntimeError(f"cursor status {status}")
    logger.info("cursor request finished")
    return str(text)
