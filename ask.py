"""Local document search first, then a configured cloud model. Tavily only gets the question."""

from __future__ import annotations

from config import resolve_answer_setup  # used by Ask tab model picker
from db import count_ready_documents, logger
from indexer import search_chunks
from llm import complete
from web_search import search_web

SYSTEM_RULES = """
You are a learning assistant helping someone new to D365 and the insurance domain
understand their own uploaded documents and the underlying concepts.

Rules, in order:
1. If the retrieved document context answers the question, answer from it and cite
   the source document (and sheet/section if available).
2. Never invent specifics about "my" documents/project that aren't in the retrieved
   context. If nothing relevant was retrieved, say plainly:
   "I couldn't find this in your uploaded documents."
3. You MAY still teach general D365 or insurance domain knowledge not found in the
   documents — this is a learning tool, general explanation is welcome — but label it
   clearly, e.g. "General context (not from your documents):" so it's never confused
   with something specific to my project.
4. If public web search snippets are provided, they are NOT the user's files and NOT
   ICEA LION project facts. Label them: "From the web (not from your documents):"
5. Explain things at a beginner level unless I show I already understand the term —
   don't assume prior D365 knowledge.
6. Never fabricate a source citation.
""".strip()

ASK_FAIL = "I couldn't get an answer just now. Please try again."
NO_DOCS = "Upload at least one document and wait until it shows Ready, then ask again."
NOT_IN_DOCS = "I couldn't find this in your uploaded documents."


def get_answer_setup(provider: str | None = None) -> dict:
    return resolve_answer_setup(provider)


def source_label(hit: dict) -> str:
    meta = hit.get("metadata") or {}
    name = str(meta.get("document_name") or "Document")
    locator = str(meta.get("source_locator") or "").strip()
    if locator:
        return f"{name} — {locator}"
    sheet = str(meta.get("sheet_name") or "").strip()
    if sheet:
        return f"{name} — Sheet: {sheet}"
    return name


def unique_sources(hits: list[dict]) -> list[dict]:
    seen: set[str] = set()
    sources: list[dict] = []
    for hit in hits:
        label = source_label(hit)
        if label in seen:
            continue
        seen.add(label)
        meta = hit.get("metadata") or {}
        sources.append(
            {
                "kind": "document",
                "label": label,
                "document_name": meta.get("document_name") or "",
                "source_locator": meta.get("source_locator") or "",
            }
        )
    return sources


def _search_query(question: str, history: list[dict]) -> str:
    prior = [item["content"] for item in history[-4:] if item.get("content")]
    if not prior:
        return question
    return "Previous conversation:\n" + "\n".join(prior) + "\n\nCurrent question:\n" + question


def _web_block(web_hits: list[dict]) -> str:
    if not web_hits:
        return "(no web search results)"
    lines = []
    for i, hit in enumerate(web_hits, start=1):
        lines.append(
            f"[Web {i}: {hit.get('label') or ''}]\n"
            f"URL: {hit.get('url') or ''}\n"
            f"{(hit.get('snippet') or '').strip()}"
        )
    return "\n\n".join(lines)


def _build_prompt(question: str, history: list[dict], hits: list[dict], web_hits: list[dict]) -> str:
    if hits:
        blocks = []
        for i, hit in enumerate(hits, start=1):
            blocks.append(
                f"[Source {i}: {source_label(hit)}]\n{(hit.get('content') or '').strip()}"
            )
        retrieved = "\n\n".join(blocks)
        context_note = (
            "Retrieved document context is below. Use it for anything specific to the user's files. "
            "Do not use web search for this question — documents were found."
        )
        web_note = "No web results are included because the documents answered the search."
        web_text = "(not used)"
    else:
        retrieved = "(no relevant passages were retrieved from the uploaded documents)"
        context_note = (
            f"No relevant document passages were retrieved. You must say: {NOT_IN_DOCS} "
            "You may then add general D365/insurance teaching, clearly labelled. "
            "If web snippets are present, summarise them under "
            '"From the web (not from your documents):" — they are public internet results, '
            "not this project's files."
        )
        web_note = "Public web snippets (question only was sent to Tavily — never the user's files):"
        web_text = _web_block(web_hits)

    history_text = "None yet."
    if history:
        lines = []
        for item in history[-8:]:
            role = "User" if item.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {item.get('content')}")
        history_text = "\n".join(lines)

    return f"""{SYSTEM_RULES}

{context_note}

Conversation so far:
{history_text}

Retrieved passages:
{retrieved}

{web_note}
{web_text}

User question:
{question}

Write the answer only. Do not edit files. Do not use tools. Do not invent sources.
"""


def answer_question(
    question: str,
    history: list[dict] | None = None,
    provider: str | None = None,
) -> dict:
    history = history or []
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "Please type a question first.", "sources": []}

    if count_ready_documents() == 0:
        return {"ok": False, "error": NO_DOCS, "sources": []}

    # 1. Free local search in uploaded documents. Files never leave this PC.
    hits = search_chunks(_search_query(question, history))
    sources = unique_sources(hits)
    logger.info("ask retrieval sources=%s", [item["label"] for item in sources])

    setup = resolve_answer_setup(provider)
    if not setup.get("ok"):
        return {"ok": False, "error": setup.get("error") or ASK_FAIL, "sources": sources}

    # 2. Tavily Search API only when documents miss — question text only.
    web_hits: list[dict] = []
    if not hits:
        web_hits = search_web(question)
        for hit in web_hits:
            sources.append(
                {
                    "kind": "web",
                    "label": hit.get("label") or hit.get("url") or "Web result",
                    "url": hit.get("url") or "",
                }
            )

    prompt = _build_prompt(question, history, hits, web_hits)
    try:
        text = complete(prompt, setup)
    except Exception:
        logger.exception("answer model failed provider=%s", setup.get("provider"))
        return {"ok": False, "error": ASK_FAIL, "sources": sources}

    if not str(text).strip():
        return {"ok": False, "error": ASK_FAIL, "sources": sources}

    text = str(text).strip()
    if not hits and NOT_IN_DOCS not in text:
        text = NOT_IN_DOCS + "\n\n" + text

    return {"ok": True, "answer": text, "sources": sources, "provider": setup.get("label")}
