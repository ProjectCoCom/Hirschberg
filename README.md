# JAT-AI

This is a fork of https://github.com/iceyxsm/JAT-AI. It is undergoing an extreme remodel, and should not be considered functional or stable, in any way, until this document is updated to advise as such.

## Project Structure

```
/workspace
├── src/                          # Main source code directory
│   └── jat_ai/                   # Core package
│       ├── __init__.py           # Package initialization
│       ├── config.py             # Configuration management
│       ├── models/               # Data models (Pydantic)
│       ├── services/             # Business logic services
│       ├── api/                  # API endpoints (FastAPI)
│       └── utils/                # Utility functions
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── conftest.py               # Pytest fixtures
├── scripts/                      # Utility scripts
│   └── cleanup.sh                # Cleanup temporary files
├── data/                         # Data storage (databases, etc.)
├── docs/                         # Documentation
├── pyproject.toml                # Project configuration & dependencies
├── requirements.txt              # Pinned dependencies
├── .dockerignore                 # Docker ignore patterns
├── .gitattributes                # Git line ending configurations
├── .gitignore                    # Git ignore patterns
├── README.md                     # This file
└── HIRSCHBERG_REMEDIATION_PLAN.md # Remediation plan document
```

## Directory Descriptions

- **src/jat_ai/**: Core application code organized into modules
  - `config.py`: Application configuration using pydantic-settings
  - `models/`: Pydantic models for data validation
  - `services/`: Business logic and external service integrations
  - `api/`: FastAPI route handlers and endpoints
  - `utils/`: Helper functions and utilities

- **tests/**: Comprehensive test suite
  - Unit tests for individual components
  - Integration tests for service interactions
  - Fixtures and conftest for test setup

- **scripts/**: Automation and utility scripts
  - `cleanup.sh`: Removes cache files, build artifacts, and temporary data

- **data/**: Runtime data storage
  - SQLite databases
  - Temporary files (cleaned by cleanup script)

- **docs/**: Project documentation

## Technology Stack

- **Python**: Primary language
- **FastAPI**: Web framework for API development
- **Pydantic**: Data validation and settings management
- **HTTPX**: Async HTTP client
- **Tenacity**: Retry logic
- **Structlog**: Structured logging
- **ChromaDB**: Vector database
- **Tiktoken**: Tokenization
- **pytest**: Testing framework
- **mypy**: Static type checking
- **ruff**: Code linting and formatting

## Development Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run cleanup script: `./scripts/cleanup.sh`
4. Configure environment variables as needed

## Scripts

- **cleanup.sh**: Removes temporary files, cache directories, and build artifacts
