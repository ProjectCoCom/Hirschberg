"""
Summary: Simple text vector store for codebase RAG.

What it does: Embeds text fragments, retrieves nearest matches, and supports localized codebase searches.

How it fits in: Backing store for 'src/core/adaptive_context.py'.
"""



from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

try:
    import chromadb
except ImportError:
    chromadb = None
    print("[RAG] chromadb not installed. RAG features disabled. Run: pip install chromadb")

DATA_DIR = Path("data/chromadb")


def _get_client():
    if chromadb is None:
        return None
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(DATA_DIR))


def _collection_name(owner: str, repo: str) -> str:
    name = f"{owner}__{repo}"
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if len(name) < 3:
        name = name + "___"
    return name[:63]


def _get_collection(owner: str, repo: str):
    client = _get_client()
    if client is None:
        return None
    return client.get_or_create_collection(name=_collection_name(owner, repo))


def _chunk_text(content: str, max_size: int = 1000) -> list[str]:
    chunks = []
    while content:
        if len(content) <= max_size:
            chunks.append(content)
            break
        cut = content.rfind("\n", 0, max_size)
        if cut <= 0:
            cut = max_size
        chunks.append(content[:cut])
        content = content[cut:].lstrip("\n")
    return [c for c in chunks if c.strip()]


def _chunk_repomix_xml(xml_content: str) -> list[str]:
    file_pattern = re.compile(r"(<file\s+path=[^>]*>.*?</file>)", re.DOTALL)
    files = file_pattern.findall(xml_content)
    if not files:
        return _chunk_text(xml_content)
    chunks = []
    for file_block in files:
        if len(file_block) <= 1500:
            chunks.append(file_block)
        else:
            chunks.extend(_chunk_text(file_block, 1000))
    return [c for c in chunks if c.strip()]


async def store_context(owner: str, repo: str, content: str, metadata: dict = None) -> str:
    if chromadb is None:
        return ""
    collection = _get_collection(owner, repo)
    if collection is None:
        return ""
    chunks = _chunk_text(content)
    doc_id = str(uuid.uuid4())
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "chunk_index": i, **(metadata or {})} for i in range(len(chunks))]

    def _store():
        collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    await asyncio.to_thread(_store)
    return doc_id


async def query_context(owner: str, repo: str, query: str, n_results: int = 5) -> list[str]:
    if chromadb is None:
        return []
    collection = _get_collection(owner, repo)
    if collection is None:
        return []

    def _query():
        count = collection.count()
        if count == 0:
            return []
        n = min(n_results, count)
        results = collection.query(query_texts=[query], n_results=n)
        return results.get("documents", [[]])[0]

    return await asyncio.to_thread(_query)


async def store_code_summary(owner: str, repo: str, file_path: str, summary: str) -> None:
    if chromadb is None:
        return
    await store_context(owner, repo, summary, metadata={"type": "code_summary", "file_path": file_path})


def get_relevant_context(owner: str, repo: str, query: str, n_results: int = 5) -> list[str]:
    if chromadb is None:
        return []
    collection = _get_collection(owner, repo)
    if collection is None:
        return []
    count = collection.count()
    if count == 0:
        return []
    n = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=n)
    return results.get("documents", [[]])[0]


async def ingest_repomix_xml(owner: str, repo: str, xml_content: str) -> int:
    if chromadb is None:
        return 0
    collection = _get_collection(owner, repo)
    if collection is None:
        return 0

    chunks = _chunk_repomix_xml(xml_content)
    if not chunks:
        return 0

    batch_id = str(uuid.uuid4())
    ids = [f"{batch_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"type": "repomix", "batch_id": batch_id, "chunk_index": i} for i in range(len(chunks))]

    def _ingest():
        batch_size = 100
        for start in range(0, len(chunks), batch_size):
            end = start + batch_size
            collection.add(
                documents=chunks[start:end],
                ids=ids[start:end],
                metadatas=metadatas[start:end],
            )

    await asyncio.to_thread(_ingest)
    return len(chunks)


def get_chunk_count(owner: str, repo: str) -> int:
    if chromadb is None:
        return 0
    collection = _get_collection(owner, repo)
    if collection is None:
        return 0
    return collection.count()


async def store_conversation_exchange(
    owner: str, repo: str, user_msg: str, assistant_msg: str, conversation_id: str = ""
) -> None:
    if chromadb is None:
        return
    collection = _get_collection(owner, repo)
    if collection is None:
        return

    exchange_text = f"USER: {user_msg}\nASSISTANT: {assistant_msg}"
    chunks = _chunk_text(exchange_text, max_size=1200)
    if not chunks:
        return

    exchange_id = str(uuid.uuid4())
    ids = [f"conv_{exchange_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"type": "conversation", "conversation_id": conversation_id, "chunk_index": i}
        for i in range(len(chunks))
    ]

    def _store():
        collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    await asyncio.to_thread(_store)


async def query_conversation_context(
    owner: str, repo: str, query: str, n_results: int = 3
) -> list[str]:
    if chromadb is None:
        return []
    collection = _get_collection(owner, repo)
    if collection is None:
        return []

    def _query():
        count = collection.count()
        if count == 0:
            return []
        n = min(n_results, count)
        results = collection.query(
            query_texts=[query],
            n_results=n,
            where={"type": "conversation"},
        )
        return results.get("documents", [[]])[0]

    try:
        return await asyncio.to_thread(_query)
    except Exception:
        return []
