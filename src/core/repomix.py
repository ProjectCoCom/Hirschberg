"""
Repomix file tree compiler.

Responsibilities:
- Packages files in the workspace into a structured format for LLM processing.

Coupling:
- Used by context compilation tools.
"""


from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

REPOS_DIR = Path("data/repos")
REPOMIX_DIR = Path("data/repomix")

_deps_ready = False


def _run_sync(cmd: str, cwd: str | None = None, timeout: int = 300) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, timeout=timeout,
            capture_output=True, text=True, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s: {cmd[:80]}"
    rc = result.returncode
    if rc != 0:
        combined = (result.stderr or result.stdout).strip()
        print(f"[repomix] CMD FAILED: {cmd}\n  rc={rc}\n  stdout={result.stdout[:200]}\n  stderr={result.stderr[:200]}")
        return rc, result.stdout, combined or f"Command exited with code {rc}"
    return 0, result.stdout, result.stderr


async def _run(cmd: str, cwd: str | None = None, timeout: int = 300) -> tuple[int, str, str]:
    return await asyncio.to_thread(_run_sync, cmd, cwd, timeout)


async def ensure_dependencies() -> None:
    global _deps_ready
    if _deps_ready:
        return

    if not shutil.which("git"):
        raise RuntimeError("git is not installed. Please install git and add it to PATH.")

    if not shutil.which("npx"):
        raise RuntimeError("Node.js/npx is not installed. Please install Node.js and add it to PATH.")

    _deps_ready = True


async def clone_or_pull(owner: str, repo: str, token: str) -> Path:
    repo_path = REPOS_DIR / owner / repo
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    if (repo_path / ".git").exists():
        rc, _, stderr = await _run("git fetch origin", cwd=str(repo_path))
        if rc != 0:
            raise RuntimeError(f"git fetch failed (rc={rc}): {stderr[:200]}")
        await _run("git reset --hard origin/HEAD", cwd=str(repo_path))
    else:
        url = f"https://{token}@github.com/{owner}/{repo}.git"
        # -c credential.helper= disables Git Credential Manager popup on Windows
        rc, _, stderr = await _run(f'git -c credential.helper= clone --depth 1 "{url}" "{repo_path}"')
        if rc != 0:
            safe_err = stderr.replace(token, "***")[:200]
            raise RuntimeError(f"git clone failed (rc={rc}): {safe_err}")

    return repo_path


async def run_repomix(repo_path: Path, owner: str, repo: str) -> str:
    REPOMIX_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPOMIX_DIR / f"{owner}__{repo}.xml"
    abs_output = output_path.resolve()

    rc, _, stderr = await _run(
        f'npx --yes repomix --output "{abs_output}"',
        cwd=str(repo_path),
    )

    if rc != 0:
        raise RuntimeError(f"repomix failed (rc={rc}): {stderr[:300]}")

    if not abs_output.exists():
        raise RuntimeError(f"repomix produced no output file at {abs_output}")

    return abs_output.read_text(encoding="utf-8", errors="replace")


async def analyze_repo(owner: str, repo: str, token: str) -> str:
    await ensure_dependencies()
    repo_path = await clone_or_pull(owner, repo, token)
    xml = await run_repomix(repo_path, owner, repo)
    return xml


def get_cached_xml(owner: str, repo: str) -> str | None:
    output_path = (REPOMIX_DIR / f"{owner}__{repo}.xml").resolve()
    if output_path.exists():
        return output_path.read_text(encoding="utf-8", errors="replace")
    return None


def get_repo_last_commit(owner: str, repo: str) -> str | None:
    repo_path = REPOS_DIR / owner / repo
    head_file = repo_path / ".git" / "refs" / "heads" / "master"
    if not head_file.exists():
        head_file = repo_path / ".git" / "refs" / "heads" / "main"
    if head_file.exists():
        return head_file.read_text().strip()[:8]
    return None
