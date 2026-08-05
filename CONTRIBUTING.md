# Contributor Guidelines

Welcome! This document provides guidelines for contributing to this project.

## Table of Contents
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Review Process](#code-review-process)

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/REPO_NAME.git`
3. Add upstream remote: `git remote add upstream https://github.com/ORIGINAL_OWNER/REPO_NAME.git`
4. Create a branch: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites
- Python 3.11+
- pip or uv package manager
- Git

### Installation
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests to verify setup
pytest
```

### Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
DATABASE_URL=sqlite+aiosqlite:///./test.db
GITHUB_TOKEN=your_github_token
JULES_API_KEY=your_jules_key
```

## Coding Standards

### Code Style
- Follow PEP 8 style guidelines
- Use Ruff for linting: `ruff check src/`
- Auto-fix issues when possible: `ruff check src/ --fix`
- Maximum line length: 120 characters

### Type Annotations
- All public functions must have type hints
- Use Pydantic models for data structures
- Run MyPy for type checking: `mypy src/`

### Documentation
- Module-level docstrings for all files
- Google-style docstrings for public functions and classes
- Include Args, Returns, Raises sections as appropriate

Example:
```python
def process_workflow(workflow: Workflow) -> WorkflowStatus:
    """Process a workflow and execute all tasks.
    
    Args:
        workflow: The workflow to process
        
    Returns:
        The final workflow status
        
    Raises:
        WorkflowValidationError: If the workflow is invalid
    """
```

### Logging
- Use structlog for all logging
- Include request_id, session_id in log context where applicable
- Log at appropriate levels (debug, info, warning, error)

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_workflow_engine.py

# Run async tests
pytest -k "async"
```

### Writing Tests
- Use pytest fixtures for setup/teardown
- Mock external services (GitHub, AI providers)
- Test both success and failure paths
- Aim for >80% code coverage

### Test Structure
```python
class TestComponentName:
    """Tests for ComponentName."""
    
    def test_happy_path(self):
        """Test the normal success case."""
        # Arrange
        # Act
        # Assert
    
    def test_error_case(self):
        """Test error handling."""
        # Arrange
        # Act
        # Assert
```

## Submitting Changes

### Commit Messages
Follow conventional commits format:
```
feat: add new workflow validation
fix: resolve race condition in coordinator
docs: update API documentation
test: add tests for edge cases
refactor: simplify error handling logic
```

### Pull Request Process
1. Ensure all tests pass: `pytest`
2. Run linters: `ruff check src/ && mypy src/`
3. Update documentation if needed
4. Create PR with clear description
5. Link to related issues
6. Request review from maintainers

### PR Checklist
- [ ] Tests added/updated
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Documentation updated
- [ ] Changelog entry added (if applicable)

## Code Review Process

### Reviewer Guidelines
- Review within 24-48 hours
- Be constructive and respectful
- Focus on correctness, clarity, and consistency
- Suggest improvements, don't just point out problems

### Common Review Points
- **Correctness**: Does the code work as intended?
- **Testing**: Are there adequate tests?
- **Performance**: Any obvious performance issues?
- **Security**: Proper input validation and error handling?
- **Maintainability**: Is the code clear and well-structured?

## Questions?

- Check existing documentation in `/docs`
- Review Architecture Decision Records in `/docs/adr`
- Open an issue for clarification
- Ask in team chat channels

---

Thank you for contributing! 🎉
