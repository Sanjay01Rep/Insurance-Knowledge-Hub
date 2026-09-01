"""Insurance Learning Assistant — Streamlit app."""

from __future__ import annotations

import base64
import html
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _quiet_streamlit_library_watch() -> None:
    """Stop Streamlit from walking torch/transformers (that freeze is the hang on Ask and on Ctrl+C)."""
    try:
        from streamlit.watcher import local_sources_watcher as watcher
    except Exception:
        return

    def get_module_paths(module):
        name = getattr(module, "__name__", "") or ""
        path = str(getattr(module, "__file__", "") or "").replace("\\", "/")
        if name.startswith(
            ("transformers", "torch", "torchvision", "sentence_transformers", "chromadb", "huggingface_hub")
        ) or "/site-packages/" in path:
            return set()
        try:
            original = getattr(get_module_paths, "_original", None)
            if original:
                return original(module)
        except Exception:
            return set()
        return set()

    get_module_paths._original = watcher.get_module_paths  # type: ignore[attr-defined]
    watcher.get_module_paths = get_module_paths


_quiet_streamlit_library_watch()

st.set_page_config(
    page_title="Insurance Learning Assistant",
    page_icon=str(ROOT / "Logo" / "ICEA Lion.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ask import answer_question, suggested_questions
from export_answer import answer_docx_bytes, answer_pdf_bytes, answer_text
from config import (
    KEY_HELP,
    PROVIDER_KEY_FIELDS,
    PROVIDER_SHORT,
    TAVILY_FIELD,
    auth_status,
    default_provider,
    list_provider_choices,
    resolve_answer_setup,
    save_env_value,
    tavily_status,
)
from custom_models import (
    CUSTOM_API_KINDS,
    delete_custom_model,
    get_custom_model,
    is_custom_id,
    save_custom_model,
    update_custom_model,
)
from db import (
    add_message,
    count_ready_documents,
    delete_document,
    init_db,
    list_documents,
    list_messages,
    new_conversation_id,
    save_document,
)
from indexer import preload_embedding_model
from processing import enqueue_processing, enqueue_unfinished

APP_VERSION = "0.7.0"
APP_TITLE = "Insurance Learning Assistant"
APP_SUBTITLE = "AI-powered Insurance and D365 Knowledge Assistant"
APP_VENV = Path(os.environ.get("LOCALAPPDATA", "")) / "MyD365LearningAssistant" / ".venv"


def _using_app_python() -> bool:
    """True when this process is the AppData venv from run.bat, not a leftover system Python."""
    try:
        exe = Path(sys.executable).resolve()
        return APP_VENV.resolve() in exe.parents
    except Exception:
        return False


def _data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{payload}"


def inject_chrome() -> None:
    icea = _data_uri(ROOT / "Logo" / "ICEA Lion.png")
    simplify = _data_uri(ROOT / "Logo" / "Simplify-icon.png")
    st.markdown(
        f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap");

:root {{
  --bg: #f4f6f8;
  --ink: #1a2332;
  --muted: #5b6b7c;
  --panel: #ffffff;
  --line: #d8e0e8;
  --brand: #005696;
  --brand-deep: #003f6e;
  --gold: #c4a035;
  --ok: #1f6b3a;
  --sans: "Source Sans 3", "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --shadow: 0 8px 24px rgba(26, 35, 50, 0.06);
  --radius: 10px;
}}

html, body, [data-testid="stAppViewContainer"], .stApp {{
  background: var(--bg) !important;
  font-family: var(--sans) !important;
  color: var(--ink) !important;
}}

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu, footer, .stDeployButton,
div[data-testid="stSidebarCollapsedControl"] {{
  display: none !important;
}}

.block-container {{
  padding: 0 1rem 2.5rem !important;
  max-width: 1180px !important;
}}

.hub-topbar {{
  background: #ffffff;
  border-bottom: 1px solid var(--line);
  box-shadow: 0 1px 0 rgba(196, 160, 53, 0.55), 0 6px 18px rgba(26, 35, 50, 0.04);
  margin: 0 -1rem 1.25rem;
}}

.hub-topbar-inner {{
  width: min(1180px, calc(100% - 2rem));
  margin: 0 auto;
  padding: 0.85rem 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}

.hub-brand {{
  display: flex;
  align-items: center;
  gap: 0.9rem;
  min-width: 0;
}}

.hub-logo-icea {{
  height: 52px;
  width: auto;
  border-radius: 6px;
  flex-shrink: 0;
}}

.hub-title {{
  margin: 0;
  font-size: clamp(1.15rem, 2.4vw, 1.5rem);
  font-weight: 700;
  color: var(--brand-deep);
  letter-spacing: -0.02em;
  line-height: 1.2;
}}

.hub-brand p {{
  margin: 0.15rem 0 0;
  color: var(--muted);
  font-size: 0.88rem;
}}

.hub-right {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}}

.hub-bot {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid #b7dfc4;
  background: #eef8f1;
  color: var(--ok);
  border-radius: 999px;
  padding: 0.2rem 0.65rem 0.2rem 0.4rem;
  font-size: 0.78rem;
  font-weight: 600;
}}

.hub-version {{
  font-family: var(--mono);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--brand-deep);
  background: #eef4f9;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}}

.hub-logo-simplify {{
  height: 36px;
  width: auto;
}}

.hub-simplify-label {{
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: 0.02em;
  color: #1a1a1a;
}}

.hub-panel {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.15rem 1.2rem 1.25rem;
}}

.hub-h2 {{
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ink);
}}

.hub-panel p, .hub-muted {{
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
}}

.hub-drop {{
  margin-top: 0.9rem;
  border: 1.5px dashed var(--line);
  border-radius: 10px;
  background: #f8fafc;
  padding: 1.35rem 1rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.92rem;
  font-weight: 600;
}}

.hub-hint {{
  margin: 0.85rem 0 0;
  font-size: 0.84rem;
  color: var(--muted);
}}

.hub-side-list {{
  margin: 0.55rem 0 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.5;
}}

.hub-footer {{
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.82rem;
}}

div[data-testid="stRadio"] > label {{
  display: none !important;
}}

div[data-testid="stRadio"] div[role="radiogroup"] {{
  background: #e8eef4;
  border-radius: 10px;
  padding: 0.28rem;
  gap: 0.35rem;
  width: 100%;
  flex-wrap: wrap !important;
}}

div[data-testid="stRadio"] div[role="radiogroup"] label {{
  background: transparent !important;
  border: 0 !important;
  padding: 0.48rem 1.05rem !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  color: var(--muted) !important;
}}

div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
  background: #fff !important;
  color: var(--brand-deep) !important;
  box-shadow: var(--shadow);
}}

div[data-testid="stRadio"] input[type="radio"] {{
  position: absolute !important;
  opacity: 0 !important;
  width: 0 !important;
  height: 0 !important;
  pointer-events: none !important;
}}

.hub-model-label {{
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--muted);
  margin: 0.75rem 0 0.35rem;
}}

.hub-source {{
  font-size: 0.82rem;
  color: var(--brand-deep);
  background: #eef4f9;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.35rem 0.6rem;
  margin: 0.25rem 0 0;
}}
.hub-source-title {{
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--muted);
  margin-top: 0.55rem;
}}
.hub-source-web {{
  font-size: 0.82rem;
  color: #6b4e00;
  background: #fff8e6;
  border: 1px solid #ead9a0;
  border-radius: 8px;
  padding: 0.35rem 0.6rem;
  margin: 0.25rem 0 0;
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: #fff !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow) !important;
  padding: 0.35rem 0.15rem;
}}

.stTextInput label, .stFileUploader label, .stTextArea label {{
  font-size: 0.84rem !important;
  font-weight: 600 !important;
  color: var(--muted) !important;
}}

[data-testid="stFileUploader"] section {{
  border: 1px dashed var(--line) !important;
  background: #f8fafc !important;
  border-radius: 8px !important;
}}

.stDownloadButton button,
button[kind="primary"],
.stFormSubmitButton button {{
  background: var(--brand) !important;
  color: #fff !important;
  border: 1px solid transparent !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
}}

button[kind="secondary"] {{
  background: #fff !important;
  color: var(--brand-deep) !important;
  border: 1px solid var(--brand) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
}}

.hub-status {{
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  line-height: 1.2;
}}
.hub-status.pending {{ background: #fff8e8; color: #8a6d12; border: 1px solid #e6c86a; }}
.hub-status.processing {{ background: #eef5fa; color: var(--brand-deep); border: 1px solid #9fc0d8; }}
.hub-status.ready {{ background: #eef8f1; color: var(--ok); border: 1px solid #b7dfc4; }}
.hub-status.failed {{ background: #fdf2f2; color: #9b1c1c; border: 1px solid #efb4b4; }}

.hub-doc-name {{
  font-weight: 700;
  color: var(--ink);
  font-size: 0.92rem;
}}
.hub-doc-meta {{
  color: var(--muted);
  font-size: 0.8rem;
  margin-top: 0.15rem;
}}
.hub-expand-hint {{
  font-size: 0.82rem;
  color: var(--muted);
  margin: 0 0 0.45rem;
}}
.hub-auth-line {{
  margin: 0.35rem 0 0.55rem;
  font-size: 0.86rem;
  font-weight: 600;
  line-height: 1.4;
}}
.hub-auth-line.ok {{ color: var(--ok); }}
.hub-auth-line.warn {{ color: #8a6d12; }}
.hub-auth-hint {{
  margin: 0.45rem 0 0;
  font-size: 0.78rem;
  color: var(--muted);
}}

div[data-testid="stExpander"] {{
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  background: #fff !important;
  margin: 0.4rem 0 !important;
}}
div[data-testid="stExpander"] details summary {{
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
  cursor: pointer !important;
}}
div[data-testid="stExpander"] details:not([open]) summary::after {{
  content: "Click to expand";
  margin-left: auto;
  font-size: 0.76rem;
  font-weight: 500;
  color: var(--muted);
  background: #f4f6f8;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  white-space: nowrap;
}}
div[data-testid="stExpander"] details[open] summary::after {{
  content: "Click to collapse";
  margin-left: auto;
  font-size: 0.76rem;
  font-weight: 500;
  color: var(--brand-deep);
  background: #eef4f9;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  white-space: nowrap;
}}

</style>
<header class="hub-topbar">
  <div class="hub-topbar-inner">
    <div class="hub-brand">
      <img class="hub-logo-icea" src="{icea}" alt="ICEA LION" />
      <div>
        <div class="hub-title">{APP_TITLE}</div>
        <p>{APP_SUBTITLE}</p>
      </div>
    </div>
    <div class="hub-right">
      <span class="hub-bot"><span aria-hidden="true">🤖</span> App up</span>
      <span class="hub-version">v{APP_VERSION}</span>
      <img class="hub-logo-simplify" src="{simplify}" alt="" />
      <span class="hub-simplify-label">Simplify3x</span>
    </div>
  </div>
</header>
""",
        unsafe_allow_html=True,
    )


STATUS_LABELS = {
    "pending": "Pending",
    "processing": "Processing",
    "ready": "Ready",
    "failed": "Failed",
}


def _doc_meta_line(doc: dict) -> str:
    bits = []
    if doc.get("module"):
        bits.append(f"Module: {doc['module']}")
    if doc.get("topic"):
        bits.append(f"Topic: {doc['topic']}")
    if doc.get("version"):
        bits.append(f"Version: {doc['version']}")
    bits.append(doc.get("uploaded_at") or "")
    return " · ".join(b for b in bits if b)


def render_documents_tab() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        kind, message = flash
        if kind == "error":
            st.error(message)
        elif kind == "warning":
            st.warning(message)
        else:
            st.success(message)

    has_docs = bool(list_documents())
    if has_docs:
        with st.expander("Upload a document", expanded=False):
            _render_upload_form(show_heading=False)
    else:
        with st.container(border=True):
            _render_upload_form(show_heading=True)

    st.markdown("")
    st.caption(
        "The first document can take a few minutes while a small language model "
        "downloads to this PC. After that, search and Ask are usually quicker."
    )
    render_document_list()


def _render_upload_form(*, show_heading: bool = True) -> None:
    if show_heading:
        st.markdown('<div class="hub-h2">Upload a document</div>', unsafe_allow_html=True)
    st.caption("Tags are optional — you can upload with just a file.")
    with st.form("upload_form", clear_on_submit=True):
        uploaded = st.file_uploader(
            "File",
            type=["pdf", "docx", "xlsx", "pptx", "txt"],
            help="PDF, Word, Excel, PowerPoint, or a text file.",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            module = st.text_input("Module (optional)", placeholder="e.g. Reinsurance")
        with col_b:
            topic = st.text_input("Topic (optional)", placeholder="e.g. Claims")
        col_c, col_d = st.columns(2)
        with col_c:
            description = st.text_input("Description (optional)", placeholder="Short note to yourself")
        with col_d:
            version = st.text_input("Version (optional)", placeholder="e.g. v1.0")
        submitted = st.form_submit_button("Upload document", type="primary")

    if submitted:
        if uploaded is None:
            st.session_state.flash = ("warning", "Please choose a file first.")
            st.rerun()
        else:
            _doc, error = save_document(
                filename=uploaded.name,
                data=uploaded.getvalue(),
                module=module,
                topic=topic,
                description=description,
                version=version,
            )
            if error:
                st.session_state.flash = ("error", error)
            else:
                enqueue_processing(_doc["id"])
                st.session_state.flash = (
                    "success",
                    "Document uploaded successfully — processing has started.",
                )
            st.rerun()


@st.fragment(run_every=3)
def render_document_list_live() -> None:
    enqueue_unfinished()
    _render_document_list_body()


def render_document_list() -> None:
    enqueue_unfinished()
    docs = list_documents()
    busy = any((doc.get("processing_status") or "") in {"pending", "processing"} for doc in docs)
    if busy:
        render_document_list_live()
        return
    _render_document_list_body()


def _render_document_list_body() -> None:
    with st.container(border=True):
        st.markdown('<div class="hub-h2">Your documents</div>', unsafe_allow_html=True)
        docs = list_documents()
        if not docs:
            st.markdown(
                '<p class="hub-hint">No documents yet. Upload a file above to get started.</p>',
                unsafe_allow_html=True,
            )
            return

        if any((doc.get("processing_status") or "") in {"pending", "processing"} for doc in docs):
            st.caption("Reading and indexing… this list refreshes on its own.")
        else:
            st.markdown(
                '<p class="hub-expand-hint">Search or filter, then click a document to expand.</p>',
                unsafe_allow_html=True,
            )

        visible = _filter_documents(docs)
        if not visible:
            st.info("No documents match. Clear the search or change the filters.")
            return

        if len(visible) != len(docs):
            st.caption(f"Showing {len(visible)} of {len(docs)} documents.")

        for doc in visible:
            status = (doc.get("processing_status") or "pending").lower()
            label = STATUS_LABELS.get(status, status.title())
            chunk_count = int(doc.get("chunk_count") or 0)
            extra = doc["file_type"].upper()
            if status == "ready" and chunk_count:
                extra = f"{extra} · {chunk_count} chunks"
            title = f"{doc['name']}  ·  {label}"
            with st.expander(title, expanded=False):
                st.markdown(
                    f'<div class="hub-doc-meta">{html.escape(_doc_meta_line(doc))}</div>'
                    f'<div class="hub-doc-meta">{html.escape(extra)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("")
                actions = st.columns([1, 1, 2])
                with actions[0]:
                    if status == "failed":
                        if st.button("Try again", key=f"retry_{doc['id']}", type="secondary"):
                            from db import update_document_status

                            update_document_status(doc["id"], "pending", chunk_count=0, error_summary="")
                            enqueue_processing(doc["id"])
                            st.rerun()
                with actions[1]:
                    if st.button("Delete", key=f"del_{doc['id']}", type="secondary"):
                        err = delete_document(doc["id"])
                        if err:
                            st.session_state.flash = ("error", err)
                        else:
                            st.session_state.flash = ("success", "Document deleted.")
                        st.rerun()
                if status == "failed":
                    reason = doc.get("error_summary") or "We couldn't process this document. Please check the file and try again."
                    st.error(reason)
                if status == "ready":
                    st.markdown('<div class="hub-source-title">Chunks</div>', unsafe_allow_html=True)
                    _render_chunk_inspector(doc["id"])


def _filter_documents(docs: list[dict]) -> list[dict]:
    modules = ["All"] + sorted({(doc.get("module") or "").strip() for doc in docs if (doc.get("module") or "").strip()})
    types = ["All"] + sorted({(doc.get("file_type") or "").upper() for doc in docs if doc.get("file_type")})
    if st.session_state.get("doc_module_filter") not in modules:
        st.session_state.doc_module_filter = "All"
    if st.session_state.get("doc_type_filter") not in types:
        st.session_state.doc_type_filter = "All"

    search_col, status_col, module_col, type_col, clear_col = st.columns([2.2, 1.1, 1.1, 0.9, 0.7])
    with search_col:
        query = st.text_input(
            "Search",
            placeholder="Name, module, topic…",
            key="doc_search",
        )
    with status_col:
        status_pick = st.selectbox(
            "Status",
            ["All", "Ready", "Processing", "Pending", "Failed"],
            key="doc_status_filter",
        )
    with module_col:
        module_pick = st.selectbox("Module", modules, key="doc_module_filter")
    with type_col:
        type_pick = st.selectbox("Type", types, key="doc_type_filter")
    with clear_col:
        st.markdown("<div style='height: 0.35rem'></div>", unsafe_allow_html=True)
        if st.button("Clear", key="doc_filter_clear", type="secondary"):
            st.session_state.doc_search = ""
            st.session_state.doc_status_filter = "All"
            st.session_state.doc_module_filter = "All"
            st.session_state.doc_type_filter = "All"
            st.rerun()

    needle = (query or "").strip().lower()
    status_key = (status_pick or "All").lower()
    visible: list[dict] = []
    for doc in docs:
        status = (doc.get("processing_status") or "").lower()
        if status_key != "all" and status != status_key:
            continue
        if module_pick != "All" and (doc.get("module") or "").strip() != module_pick:
            continue
        if type_pick != "All" and (doc.get("file_type") or "").upper() != type_pick:
            continue
        if needle:
            haystack = " ".join(
                [
                    str(doc.get("name") or ""),
                    str(doc.get("module") or ""),
                    str(doc.get("topic") or ""),
                    str(doc.get("description") or ""),
                    str(doc.get("version") or ""),
                ]
            ).lower()
            if needle not in haystack:
                continue
        visible.append(doc)
    return visible


def _render_chunk_inspector(doc_id: str) -> None:
    try:
        from indexer import get_chunks_for_document

        chunks = get_chunks_for_document(doc_id)
    except Exception:
        st.caption("Chunks are not available to inspect yet.")
        return
    if not chunks:
        st.caption("No chunks stored for this document.")
        return
    for chunk in chunks[:40]:
        meta = chunk.get("metadata") or {}
        locator = meta.get("source_locator") or ""
        sheet = meta.get("sheet_name") or ""
        label = locator or (f"Sheet: {sheet}" if sheet else "Chunk")
        st.caption(label)
        preview = (chunk.get("content") or "")[:700]
        st.text(preview)
        st.markdown("")
    if len(chunks) > 40:
        st.caption(f"Showing first 40 of {len(chunks)} chunks.")


def _render_answer_exports(index: int, message: dict, model_bits: list[dict]) -> None:
    answer = (message.get("content") or "").strip()
    sources = [s for s in (message.get("sources") or []) if s.get("kind") != "model"]
    model_note = ""
    if model_bits:
        info = model_bits[0]
        used = info.get("model") or ""
        label = info.get("label") or ""
        if used:
            model_note = f"Answered by {label} using {used}."
    text_body = answer_text(answer, sources, model_note)
    st.caption("Save this answer")
    down_a, down_b, down_c = st.columns(3)
    with down_a:
        st.download_button(
            "Text",
            data=text_body.encode("utf-8"),
            file_name="learning-answer.txt",
            mime="text/plain",
            key=f"export_txt_{index}_{message.get('id') or index}",
        )
    with down_b:
        st.download_button(
            "Word",
            data=answer_docx_bytes(answer, sources, model_note),
            file_name="learning-answer.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"export_docx_{index}_{message.get('id') or index}",
        )
    with down_c:
        st.download_button(
            "PDF",
            data=answer_pdf_bytes(answer, sources, model_note),
            file_name="learning-answer.pdf",
            mime="application/pdf",
            key=f"export_pdf_{index}_{message.get('id') or index}",
        )


def render_ask_tab() -> None:
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = new_conversation_id()

    with st.container(border=True):
        head_l, head_r = st.columns([3.2, 1.1])
        with head_l:
            st.markdown('<div class="hub-h2">Ask</div>', unsafe_allow_html=True)
            st.caption(
                "Your files are searched on this PC first (free). Pick which model should write the answer. "
                "Excel and PDF contents are never sent to Tavily or the internet."
            )
        with head_r:
            if st.button("New conversation", type="secondary"):
                st.session_state.conversation_id = new_conversation_id()
                st.rerun()

        choices = list_provider_choices()
        choice_ids = [item["id"] for item in choices]
        if "answer_model" not in st.session_state or st.session_state.answer_model not in choice_ids:
            st.session_state.answer_model = default_provider()
        st.markdown(
            '<div class="hub-model-label">Which model should write the answer?</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Which model should write the answer?",
            options=choice_ids,
            format_func=lambda pid: next(
                (item["label"] for item in choices if item["id"] == pid), pid
            ),
            horizontal=True,
            key="answer_model",
            label_visibility="collapsed",
        )

        selected = next(
            (item for item in choices if item["id"] == st.session_state.answer_model),
            choices[0],
        )
        setup = resolve_answer_setup(st.session_state.answer_model)
        if setup.get("ok"):
            model_note = f" ({setup.get('model')})" if setup.get("model") else ""
            web_note = (
                " If nothing is in your documents, Tavily can look on the public web (question only)."
                if setup.get("web_ok")
                else " Web fallback is off until you add a Tavily key in Auth on the right."
            )
            st.caption(f"Using {selected['label']}{model_note}.{web_note}")
        else:
            st.warning(setup.get("error") or "Add this model's key in .env, or pick another model.")

        if count_ready_documents() == 0:
            st.info("Upload a document in the Documents tab and wait until it shows Ready, then ask here.")
            return

        messages = list_messages(st.session_state.conversation_id)
        if not messages:
            st.caption("Try one of these, or type your own question below.")
            for i, suggestion in enumerate(suggested_questions()):
                if st.button(suggestion, key=f"ask_suggest_{i}"):
                    st.session_state.pending_ask = suggestion
                    st.rerun()

        for index, message in enumerate(messages):
            role = message.get("role") or "assistant"
            with st.chat_message("user" if role == "user" else "assistant"):
                st.markdown(message.get("content") or "")
                sources = message.get("sources") or []
                model_bits = [s for s in sources if s.get("kind") == "model"]
                doc_sources = [s for s in sources if (s.get("kind") or "document") == "document"]
                web_sources = [s for s in sources if s.get("kind") == "web"]
                if role == "assistant" and model_bits:
                    info = model_bits[0]
                    used = info.get("model") or ""
                    label = info.get("label") or "Gemini"
                    requested = info.get("requested") or ""
                    if used and requested and used != requested:
                        st.caption(
                            f"Answered by {label} using {used} ({requested} was busy or unavailable)."
                        )
                    elif used:
                        st.caption(f"Answered by {label} using {used}.")
                if role == "assistant" and sources:
                    if doc_sources:
                        st.markdown('<div class="hub-source-title">Sources (your documents)</div>', unsafe_allow_html=True)
                        for source in doc_sources:
                            title = source.get("label") or "Source"
                            excerpt = (source.get("excerpt") or "").strip()
                            with st.expander(title, expanded=False):
                                if excerpt:
                                    st.text(excerpt)
                                else:
                                    st.caption("Passage was not stored for this older answer. Search Documents for this file.")
                    if web_sources:
                        st.markdown(
                            '<div class="hub-source-title">From the web (not from your documents)</div>',
                            unsafe_allow_html=True,
                        )
                        for source in web_sources:
                            label = html.escape(source.get("label") or "")
                            url = html.escape(source.get("url") or "")
                            extra = f" — {url}" if url else ""
                            st.markdown(f'<div class="hub-source-web">{label}{extra}</div>', unsafe_allow_html=True)
                if role == "assistant" and (message.get("content") or "").strip():
                    _render_answer_exports(index, message, model_bits)

    pending = st.session_state.pop("pending_ask", None)
    question = st.chat_input("Ask about your documents…") or pending
    if not question:
        return

    history = list_messages(st.session_state.conversation_id)
    add_message(st.session_state.conversation_id, "user", question)
    with st.spinner("Looking through your documents…"):
        result = answer_question(question, history, provider=st.session_state.get("answer_model"))
    if result.get("ok"):
        sources = list(result.get("sources") or [])
        used = (result.get("model_used") or "").strip()
        if used:
            sources = [
                {
                    "kind": "model",
                    "label": result.get("provider") or "Gemini",
                    "model": used,
                    "requested": result.get("model_requested") or "",
                }
            ] + sources
        add_message(
            st.session_state.conversation_id,
            "assistant",
            result["answer"],
            sources,
        )
    else:
        add_message(
            st.session_state.conversation_id,
            "assistant",
            result.get("error") or "I couldn't get an answer just now. Please try again.",
            result.get("sources") or [],
        )
    st.rerun()


def render_auth_panel() -> None:
    if "answer_model" not in st.session_state:
        st.session_state.answer_model = default_provider()
    if "auth_editing" not in st.session_state:
        st.session_state.auth_editing = False
    if "auth_editing_tavily" not in st.session_state:
        st.session_state.auth_editing_tavily = False
    if st.session_state.pop("_reset_custom_form", False):
        st.session_state.custom_name = ""
        st.session_state.custom_model_id = ""
        st.session_state.pop("custom_api_key", None)
        st.session_state.pop("custom_base_url", None)

    provider = st.session_state.answer_model
    custom = is_custom_id(provider)
    custom_row = get_custom_model(provider) if custom else None
    if custom and not custom_row:
        provider = default_provider()
        custom = False
    if st.session_state.get("_auth_for_provider") != provider:
        st.session_state._auth_for_provider = provider
        st.session_state.auth_editing = False
        st.session_state.pop("confirm_delete_model", None)

    if custom:
        short = custom_row["name"]
        status = {
            "present": bool(custom_row.get("ready")),
            "message": (
                f"{short} saved on this PC · Ready."
                if custom_row.get("ready")
                else f"No key for {short} — paste it below."
            ),
        }
    else:
        if provider not in PROVIDER_SHORT:
            provider = default_provider()
        short = PROVIDER_SHORT[provider]
        status = auth_status(provider)

    with st.container(border=True):
        st.markdown('<div class="hub-h2">Auth</div>', unsafe_allow_html=True)
        st.caption(f"Key for {short} — paste and save like the Auth token in Test Management Hub.")
        help_info = None if custom else KEY_HELP.get(provider)
        if help_info:
            st.markdown(
                f"[{html.escape(help_info['label'])}]({help_info['url']}) — {html.escape(help_info['steps'])}"
            )
        kind = "ok" if status["present"] else "warn"
        st.markdown(
            f'<p class="hub-auth-line {kind}">{html.escape(status["message"])}</p>',
            unsafe_allow_html=True,
        )

        show_edit = st.session_state.auth_editing or not status["present"]
        if status["present"] and not st.session_state.auth_editing:
            if st.button("Change key", key="auth_change", type="secondary"):
                st.session_state.auth_editing = True
                st.rerun()

        if show_edit and custom:
            new_key = st.text_input(
                f"{short} API key",
                type="password",
                placeholder="Paste API key",
                key="auth_input_custom_key",
            )
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save key", key="auth_save"):
                    try:
                        update_custom_model(provider, api_key=new_key)
                        st.session_state.pop("auth_input_custom_key", None)
                        st.session_state.auth_editing = False
                        st.session_state.auth_flash = "Key saved on this PC. Applied immediately — no restart needed."
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))
            with cancel_col:
                if status["present"] and st.button("Cancel", key="auth_cancel", type="secondary"):
                    st.session_state.auth_editing = False
                    st.session_state.pop("auth_input_custom_key", None)
                    st.rerun()
            st.markdown(
                '<p class="hub-auth-hint">Saved on this PC · applied immediately</p>',
                unsafe_allow_html=True,
            )
        elif show_edit:
            fields = PROVIDER_KEY_FIELDS[provider]
            values: dict[str, str] = {}
            for field in fields:
                kwargs = {
                    "label": field["label"],
                    "placeholder": field["placeholder"],
                    "key": f"auth_input_{field['name']}",
                }
                if field["secret"]:
                    kwargs["type"] = "password"
                values[field["name"]] = st.text_input(**kwargs)
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save key", key="auth_save"):
                    try:
                        for field in fields:
                            save_env_value(field["name"], values.get(field["name"]) or "")
                            st.session_state.pop(f"auth_input_{field['name']}", None)
                        st.session_state.auth_editing = False
                        st.session_state.auth_flash = (
                            "Key saved to .env and ready. Applied immediately — no restart needed."
                        )
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))
            with cancel_col:
                if status["present"] and st.button("Cancel", key="auth_cancel", type="secondary"):
                    st.session_state.auth_editing = False
                    for field in PROVIDER_KEY_FIELDS[provider]:
                        st.session_state.pop(f"auth_input_{field['name']}", None)
                    st.rerun()
            st.markdown(
                '<p class="hub-auth-hint">Saved to <code>.env</code> · applied immediately</p>',
                unsafe_allow_html=True,
            )

        if custom:
            if st.session_state.get("confirm_delete_model") == provider:
                st.warning("This removes the saved model from Ask. You can add it again later.")
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("Yes, delete", key="auth_delete_yes"):
                        delete_custom_model(provider)
                        st.session_state.confirm_delete_model = None
                        st.session_state.auth_flash = "Saved model deleted."
                        st.session_state._pending_answer_model = default_provider()
                        st.rerun()
                with no_col:
                    if st.button("Cancel", key="auth_delete_no", type="secondary"):
                        st.session_state.confirm_delete_model = None
                        st.rerun()
            elif st.button("Delete this saved model", key="auth_delete", type="secondary"):
                st.session_state.confirm_delete_model = provider
                st.rerun()

        if st.session_state.get("auth_flash"):
            st.success(st.session_state.auth_flash)
            st.session_state.auth_flash = ""

        st.divider()
        with st.expander("Add another model"):
            st.caption("Saved models stay on this PC and show up on the Ask tab next time.")
            kind_labels = {key: value["label"] for key, value in CUSTOM_API_KINDS.items()}
            kind_pick = st.selectbox(
                "Kind of API",
                options=list(kind_labels.keys()),
                format_func=lambda key: kind_labels[key],
                key="custom_kind",
            )
            kind_info = CUSTOM_API_KINDS.get(kind_pick) or CUSTOM_API_KINDS["other"]
            if kind_info.get("help_url"):
                st.markdown(
                    f"[{html.escape(kind_info['help_label'])}]({kind_info['help_url']})"
                )
            custom_name = st.text_input("Name on the Ask tab", placeholder="e.g. Groq or Gemini", key="custom_name")
            custom_model = st.text_input(
                "Model name from the provider",
                placeholder=f"e.g. {kind_info.get('example_model') or 'model-id'}",
                key="custom_model_id",
            )
            custom_key = st.text_input("API key", type="password", placeholder="Paste API key", key="custom_api_key")
            custom_url = ""
            if kind_pick == "other":
                custom_url = st.text_input(
                    "API address",
                    placeholder="https://api.example.com/v1",
                    key="custom_base_url",
                )
            if st.button("Save this model", key="custom_save"):
                try:
                    saved = save_custom_model(
                        name=custom_name,
                        model=custom_model,
                        api_key=custom_key,
                        kind=kind_pick,
                        base_url=custom_url,
                    )
                    st.session_state.auth_flash = f"{saved['name']} saved. It will be here next time you open the app."
                    st.session_state._reset_custom_form = True
                    st.session_state._pending_answer_model = saved["id"]
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))

        st.divider()
        t_status = tavily_status()
        t_kind = "ok" if t_status["present"] else "warn"
        st.markdown('<div class="hub-source-title">Web search (optional)</div>', unsafe_allow_html=True)
        tavily_help = KEY_HELP["tavily"]
        st.markdown(
            f"[{html.escape(tavily_help['label'])}]({tavily_help['url']}) — {html.escape(tavily_help['steps'])}"
        )
        st.markdown(
            f'<p class="hub-auth-line {t_kind}">{html.escape(t_status["message"])}</p>',
            unsafe_allow_html=True,
        )
        t_edit = st.session_state.auth_editing_tavily or not t_status["present"]
        if t_status["present"] and not st.session_state.auth_editing_tavily:
            if st.button("Change Tavily key", key="tavily_change", type="secondary"):
                st.session_state.auth_editing_tavily = True
                st.rerun()
        if t_edit:
            tavily_val = st.text_input(
                TAVILY_FIELD["label"],
                type="password",
                placeholder=TAVILY_FIELD["placeholder"],
                key="auth_input_tavily",
            )
            t_save, t_cancel = st.columns(2)
            with t_save:
                if st.button("Save Tavily key", key="tavily_save"):
                    try:
                        save_env_value(TAVILY_FIELD["name"], tavily_val)
                        st.session_state.pop("auth_input_tavily", None)
                        st.session_state.auth_editing_tavily = False
                        st.session_state.tavily_flash = "Tavily key saved to .env and ready."
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))
            with t_cancel:
                if t_status["present"] and st.button("Cancel", key="tavily_cancel", type="secondary"):
                    st.session_state.auth_editing_tavily = False
                    st.session_state.pop("auth_input_tavily", None)
                    st.rerun()
            st.markdown(
                '<p class="hub-auth-hint">Saved to <code>.env</code> · applied immediately</p>',
                unsafe_allow_html=True,
            )
        if st.session_state.get("tavily_flash"):
            st.success(st.session_state.tavily_flash)
            st.session_state.tavily_flash = ""


init_db()
inject_chrome()
preload_embedding_model()
if not _using_app_python():
    st.error(
        "This window is an old or extra copy of the app. Close every Insurance Learning Assistant "
        "window and the terminal, then start again by double-clicking run.bat. "
        "Always open http://localhost:8501 — do not use Cursor Live Preview."
    )

if "module" not in st.session_state:
    st.session_state.module = "Documents"
pending_model = st.session_state.pop("_pending_answer_model", None)
if pending_model:
    st.session_state.answer_model = pending_model

st.radio(
    "Modules",
    ["Documents", "Ask"],
    horizontal=True,
    key="module",
    label_visibility="collapsed",
)

main_col, side_col = st.columns([1.2, 0.8], gap="medium")

with main_col:
    if st.session_state.module == "Documents":
        render_documents_tab()
    else:
        render_ask_tab()

with side_col:
    render_auth_panel()
    st.markdown(
        """
<div class="hub-panel">
  <div class="hub-h2">How this works</div>
  <ol class="hub-side-list">
    <li>Add your D365 and insurance documents</li>
    <li>Search or filter your documents, then click one to expand</li>
    <li>Paste the API key in Auth, or add another model and Save this model</li>
    <li>On Ask, pick a starter question or type your own, then click a source to read the passage</li>
  </ol>
  <p class="hub-hint">If something is not in your files, the assistant will say so, then can still explain general D365 or insurance ideas, clearly labelled.</p>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown(
    '<p class="hub-footer">Local learning tool · answers from your documents show their source · general D365/insurance teaching is labelled separately</p>',
    unsafe_allow_html=True,
)
