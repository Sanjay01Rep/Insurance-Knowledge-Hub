"""ChromaDB index + local sentence-transformer embeddings."""

from __future__ import annotations

import threading
from typing import Any

from db import DATA_DIR, logger

CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION_NAME = "knowledge_chunks"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_collection = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("loading embedding model %s", EMBED_MODEL_NAME)
            _model = SentenceTransformer(EMBED_MODEL_NAME)
            logger.info("embedding model ready")
        return _model


def preload_embedding_model() -> None:
    """Load the local search model in the background so the first Ask is quicker."""
    thread = threading.Thread(target=_get_model, daemon=True, name="preload-embeddings")
    thread.start()


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def delete_document_chunks(document_id: str) -> None:
    collection = _get_collection()
    existing = collection.get(where={"document_id": document_id}, include=[])
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)
        logger.info("removed %s indexed chunks for id=%s", len(ids), document_id)


def index_chunks(document_id: str, chunks: list[dict[str, Any]]) -> int:
    delete_document_chunks(document_id)
    if not chunks:
        return 0
    model = _get_model()
    texts = [chunk["content"] for chunk in chunks]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    ids = [f"{document_id}_{chunk['chunk_index']}" for chunk in chunks]
    metadatas = [_clean_metadata(chunk["metadata"]) for chunk in chunks]
    _get_collection().upsert(
        ids=ids,
        embeddings=vectors.tolist(),
        documents=texts,
        metadatas=metadatas,
    )
    logger.info("indexed %s chunks id=%s", len(chunks), document_id)
    return len(chunks)


def get_chunks_for_document(document_id: str) -> list[dict[str, Any]]:
    result = _get_collection().get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    rows = []
    ids = result.get("ids") or []
    docs = result.get("documents") or []
    metas = result.get("metadatas") or []
    for i, chunk_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        rows.append(
            {
                "id": chunk_id,
                "content": docs[i] if i < len(docs) else "",
                "metadata": meta or {},
            }
        )
    rows.sort(key=lambda row: int(row["metadata"].get("chunk_index") or 0))
    return rows


def search_chunks(
    query: str,
    *,
    n_results: int = 6,
    max_distance: float = 0.72,
) -> list[dict[str, Any]]:
    """Return the most relevant chunks. Empty list if nothing is close enough."""
    text = (query or "").strip()
    if not text:
        return []
    collection = _get_collection()
    if collection.count() == 0:
        return []
    model = _get_model()
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    result = collection.query(
        query_embeddings=[vector.tolist()],
        n_results=min(n_results, max(collection.count(), 1)),
        include=["documents", "metadatas", "distances"],
    )
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    hits: list[dict[str, Any]] = []
    for i, content in enumerate(docs):
        distance = float(distances[i]) if i < len(distances) else 1.0
        if distance > max_distance:
            continue
        meta = metas[i] if i < len(metas) else {}
        hits.append(
            {
                "id": ids[i] if i < len(ids) else "",
                "content": content or "",
                "metadata": meta or {},
                "distance": distance,
            }
        )
    logger.info("retrieval hits=%s query_len=%s", len(hits), len(text))
    return hits


def _clean_metadata(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in meta.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned
