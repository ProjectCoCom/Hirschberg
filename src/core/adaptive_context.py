"""
Summary: RAG and adaptive workspace context builder.

What it does: Indexes files, trims overly long file contexts, and compiles relevant context snippets for agents.

How it fits in: Depends on 'src/core/rag_store.py'.
"""



from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from core.rag_store import query_context

DB_PATH = Path("data/jat.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunk_scores (
    chunk_id TEXT PRIMARY KEY,
    collection TEXT,
    score REAL DEFAULT 1.0,
    hit_count INTEGER DEFAULT 0,
    last_hit TEXT
)
"""


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


async def record_chunk_usage(collection: str, chunk_ids: list[str]) -> None:
    def _record():
        conn = _get_conn()
        now = datetime.now(UTC).isoformat()
        for cid in chunk_ids:
            existing = conn.execute(
                "SELECT score, hit_count FROM chunk_scores WHERE chunk_id = ?", (cid,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE chunk_scores SET score = score + 0.1, hit_count = hit_count + 1, last_hit = ? WHERE chunk_id = ?",
                    (now, cid),
                )
            else:
                conn.execute(
                    "INSERT INTO chunk_scores (chunk_id, collection, score, hit_count, last_hit) VALUES (?, ?, 1.1, 1, ?)",
                    (cid, collection, now),
                )
        conn.commit()
        conn.close()

    await asyncio.to_thread(_record)


async def get_boosted_results(owner: str, repo: str, query: str, n_results: int = 5) -> list[str]:
    rag_chunks = await query_context(owner, repo, query, n_results=n_results * 2)
    if not rag_chunks:
        return []

    collection = f"{owner}__{repo}"

    def _score_chunks():
        conn = _get_conn()
        scored = []
        for i, chunk in enumerate(rag_chunks):
            chunk_id = f"{collection}_{hash(chunk[:100]) & 0xFFFFFFFF}"
            row = conn.execute(
                "SELECT score FROM chunk_scores WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            boost = row[0] if row else 1.0
            relevance = 1.0 - (i / len(rag_chunks))
            combined = relevance * 0.7 + (boost / max(boost, 5.0)) * 0.3
            scored.append((combined, chunk))
        conn.close()
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:n_results]]

    return await asyncio.to_thread(_score_chunks)


async def detect_referenced_chunks(response: str, injected_chunks: list[str]) -> list[str]:
    if not response or not injected_chunks:
        return []

    def _detect():
        referenced = []
        response_lower = response.lower()
        for chunk in injected_chunks:
            words = chunk.split()
            if len(words) < 10:
                continue
            threshold = int(len(words) * 0.3)
            matches = sum(1 for w in words if w.lower() in response_lower)
            if matches >= threshold:
                referenced.append(chunk)
        return referenced

    return await asyncio.to_thread(_detect)


def decay_scores(collection: str, factor: float = 0.95) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE chunk_scores SET score = score * ? WHERE collection = ?",
        (factor, collection),
    )
    conn.commit()
    conn.close()
