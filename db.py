"""Local document storage: SQLite metadata + original files on disk."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MyD365LearningAssistant"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "knowledge.db"
LOG_PATH = DATA_DIR / "app.log"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
MAX_FILE_BYTES = 25 * 1024 * 1024
TYPE_ERROR = "Please select a supported file type (PDF, DOCX, XLSX, PPTX, TXT)."
SIZE_ERROR = "This file is too large. Please choose a file under 25 MB."
SAVE_ERROR = "We couldn't save this document. Please try again."
DELETE_ERROR = "We couldn't delete this document. Please try again."

logger = logging.getLogger("insurance_learning")


def _setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def init_db() -> None:
    _setup_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                module TEXT,
                topic TEXT,
                description TEXT,
                version TEXT,
                uploaded_at TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                chunk_count INTEGER DEFAULT 0,
                error_summary TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        _ensure_columns(conn)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    if "chunk_count" not in existing:
        conn.execute("ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0")
    if "error_summary" not in existing:
        conn.execute("ALTER TABLE documents ADD COLUMN error_summary TEXT")
    conn.commit()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def is_allowed_file(filename: str) -> bool:
    return extension_of(filename) in ALLOWED_EXTENSIONS


def list_documents() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_document(doc_id: str) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def save_document(
    *,
    filename: str,
    data: bytes,
    module: str = "",
    topic: str = "",
    description: str = "",
    version: str = "",
) -> tuple[dict | None, str | None]:
    init_db()
    name = Path(filename).name.strip() or "untitled"
    if not is_allowed_file(name):
        logger.info("upload rejected: unsupported type name=%s", name)
        return None, TYPE_ERROR
    if len(data) > MAX_FILE_BYTES:
        logger.info("upload rejected: too large bytes=%s name=%s", len(data), name)
        return None, SIZE_ERROR
    if not data:
        logger.info("upload rejected: empty file name=%s", name)
        return None, "This file looks empty. Please choose another file."

    doc_id = str(uuid.uuid4())
    ext = extension_of(name)
    stored = UPLOADS_DIR / f"{doc_id}{ext}"
    try:
        stored.write_bytes(data)
    except OSError:
        logger.exception("failed to write upload id=%s", doc_id)
        return None, SAVE_ERROR

    record = {
        "id": doc_id,
        "name": name,
        "file_type": ext.lstrip("."),
        "module": (module or "").strip(),
        "topic": (topic or "").strip(),
        "description": (description or "").strip(),
        "version": (version or "").strip(),
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "storage_path": str(stored),
        "processing_status": "pending",
        "chunk_count": 0,
        "error_summary": "",
    }
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, name, file_type, module, topic, description, version,
                    uploaded_at, storage_path, processing_status, chunk_count, error_summary
                ) VALUES (
                    :id, :name, :file_type, :module, :topic, :description, :version,
                    :uploaded_at, :storage_path, :processing_status, :chunk_count, :error_summary
                )
                """,
                record,
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("failed to save metadata id=%s", doc_id)
        try:
            stored.unlink(missing_ok=True)
        except OSError:
            pass
        return None, SAVE_ERROR

    logger.info("document uploaded id=%s type=%s status=pending", doc_id, record["file_type"])
    return record, None


def update_document_status(
    doc_id: str,
    status: str,
    *,
    chunk_count: int | None = None,
    error_summary: str | None = None,
) -> None:
    init_db()
    fields = ["processing_status = ?"]
    values: list[object] = [status]
    if chunk_count is not None:
        fields.append("chunk_count = ?")
        values.append(chunk_count)
    if error_summary is not None:
        fields.append("error_summary = ?")
        values.append(error_summary)
    values.append(doc_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE documents SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    logger.info("status id=%s -> %s chunks=%s", doc_id, status, chunk_count)


def list_unfinished_documents() -> list[dict]:
    return [
        doc
        for doc in list_documents()
        if (doc.get("processing_status") or "") in {"pending", "processing"}
    ]


def delete_document(doc_id: str) -> str | None:
    init_db()
    doc = get_document(doc_id)
    if not doc:
        return DELETE_ERROR
    path = Path(doc["storage_path"])
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("failed to delete file id=%s", doc_id)
        return DELETE_ERROR
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("failed to delete metadata id=%s", doc_id)
        return DELETE_ERROR
    logger.info("document deleted id=%s", doc_id)
    try:
        from indexer import delete_document_chunks

        delete_document_chunks(doc_id)
    except Exception:
        logger.exception("could not remove indexed chunks id=%s", doc_id)
    return None


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> dict:
    init_db()
    record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "sources_json": json.dumps(sources or []),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, sources_json, created_at
            ) VALUES (
                :id, :conversation_id, :role, :content, :sources_json, :created_at
            )
            """,
            record,
        )
        conn.commit()
    return {
        "id": record["id"],
        "role": role,
        "content": content,
        "sources": sources or [],
        "created_at": record["created_at"],
    }


def list_messages(conversation_id: str) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id,),
        ).fetchall()
    messages = []
    for row in rows:
        item = dict(row)
        try:
            item["sources"] = json.loads(item.get("sources_json") or "[]")
        except json.JSONDecodeError:
            item["sources"] = []
        messages.append(item)
    return messages


def count_ready_documents() -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM documents WHERE processing_status = 'ready'"
        ).fetchone()
    return int(row["n"] if row else 0)
