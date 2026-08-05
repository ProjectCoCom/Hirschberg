"""
Summary: Python logic module 'Json Extract'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Json Extract'.

How it fits in: Imported and utilized by surrounding backend structures.
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

    start_idx = first_brace if (first_bracket == -1 or (first_brace != -1 and first_brace < first_bracket)) else first_bracket

    decoder = json.JSONDecoder()
    for idx in range(start_idx, len(text)):
        if text[idx] in ("{", "["):
            try:
                data, _ = decoder.raw_decode(text[idx:])
                return data
            except json.JSONDecodeError:
                continue

    return None
