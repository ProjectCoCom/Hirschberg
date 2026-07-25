"""
System-wide custom exception classes.

Responsibilities:
- Defines standard error classes (e.g., JATException, AccountPoolExhausted) to organize error handling.

Coupling:
- Imported by core managers, clients, and API handlers to raise and catch exceptions consistently.
"""


class JatError(Exception):
    pass


class JulesApiError(JatError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Jules API {status_code}: {message}")

    @property
    def is_retryable(self) -> bool:
        return self.status_code >= 500 or self.status_code == 429


class GitHubApiError(JatError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API {status_code}: {message}")

    @property
    def is_retryable(self) -> bool:
        return self.status_code >= 500 or self.status_code == 429


class AccountPoolExhausted(JatError):
    pass


class WorkflowValidationError(JatError):
    pass


class DependencyTimeoutError(JatError):
    pass


class SessionTimeoutError(JatError):
    pass


class MergeFailedError(JatError):
    pass
