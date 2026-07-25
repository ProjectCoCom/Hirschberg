#!/usr/bin/env python3
"""
scripts/generate_map.py

Responsibilities:
- Walks the repository (respecting Part A's exclusions) and parses each file's header.
- Extracts the one-line summary from the header.
- Formulates the 'raw_url' using git configuration (remote origin URL and 'development' branch).
- Generates 'docs/map.json' containing metadata maps of all hand-authored files.

Coupling:
- Relies on 'git' commands and standard subprocess functions.
- Consumes file headers written by 'scripts/generate_headers.py'.
"""

import os
import json
import subprocess
import re

# Standardized exclusions (same as Part A)
EXCLUSIONS = [
    "node_modules", ".venv", "site-packages", ".git", ".pytest_cache", "__pycache__", ".jules", "docs/map.json"
]
LOCK_FILES = ["uv.lock", "package-lock.json", "pnpm-lock.yaml"]

def get_git_info():
    """Derives owner and repo name dynamically from git configuration."""
    owner = "ProjectCoCom"
    repo = "Hirschberg"

    try:
        # Get remote URL
        url_res = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        url = url_res.stdout.strip()
        # Extract owner/repo from SSH or HTTPS github URL
        # Matches formats:
        # https://github.com/owner/repo[.git]
        # git@github.com:owner/repo.git
        match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
        if match:
            owner = match.group(1)
            repo = match.group(2)
    except Exception as e:
        print(f"Warning: failed to fetch git remote origin: {e}. Defaulting to '{owner}/{repo}'.")

    return owner, repo

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
            desc = data.get("_description", "")
            if desc.startswith("1. "):
                end_idx = desc.find(" 2.")
                if end_idx != -1:
                    return desc[3:end_idx].strip()
                return desc[3:].strip()
            return desc
        except Exception:
            return ""

    lines = content.splitlines()

    if ext == ".py":
        in_docstring = False
        marker = None
        for line in lines:
            if not in_docstring:
                if '"""' in line:
                    in_docstring = True
                    marker = '"""'
                    cleaned = line.split('"""', 1)[1].strip()
                    if cleaned:
                        return cleaned
                elif "'''" in line:
                    in_docstring = True
                    marker = "'''"
                    cleaned = line.split("'''", 1)[1].strip()
                    if cleaned:
                        return cleaned
            else:
                if marker in line:
                    cleaned = line.split(marker, 1)[0].strip()
                    if cleaned:
                        return cleaned
                    break
                # If first line after docstring start is not empty and not filename
                cleaned = line.strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    elif ext in [".ts", ".tsx", ".js", ".mjs", ".css"]:
        in_comment = False
        for line in lines:
            if not in_comment:
                if "/*" in line:
                    in_comment = True
                    cleaned = line.split("/*", 1)[1].strip()
                    if cleaned.startswith("*"):
                        cleaned = cleaned[1:].strip()
                    if cleaned and not cleaned.startswith("*/") and not cleaned.startswith(filepath):
                        return cleaned
            else:
                if "*/" in line:
                    cleaned = line.split("*/", 1)[0].strip()
                    if cleaned.startswith("*"):
                        cleaned = cleaned[1:].strip()
                    if cleaned and not cleaned.startswith(filepath):
                        return cleaned
                    break
                cleaned = line.strip()
                if cleaned.startswith("*"):
                    cleaned = cleaned[1:].strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    elif ext == ".html":
        in_comment = False
        for line in lines:
            if not in_comment:
                if "<!--" in line:
                    in_comment = True
                    cleaned = line.split("<!--", 1)[1].strip()
                    if cleaned and not cleaned.startswith("-->") and not cleaned.startswith(filepath):
                        return cleaned
            else:
                if "-->" in line:
                    cleaned = line.split("-->", 1)[0].strip()
                    if cleaned and not cleaned.startswith(filepath):
                        return cleaned
                    break
                cleaned = line.strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    elif ext in [".sh", ".toml"]:
        for line in lines:
            if line.strip().startswith("#"):
                cleaned = line.strip()[1:].strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    elif ext == ".bat":
        for line in lines:
            if line.strip().upper().startswith("REM"):
                cleaned = line.strip()[3:].strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned
            elif line.strip().startswith("::"):
                cleaned = line.strip()[2:].strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    elif ext == ".sql":
        for line in lines:
            if line.strip().startswith("--"):
                cleaned = line.strip()[2:].strip()
                if cleaned and not cleaned.startswith(filepath):
                    return cleaned

    return ""

def main():
    owner, repo = get_git_info()
    branch = "development" # Strictly hardcode branch to 'development' per user request
    print(f"Git target: owner='{owner}', repo='{repo}', branch='{branch}'")

    included_files = []
    for root, dirs, files in os.walk("."):
        # Apply exclusions to directories
        dirs[:] = [d for d in dirs if d not in EXCLUSIONS and not d.startswith(".")]

        for file in files:
            if file in LOCK_FILES:
                continue

            filepath = os.path.join(root, file)
            filepath = os.path.relpath(filepath, ".")

            # Additional exclusions check
            if any(ex in filepath for ex in EXCLUSIONS):
                continue

            # Exclude known binary and media types
            if file.endswith((".db", ".log", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".md", ".xml")):
                continue

            ext = os.path.splitext(file)[1]
            if ext in [".py", ".json", ".sql", ".sh", ".bat", ".toml", ".ts", ".tsx", ".css", ".html", ".mjs"]:
                included_files.append(filepath)

    map_entries = []
    for fp in sorted(included_files):
        desc = extract_description(fp)
        # Formulate Raw URL using the exact convention:
        # https://raw.githubusercontent.com/[owner]/[repo]/refs/heads/[branch]/[relative path]
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
