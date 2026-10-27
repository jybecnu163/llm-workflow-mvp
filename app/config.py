from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3-coder:30b"
# DEFAULT_MODEL = "llama3.1:8b"
REQUEST_TIMEOUT = 120.0

# config.py
EXCEL_WORKDIR = Path(__file__).parent.parent / "data" / "excel"
EXCEL_WORKDIR.mkdir(parents=True, exist_ok=True)
EXCEL_PREVIEW_ROWS = 20

# ---------- RAG 配置 ----------
EMBED_MODEL = "nomic-embed-text"
EMBED_URL = "http://127.0.0.1:11434/api/embed"

RAG_DOCS_DIR = Path(__file__).parent.parent / "data" / "rag_docs"
RAG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma_rag"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

RAG_COLLECTION = "documents"
RAG_CHUNK_SIZE = 500
RAG_CHUNK_OVERLAP = 80
RAG_TOP_K = 5
RAG_EMBED_BATCH = 32