"""Call whichever cloud model the user configured. Do not log keys or document text."""

from __future__ import annotations

import tempfile
from pathlib import Path

from config import env
from db import DATA_DIR, logger


def complete(prompt: str, setup: dict) -> str:
    provider = setup["provider"]
    if provider == "openai":
        return _openai(prompt, setup["model"])
    if provider == "anthropic":
        return _anthropic(prompt, setup["model"])
    if provider == "azure":
        return _azure(prompt)
    if provider == "cursor":
        return _cursor(prompt, setup["model"])
    raise RuntimeError(f"unknown provider {provider}")


def _openai(prompt: str, model: str) -> str:
    import httpx

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {env('OPENAI_API_KEY')}",
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
