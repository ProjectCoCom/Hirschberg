"""
JSON object extraction utility.

Responsibilities:
- Provides a robust, brace-nesting-aware helper to extract JSON objects
  from mixed conversational text using `json.JSONDecoder().raw_decode()`.

Coupling:
- Used by `src/core/qa_reviewer.py`, `src/core/decomposer.py`, and `src/core/auto_mode.py`.
"""

from __future__ import annotations

import json


def extract_json_object(text: str) -> dict | list | None:
    """Robust, brace-nesting-aware helper that extracts the first complete JSON object or array
    from a given text string using json.JSONDecoder.raw_decode.
    Returns None if no valid JSON block can be parsed.
    """
    first_brace = text.find("{")
    first_bracket = text.find("[")

    if first_brace == -1 and first_bracket == -1:
        return None

    # Pick the earlier of { or [
    if first_bracket == -1:
        start_idx = first_brace
    elif first_brace == -1:
        start_idx = first_bracket
    else:
        start_idx = first_brace if first_brace < first_bracket else first_bracket

    decoder = json.JSONDecoder()
    for idx in range(start_idx, len(text)):
        if text[idx] in ("{", "["):
            try:
                data, _ = decoder.raw_decode(text[idx:])
                return data
            except json.JSONDecodeError:
                continue

    return None
