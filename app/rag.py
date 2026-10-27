import os
import re
from pathlib import Path

import chromadb
from pypdf import PdfReader

from app.config import (
    CHROMA_DIR,
    RAG_COLLECTION,
    RAG_DOCS_DIR,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_TOP_K,
)
from app.ollama_client import chat, embed

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _get_collection():
    return _get_client().get_or_create_collection(
        name=RAG_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# ---------- 文件与切分 ----------

def _safe_doc_path(name: str) -> Path:
    base = RAG_DOCS_DIR.resolve()
    p = (base / name).resolve() if not os.path.isabs(name) else Path(name).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError(f"路径必须位于 {base} 内")
    if p.suffix.lower() not in (".pdf", ".txt", ".md", ".markdown"):
        raise ValueError("只支持 .pdf / .txt / .md / .markdown")
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p


def _load_text(path: Path) -> tuple[str, list[tuple[int, str]]]:
    """返回 (全文, [(页码, 文本)])"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            t = (page.extract_text() or "").strip()
            pages.append((i, t))
        full = "\n\n".join(t for _, t in pages if t)
        return full, pages
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text, [(1, text)]


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """按 size 切分，尽量在标点处断开，带 overlap。"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    break_chars = "。！？；.!?;\n"
    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + size, n)
        if end < n:
            best = -1
            for i in range(end - 1, max(start + size // 2, start), -1):
                if text[i] in break_chars:
                    best = i + 1
                    break
            if best > start:
                end = best
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


# ---------- 入库 ----------

async def ingest_document(path_name: str) -> dict:
    path = _safe_doc_path(path_name)
    full_text, pages = _load_text(path)
    if not full_text.strip():
        return {
            "file": path.name,
            "pages": len(pages),
            "chunks_added": 0,
            "error": "文档没有可提取的文本（可能是扫描版 PDF）",
        }

    collection = _get_collection()
    filename = path.name
    total_chunks = 0

    from app.config import RAG_EMBED_BATCH  # 见第 4 步

    for page_num, page_text in pages:
        if not page_text.strip():
            continue
        chunks = _split_text(page_text, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP)
        if not chunks:
            continue

        # 分批批量 embedding
        page_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), RAG_EMBED_BATCH):
            batch = chunks[i:i + RAG_EMBED_BATCH]
            batch_embs = await embed(batch)  # 一次请求处理整批
            page_embeddings.extend(batch_embs)

        if len(page_embeddings) != len(chunks):
            raise ValueError(
                f"embedding 数量不匹配: chunks={len(chunks)}, embeddings={len(page_embeddings)}"
            )

        ids = [f"{filename}_p{page_num}_c{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": filename, "page": page_num, "chunk_index": i}
            for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=page_embeddings,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)

    return {
        "file": filename,
        "pages": len(pages),
        "chunks_added": total_chunks,
        "collection_size": collection.count(),
    }


# ---------- 检索 ----------

async def search(
        question: str,
        top_k: int = RAG_TOP_K,
        source_filter: str | None = None,
) -> list[dict]:
    question = (question or "").strip()
    if not question:
        return []

    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    q_emb = await embed(question)
    where = {"source": source_filter} if source_filter else None

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(top_k, total),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]

    chunks = []
    for doc, meta, dist in zip(docs, metas, dists):
        chunks.append({
            "text": doc,
            "source": meta.get("source", ""),
            "page": meta.get("page", 0),
            "chunk_index": meta.get("chunk_index", 0),
            "score": round(1 - float(dist), 3),
        })
    return chunks


# ---------- 问答 ----------

RAG_SYSTEM = "你是文档问答助手。只根据用户提供的文档片段回答，严禁编造。"


async def answer_question(question: str, top_k: int = RAG_TOP_K) -> dict:
    chunks = await search(question, top_k=top_k)

    if not chunks:
        return {
            "answer": "知识库为空或没有检索到相关内容。请先上传文档，或换个问法。",
            "sources": [],
            "chunks_used": 0,
        }

    context_parts = []
    for i, c in enumerate(chunks, 1):
        context_parts.append(
            f"[片段 {i}] 来源: {c['source']} 第 {c['page']} 页\n{c['text']}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""你是文档问答助手。请**只根据**下面提供的文档片段回答问题。

【文档片段】
{context}

【用户问题】
{question}

【规则】
1. 只使用文档片段中的信息，严禁编造。
2. 如果片段中没有相关信息，直接回答"根据提供的文档，无法回答该问题"。
3. 回答末尾附上 [来源: 文件名 第X页]。
4. 数字、日期、金额必须原样引用，不要改动。

回答："""

    answer = await chat(prompt, system=RAG_SYSTEM, temperature=0.1)

    seen = set()
    sources = []
    for c in chunks:
        key = (c["source"], c["page"])
        if key not in seen:
            seen.add(key)
            sources.append({
                "source": c["source"],
                "page": c["page"],
                "score": c["score"],
            })

    return {
        "answer": answer.strip(),
        "sources": sources,
        "chunks_used": len(chunks),
    }


CHAPTER_FILE_RE = re.compile(r"^第(\d+)回_(.+)\.txt$")


async def ingest_chapter_files(dir_name: str = "sanguo") -> dict:
    """遍历 data/rag_docs/{dir_name}/ 下所有 第XXX回_标题.txt 文件并入库。"""
    from app.config import RAG_EMBED_BATCH

    base = RAG_DOCS_DIR.resolve()
    dir_path = (base / dir_name).resolve()
    print(dir_path)
    if not str(dir_path).startswith(str(base)):
        raise ValueError(f"目录必须位于 {base} 内")
    if not dir_path.exists() or not dir_path.is_dir():
        raise FileNotFoundError(str(dir_path))

    files = sorted(dir_path.glob("*.txt"))
    if not files:
        return {"dir": dir_name, "files": 0, "chunks_added": 0,
                "error": "目录下没有 txt 文件"}

    collection = _get_collection()
    total_chunks = 0
    processed = 0
    skipped = []

    for f in files:
        m = CHAPTER_FILE_RE.match(f.name)
        if not m:
            skipped.append(f.name)
            print(f"[skip] 文件名不符合格式: {f.name}")
            continue

        chapter_num = int(m.group(1))
        chapter_title = m.group(2)

        text = f.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        chunks = _split_text(text, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP)
        if not chunks:
            continue

        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), RAG_EMBED_BATCH):
            batch = chunks[i:i + RAG_EMBED_BATCH]
            embeddings.extend(await embed(batch))

        if len(embeddings) != len(chunks):
            raise ValueError(
                f"第{chapter_num}回 embedding 数量不匹配: "
                f"chunks={len(chunks)}, embeddings={len(embeddings)}"
            )

        ids = [f"{dir_name}_ch{chapter_num:03d}_c{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": f.name,
                "chapter": chapter_num,
                "chapter_title": chapter_title,
                "page": chapter_num,
                "chunk_index": i,
                "type": "chunk",
            }
            for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)
        processed += 1
        print(f"[ingest] 第{chapter_num:03d}回 {chapter_title}: {len(chunks)} chunks")

    return {
        "dir": dir_name,
        "files": processed,
        "skipped": skipped,
        "chunks_added": total_chunks,
        "collection_size": collection.count(),
    }
