"""Saved extra models (not the built-in ones). Keys stay on this PC."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from db import DATA_DIR, logger

CUSTOM_PATH = DATA_DIR / "custom_models.json"

CUSTOM_API_KINDS = {
    "openai": {
        "label": "ChatGPT / OpenAI",
        "base_url": "https://api.openai.com/v1",
        "help_url": "https://platform.openai.com/api-keys",
        "help_label": "Get an OpenAI API key",
        "example_model": "gpt-4o-mini",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "help_url": "https://console.groq.com/keys",
        "help_label": "Get a Groq API key",
        "example_model": "llama-3.1-8b-instant",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "help_url": "https://platform.deepseek.com/api_keys",
        "help_label": "Get a DeepSeek API key",
        "example_model": "deepseek-chat",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "help_url": "https://aistudio.google.com/apikey",
        "help_label": "Get a Gemini API key",
        "example_model": "gemini-3.7-flash",
    },
    "other": {
        "label": "Other (type the address)",
        "base_url": "",
        "help_url": "",
        "help_label": "",
        "example_model": "the model id from that provider",
    },
}


def _path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return CUSTOM_PATH


def _load_raw() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("could not read custom models")
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict) and item.get("id")]


def _save_raw(rows: list[dict]) -> None:
    _path().write_text(json.dumps(rows, indent=2), encoding="utf-8")


def is_custom_id(provider_id: str | None) -> bool:
    return str(provider_id or "").startswith("custom_")


def list_custom_models(*, include_secrets: bool = False) -> list[dict]:
    rows = []
    for item in _load_raw():
        key = str(item.get("api_key") or "").strip()
        row = {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or "Custom model").strip() or "Custom model",
            "model": str(item.get("model") or "").strip(),
            "base_url": str(item.get("base_url") or "").strip(),
            "kind": str(item.get("kind") or "other"),
            "ready": bool(key),
            "custom": True,
        }
        if include_secrets:
            row["api_key"] = key
        rows.append(row)
    return rows


def get_custom_model(model_id: str) -> dict | None:
    for item in list_custom_models(include_secrets=True):
        if item["id"] == model_id:
            return item
    return None


def save_custom_model(
    *,
    name: str,
    model: str,
    api_key: str,
    kind: str = "other",
    base_url: str = "",
) -> dict:
    name = (name or "").strip()
    model = (model or "").strip()
    api_key = (api_key or "").strip()
    kind = (kind or "other").strip()
    preset = CUSTOM_API_KINDS.get(kind) or CUSTOM_API_KINDS["other"]
    base_url = (base_url or "").strip() or str(preset.get("base_url") or "")
    if not name:
        raise ValueError("Give this model a name, e.g. Groq or Gemini.")
    if not model:
        raise ValueError("Enter the model name from the provider, e.g. gpt-4o-mini or llama-3.1-8b.")
    if not api_key:
        raise ValueError("Paste an API key first.")
    if "\n" in api_key or "\r" in api_key:
        raise ValueError("That key is not valid.")
    if not base_url:
        raise ValueError("Enter the API address, or pick a known provider.")

    model_id = f"custom_{uuid.uuid4().hex[:12]}"
    rows = _load_raw()
    rows.append(
        {
            "id": model_id,
            "name": name,
            "model": model,
            "api_key": api_key,
            "base_url": base_url.rstrip("/"),
            "kind": kind,
        }
    )
    _save_raw(rows)
    logger.info("custom model saved id=%s", model_id)
    return {"id": model_id, "name": name, "model": model, "ready": True, "custom": True}


def update_custom_model(
    model_id: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> None:
    rows = _load_raw()
    found = False
    for item in rows:
        if item.get("id") != model_id:
            continue
        found = True
        if api_key is not None:
            key = api_key.strip()
            if not key:
                raise ValueError("Paste an API key first.")
            item["api_key"] = key
        if model is not None and model.strip():
            item["model"] = model.strip()
        if base_url is not None and base_url.strip():
            item["base_url"] = base_url.strip().rstrip("/")
    if not found:
        raise ValueError("That saved model is no longer here.")
    _save_raw(rows)


def delete_custom_model(model_id: str) -> None:
    if not is_custom_id(model_id):
        raise ValueError("Built-in models cannot be deleted.")
    rows = [item for item in _load_raw() if item.get("id") != model_id]
    _save_raw(rows)
    logger.info("custom model deleted id=%s", model_id)
