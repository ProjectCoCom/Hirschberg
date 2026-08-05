"""
Summary: Core application configuration loaded from the environment.

What it does: Retrieves and exposes configurations like database URL, GitHub keys, and security credentials.

How it fits in: Referenced by server launch and backend clients to get operational parameters.
"""



import logging
import re

import structlog
from pydantic_settings import BaseSettings

SECRET_PATTERN = re.compile(
    r"(AQ\.[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sb_[A-Za-z0-9_]{20,})"
)


def _mask_secrets(_, __, event_dict: dict) -> dict:
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = SECRET_PATTERN.sub("[MASKED]", value)
    return event_dict


class Settings(BaseSettings):
    github_token: str = ""
    github_fg_token: str = ""
    encryption_key: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    default_repo_owner: str = ""
    default_repo_name: str = ""
    log_level: str = "INFO"
    max_delegation_depth: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def load_settings() -> Settings:
    settings = Settings()
    if not settings.encryption_key:
        from pathlib import Path

        from cryptography.fernet import Fernet
        new_key = Fernet.generate_key().decode()

        env_path = Path(".env")
        lines = []
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            lines = content.splitlines()

        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("ENCRYPTION_KEY="):
                lines[i] = f"ENCRYPTION_KEY={new_key}"
                found = True
                break
        if not found:
            lines.append(f"ENCRYPTION_KEY={new_key}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        settings = Settings()
        settings.encryption_key = new_key
    return settings


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _mask_secrets,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )
