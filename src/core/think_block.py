"""
Summary: Thinking block XML parser.

What it does: Extracts '<thought>' blocks from raw LLM responses to isolate reasoning from code output.

How it fits in: Used by 'src/core/ai_interface.py'.
"""



from __future__ import annotations

import re


def extract_think_block(content: str) -> tuple[str, str | None]:
    pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    match = pattern.search(content)
    if not match:
        return content, None
    thinking = match.group(1).strip()
    visible = (content[:match.start()] + content[match.end():]).strip()
    return visible, thinking
