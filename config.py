"""Load .env and pick the answer model the user set up. Never log secrets."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_PLACEHOLDERS = {
    "",
    "paste-your-key-here",
    "your-key-here",
    "your-openai-key-here",
    "your-anthropic-key-here",
    "your-azure-key-here",
    "your-google-key-here",
    "your-search-engine-id-here",
    "your-tavily-key-here",
}

PROVIDER_ORDER = ("gemini", "openai", "anthropic", "cursor", "azure")

PROVIDER_LABELS = {
    "gemini": "Gemini (Google)",
    "openai": "ChatGPT (OpenAI)",
    "anthropic": "Claude (Anthropic)",
    "cursor": "Cursor",
    "azure": "Azure OpenAI",
}

PROVIDER_SHORT = {
    "gemini": "Gemini",
    "openai": "ChatGPT",
    "anthropic": "Claude",
    "cursor": "Cursor",
    "azure": "Azure OpenAI",
}

PROVIDER_KEY_FIELDS = {
    "gemini": [
        {"name": "GEMINI_API_KEY", "label": "Gemini API key", "secret": True, "placeholder": "Paste API key"},
    ],
    "openai": [
        {"name": "OPENAI_API_KEY", "label": "ChatGPT API key", "secret": True, "placeholder": "Paste API key"},
    ],
    "anthropic": [
        {"name": "ANTHROPIC_API_KEY", "label": "Claude API key", "secret": True, "placeholder": "Paste API key"},
    ],
    "cursor": [
        {"name": "CURSOR_API_KEY", "label": "Cursor API key", "secret": True, "placeholder": "Paste API key"},
    ],
    "azure": [
        {"name": "AZURE_OPENAI_API_KEY", "label": "Azure OpenAI API key", "secret": True, "placeholder": "Paste API key"},
        {"name": "AZURE_OPENAI_ENDPOINT", "label": "Azure endpoint", "secret": False, "placeholder": "https://….openai.azure.com"},
        {"name": "AZURE_OPENAI_DEPLOYMENT", "label": "Deployment name", "secret": False, "placeholder": "e.g. gpt-4o-mini"},
    ],
}

KEY_HELP = {
    "gemini": {
        "label": "Get a Gemini API key (free)",
        "url": "https://aistudio.google.com/apikey",
        "steps": "Sign in with Google → Create API key → copy it.",
    },
    "openai": {
        "label": "Get a ChatGPT API key",
        "url": "https://platform.openai.com/api-keys",
        "steps": "Sign in → Create new secret key → copy it once.",
    },
    "anthropic": {
        "label": "Get a Claude API key",
        "url": "https://console.anthropic.com/settings/keys",
        "steps": "Sign in → Create key → copy it once.",
    },
    "cursor": {
        "label": "Get a Cursor API key",
        "url": "https://cursor.com/dashboard/integrations",
        "steps": "Sign in → Integrations → create a key → copy it.",
    },
    "azure": {
        "label": "Get Azure OpenAI settings",
        "url": "https://portal.azure.com/",
        "steps": "Open your Azure OpenAI resource → Keys and Endpoint, plus the deployment name.",
    },
    "tavily": {
        "label": "Get a Tavily key",
        "url": "https://app.tavily.com/",
        "steps": "Sign in → API Keys → copy the key.",
    },
}

TAVILY_FIELD = {
    "name": "TAVILY_API_KEY",
    "label": "Tavily API key",
    "secret": True,
    "placeholder": "Paste Tavily key",
}

MISSING_ANY = (
    "Answers are not set up yet. Paste a key in the Auth panel on the right, then click Save key."
)


def reload_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def is_set(name: str) -> bool:
    value = env(name)
    if not value:
        return False
    if value.lower() in _PLACEHOLDERS:
        return False
    if value.lower().startswith("paste-"):
        return False
    return True


def available_providers() -> list[str]:
    found: list[str] = []
    if is_set("GEMINI_API_KEY"):
        found.append("gemini")
    if is_set("OPENAI_API_KEY"):
        found.append("openai")
    if is_set("ANTHROPIC_API_KEY"):
        found.append("anthropic")
    if is_set("CURSOR_API_KEY"):
        found.append("cursor")
    if is_set("AZURE_OPENAI_API_KEY") and is_set("AZURE_OPENAI_ENDPOINT") and is_set("AZURE_OPENAI_DEPLOYMENT"):
        found.append("azure")
    return found


def web_search_configured() -> bool:
    return is_set("TAVILY_API_KEY")


def list_provider_choices() -> list[dict]:
    """Built-in models plus any extra models the user saved."""
    from custom_models import list_custom_models

    reload_env()
    ready = set(available_providers())
    rows: list[dict] = []
    for provider in PROVIDER_ORDER:
        rows.append(
            {
                "id": provider,
                "label": PROVIDER_SHORT[provider],
                "full_label": PROVIDER_LABELS[provider],
                "ready": provider in ready,
                "model": _model_for(provider) if provider in ready else "",
                "custom": False,
            }
        )
    for item in list_custom_models():
        rows.append(
            {
                "id": item["id"],
                "label": item["name"],
                "full_label": item["name"],
                "ready": item["ready"],
                "model": item["model"],
                "custom": True,
            }
        )
    return rows


def default_provider() -> str:
    reload_env()
    ready = available_providers()
    requested = env("ANSWER_PROVIDER").lower()
    if requested in ready:
        return requested
    if ready:
        return ready[0]
    return "gemini"


def resolve_answer_setup(preferred: str | None = None) -> dict:
    """Return which cloud model will write answers. Local document search does not need this."""
    from custom_models import get_custom_model, is_custom_id

    reload_env()
    found = available_providers()
    requested = (preferred or env("ANSWER_PROVIDER") or "").strip()
    requested_lower = requested.lower()

    if is_custom_id(requested):
        custom = get_custom_model(requested)
        if not custom:
            return {
                "ok": False,
                "provider": requested,
                "label": "Saved model",
                "model": "",
                "custom": True,
                "error": "That saved model was deleted. Pick another model, or add it again in Auth.",
                "web_ok": web_search_configured(),
            }
        if not custom.get("ready"):
            return {
                "ok": False,
                "provider": requested,
                "label": custom["name"],
                "model": custom.get("model") or "",
                "custom": True,
                "error": f"{custom['name']} is selected, but its key is empty. Paste it in Auth on the right.",
                "web_ok": web_search_configured(),
            }
        return {
            "ok": True,
            "provider": "custom",
            "custom_id": custom["id"],
            "label": custom["name"],
            "model": custom["model"],
            "base_url": custom["base_url"],
            "api_key": custom["api_key"],
            "custom": True,
            "error": None,
            "web_ok": web_search_configured(),
        }

    if requested_lower:
        if requested_lower not in PROVIDER_LABELS:
            return {
                "ok": False,
                "provider": None,
                "label": "",
                "model": "",
                "custom": False,
                "error": (
                    "Choose Gemini, ChatGPT, Claude, Cursor, Azure OpenAI, or one of your saved models. "
                    f"“{requested}” is not a known model."
                ),
                "web_ok": web_search_configured(),
            }
        if requested_lower not in found:
            return {
                "ok": False,
                "provider": requested_lower,
                "label": PROVIDER_LABELS[requested_lower],
                "model": "",
                "custom": False,
                "error": _missing_for(requested_lower),
                "web_ok": web_search_configured(),
            }
        provider = requested_lower
    elif found:
        provider = found[0]
    else:
        return {
            "ok": False,
            "provider": None,
            "label": "",
            "model": "",
            "custom": False,
            "error": MISSING_ANY,
            "web_ok": web_search_configured(),
        }

    model = _model_for(provider)
    return {
        "ok": True,
        "provider": provider,
        "label": PROVIDER_LABELS[provider],
        "model": model,
        "custom": False,
        "error": None,
        "web_ok": web_search_configured(),
    }


def _model_for(provider: str) -> str:
    if provider == "gemini":
        return env("GEMINI_MODEL") or "gemini-3.7-flash"
    if provider == "openai":
        return env("OPENAI_MODEL") or "gpt-4o-mini"
    if provider == "anthropic":
        return env("ANTHROPIC_MODEL") or "claude-sonnet-4-5"
    if provider == "cursor":
        return env("CURSOR_MODEL") or "composer-2.5"
    if provider == "azure":
        return env("AZURE_OPENAI_DEPLOYMENT")
    return ""


def _missing_for(provider: str) -> str:
    name = PROVIDER_SHORT.get(provider, provider)
    if provider == "azure":
        return (
            f"{name} is selected, but Azure settings are incomplete. "
            "Paste them in Auth on the right, or pick another model."
        )
    return f"{name} is selected, but its key is empty. Paste it in Auth on the right, or pick another model."


def provider_key_ready(provider: str) -> bool:
    reload_env()
    fields = PROVIDER_KEY_FIELDS.get(provider) or []
    return bool(fields) and all(is_set(field["name"]) for field in fields)


def auth_status(provider: str) -> dict:
    """UI-safe status for the Auth panel. Never includes the secret."""
    reload_env()
    short = PROVIDER_SHORT.get(provider, provider)
    if provider_key_ready(provider):
        return {
            "present": True,
            "message": f"{short} key loaded from .env · Ready.",
        }
    return {
        "present": False,
        "message": f"No {short} key in .env — paste it below.",
    }


def tavily_status() -> dict:
    reload_env()
    if web_search_configured():
        return {"present": True, "message": "Tavily key loaded from .env · Ready."}
    return {"present": False, "message": "No Tavily key in .env — paste it below for web fallback."}


def save_env_value(name: str, value: str) -> None:
    """Write one key into .env and apply it immediately. Never log the value."""
    value = (value or "").strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Paste a valid key first.")
    if value.lower() in _PLACEHOLDERS or value.lower().startswith("paste-"):
        raise ValueError("Paste a real key, not a placeholder.")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise ValueError("That setting cannot be saved.")

    env_path = ROOT / ".env"
    line = f"{name}={value}"
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        pattern = re.compile(rf"^[ \t]*{re.escape(name)}[ \t]*=.*$", re.M)
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            trimmed = text.rstrip()
            text = f"{trimmed}\n{line}\n" if trimmed else f"{line}\n"
        env_path.write_text(text, encoding="utf-8")
    else:
        env_path.write_text(f"{line}\n", encoding="utf-8")
    os.environ[name] = value
    reload_env()
