#!/usr/bin/env python3
"""
Summary: Python logic module 'Generate Map'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Generate Map'.

How it fits in: Imported and utilized by surrounding backend structures.
"""


import os
import json
import subprocess
import re

# Standardized exclusions (same as generate_headers.py)
EXCLUSIONS = [
    "node_modules", ".venv", "site-packages", ".git", ".pytest_cache", "__pycache__", ".jules", "docs/map.json", "docs/depreciated"
]
LOCK_FILES = ["uv.lock", "package-lock.json", "pnpm-lock.yaml"]

def get_git_info():
    """Derives owner, repo, and default branch dynamically from git configuration."""
    owner = "ProjectCoCom"
    repo = "Hirschberg"
    branch = "development" # safe fallback

    try:
        # Get remote URL
        url_res = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        url = url_res.stdout.strip()
        match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
        if match:
            owner = match.group(1)
            repo = match.group(2)
            if repo.endswith(".git"):
                repo = repo[:-4]
    except Exception as e:
        print(f"Warning: failed to fetch git remote origin: {e}. Defaulting to '{owner}/{repo}'.")

    try:
        # Get dynamic default branch ref
        ref_res = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True
        )
        ref = ref_res.stdout.strip()
        if ref.startswith("refs/remotes/origin/"):
            branch = ref[len("refs/remotes/origin/"):]
        else:
            # Fallback auto-set head if head not found
            subprocess.run(["git", "remote", "set-head", "origin", "--auto"], capture_output=True)
            ref_res2 = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True, text=True
            )
            ref2 = ref_res2.stdout.strip()
            if ref2.startswith("refs/remotes/origin/"):
                branch = ref2[len("refs/remotes/origin/"):]
    except Exception as e:
        print(f"Warning: failed to fetch default branch dynamically: {e}. Defaulting to '{branch}'.")

    return owner, repo, branch

def extract_description(filepath: str) -> str:
    """Parses a file's header comment block to extract the one-line summary."""
    ext = os.path.splitext(filepath)[1]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ""

    if ext == ".json":
        try:
            data = json.loads(content)
            desc = data.get("_description", [])
            # Handle array representation
            if isinstance(desc, list):
                for item in desc:
                    if item.startswith("Summary:"):
                        return item[len("Summary:"):].strip()
                return " ".join(desc)
            elif isinstance(desc, str):
                if desc.startswith("1. "):
                    end_idx = desc.find(" 2.")
                    if end_idx != -1:
                        return desc[3:end_idx].strip()
                    return desc[3:].strip()
                elif desc.startswith("Summary:"):
                    return desc[len("Summary:"):].strip()
                return desc
            return ""
        except Exception:
            return ""

    lines = content.splitlines()

    for line in lines:
        cleaned = line.strip()
        # Strip block/comment markers
        if cleaned.startswith("/*") or cleaned.startswith("*/") or cleaned.startswith("<!--") or cleaned.startswith("-->") or cleaned.startswith('"""') or cleaned.startswith("'''"):
            cleaned = cleaned.replace("/*", "").replace("*/", "").replace("<!--", "").replace("-->", "").replace('"""', '').replace("'''", "").strip()
        if cleaned.startswith("*"):
            cleaned = cleaned[1:].strip()
        if cleaned.startswith("#") or cleaned.startswith("--") or cleaned.startswith("::"):
            # Strip comment prefixes
            cleaned = re.sub(r"^(#|--|::)\s*", "", cleaned).strip()
        elif cleaned.upper().startswith("REM"):
            cleaned = re.sub(r"^(REM|rem)\s*", "", cleaned).strip()

        if cleaned.startswith("Summary:"):
            return cleaned[len("Summary:"):].strip()

    return ""

def extract_markdown_title(filepath: str) -> str:
    """Gets the first Markdown header or first non-blank line of a prose file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned.startswith("#"):
                    return re.sub(r"^#+\s*", "", cleaned).strip()
                elif cleaned:
                    return cleaned
    except Exception:
        pass
    return ""

def main():
    owner, repo, branch = get_git_info()
    print(f"Git target: owner='{owner}', repo='{repo}', branch='{branch}'")

    included_files = []
    for root, dirs, files in os.walk("."):
        # Apply exclusions to directories
        dirs[:] = [d for d in dirs if d not in EXCLUSIONS and not d.startswith(".")]

        for file in files:
            if file in LOCK_FILES:
                continue

            # Skip backup, editor, temporary files
            if file.endswith((".bak", ".orig", ".old")) or file.endswith("~") or file.startswith("."):
                continue

            filepath = os.path.join(root, file)
            filepath = os.path.relpath(filepath, ".")

            # Additional exclusions check
            if any(ex in filepath for ex in EXCLUSIONS):
                continue

            # Exclude known binary and media types
            if file.endswith((".db", ".log", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".xml")):
                continue

            ext = os.path.splitext(file)[1]
            if ext in [".py", ".json", ".sql", ".sh", ".bat", ".toml", ".ts", ".tsx", ".css", ".html", ".mjs", ".md", ".markdown"]:
                included_files.append(filepath)

    map_entries = []
    for fp in sorted(included_files):
        if fp.endswith((".md", ".markdown")):
            desc = extract_markdown_title(fp)
        else:
            desc = extract_description(fp)

        # Formulate Raw URL dynamically
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/{branch}/{fp}"

        map_entries.append({
            "path": fp,
            "raw_url": raw_url,
            "description": desc
        })

    os.makedirs("docs", exist_ok=True)
    with open("docs/map.json", "w", encoding="utf-8") as f:
        json.dump(map_entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Part B: Generated map with {len(map_entries)} entries successfully at 'docs/map.json'!")

if __name__ == "__main__":
    main()
