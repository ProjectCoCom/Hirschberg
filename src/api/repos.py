"""
API router for workspace repository metadata.

Responsibilities:
- Manages target repo details and configurations for the agent runtime.

Coupling:
- Interacts with database.
"""


from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import load_settings
from core.rag_store import get_chunk_count, ingest_repomix_xml
from core.repomix import analyze_repo, get_cached_xml

router = APIRouter()
settings = load_settings()


@router.post("/api/repos/{owner}/{repo}/analyze")
async def analyze(owner: str, repo: str):
    token = settings.github_token
    if not token:
        raise HTTPException(400, "No GitHub token configured")

    try:
        xml = await analyze_repo(owner, repo, token)
    except RuntimeError as e:
        import traceback
        traceback.print_exc()
        msg = str(e) or "Unknown runtime error (empty message)"
        print(f"[analyze] RuntimeError: {msg}")
        raise HTTPException(500, f"Analysis failed: {msg}") from e
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = f"{type(e).__name__}: {e}"
        print(f"[analyze] Exception: {msg}")
        raise HTTPException(500, f"Unexpected error: {msg}") from e

    return {"xml": xml, "cached": False, "chars": len(xml)}


@router.get("/api/repos/{owner}/{repo}/context")
async def get_context(owner: str, repo: str):
    cached = get_cached_xml(owner, repo)
    if not cached:
        raise HTTPException(404, "No cached analysis. Run analyze first.")
    return {"xml": cached, "chars": len(cached)}


@router.post("/api/repos/{owner}/{repo}/init-jdocs")
async def init_jdocs_endpoint(owner: str, repo: str, branch: str = "main"):
    token = settings.github_token
    if not token:
        raise HTTPException(400, "No GitHub token configured")

    from core.jdocs import init_jdocs
    results = await init_jdocs(owner, repo, branch, token)
    return {"results": results}


@router.post("/api/repos/{owner}/{repo}/ingest")
async def ingest_repo(owner: str, repo: str):
    xml = get_cached_xml(owner, repo)
    if not xml:
        raise HTTPException(404, "No cached analysis found. Run analyze first.")
    count = await ingest_repomix_xml(owner, repo, xml)
    return {"chunks": count, "status": "ingested"}


@router.get("/api/repos/{owner}/{repo}/rag-status")
async def rag_status(owner: str, repo: str):
    count = get_chunk_count(owner, repo)
    return {"ingested": count > 0, "chunks": count}
