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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def load_settings() -> Settings:
    return Settings()


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
