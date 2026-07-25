"""
Text and context compressor helper.

Responsibilities:
- Compresses excessive token streams and long histories to keep agent contexts within model limits.

Coupling:
- Assists prompt construction.
"""


from __future__ import annotations

import re

_SINGLE_LINE_COMMENT = re.compile(r"(^|\s)//[^\n]*", re.MULTILINE)
_HASH_COMMENT = re.compile(r"(^|\s)#[^\n]*", re.MULTILINE)
_MULTI_LINE_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_LONG_STRING_DOUBLE = re.compile(r'"([^"\\]|\\.){200,}"')
_LONG_STRING_SINGLE = re.compile(r"'([^'\\]|\\.){200,}'")
_CONSECUTIVE_WHITESPACE = re.compile(r"[ \t]{2,}")
_STDLIB_IMPORT = re.compile(
    r"^(?:import|from)\s+("
    r"os|sys|re|json|math|time|datetime|collections|itertools|functools|"
    r"pathlib|typing|abc|io|copy|enum|dataclasses|contextlib|operator|"
    r"string|textwrap|struct|hashlib|hmac|secrets|uuid|logging|warnings|"
    r"subprocess|shutil|tempfile|glob|fnmatch|stat|fileinput|"
    r"socket|http|urllib|email|html|xml|csv|configparser|argparse|"
    r"threading|multiprocessing|asyncio|concurrent|queue|sched|"
    r"unittest|doctest|pdb|traceback|inspect|dis|"
    r"pickle|shelve|sqlite3|zipfile|tarfile|gzip|bz2|lzma|"
    r"signal|mmap|ctypes|platform|locale|gettext|codecs"
    r")(?:\s|\.|$).*$",
    re.MULTILINE,
)


def _truncate_long_string(match: re.Match) -> str:
    full = match.group(0)
    quote = full[0]
    inner = full[1:-1]
    return f"{quote}{inner[:50]}...{quote}"


def _strip_comments(text: str) -> str:
    text = _MULTI_LINE_COMMENT.sub("", text)
    text = _SINGLE_LINE_COMMENT.sub(r"\1", text)
    text = _HASH_COMMENT.sub(r"\1", text)
    return text


def _remove_stdlib_imports(text: str) -> str:
    return _STDLIB_IMPORT.sub("", text)


def _truncate_strings(text: str) -> str:
    text = _LONG_STRING_DOUBLE.sub(_truncate_long_string, text)
    text = _LONG_STRING_SINGLE.sub(_truncate_long_string, text)
    return text


def compress_context(content: str, target_ratio: float = 0.5) -> str:
    if not content:
        return content
    result = _strip_comments(content)
    result = _remove_stdlib_imports(result)
    result = _truncate_strings(result)
    result = _TRAILING_WHITESPACE.sub("", result)
    result = _MULTIPLE_BLANK_LINES.sub("\n\n", result)
    result = _CONSECUTIVE_WHITESPACE.sub(" ", result)
    return result.strip()


def compress_xml_context(xml_content: str) -> str:
    if not xml_content:
        return xml_content

    file_pattern = re.compile(r"(<file\s+[^>]*>)(.*?)(</file>)", re.DOTALL)

    def _compress_file_block(match: re.Match) -> str:
        open_tag = match.group(1)
        inner = match.group(2)
        close_tag = match.group(3)
        compressed = compress_context(inner)
        return f"{open_tag}{compressed}{close_tag}"

    return file_pattern.sub(_compress_file_block, xml_content)
