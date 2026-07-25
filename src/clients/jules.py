"""
HTTP client for interacting with Jules APIs.

Responsibilities:
- Manages connection sessions, runs workspace command executions, and fetches agent logs.

Coupling:
- Tightly coupled to Jules execution services.
"""


from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from exceptions import JulesApiError
from models.jules import Activity, Session, Source

log = structlog.get_logger()

JULES_BASE_URL = "https://jules.googleapis.com/v1alpha"
DEFAULT_TIMEOUT = 30.0


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, JulesApiError) and exc.is_retryable


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
)


class JulesClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=JULES_BASE_URL,
            headers={
                "X-Goog-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=DEFAULT_TIMEOUT,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _raise_on_error(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise JulesApiError(response.status_code, response.text)

    @_retry
    async def create_session(
        self,
        prompt: str,
        source: str,
        branch: str = "main",
        title: str = "Automated Task",
        automation_mode: str = "AUTO_CREATE_PR",
        require_plan_approval: bool = False,
    ) -> Session:
        payload: dict = {
            "prompt": prompt,
            "sourceContext": {
                "source": source,
                "githubRepoContext": {"startingBranch": branch},
            },
            "automationMode": automation_mode,
            "title": title,
            "requirePlanApproval": require_plan_approval,
        }
        response = await self._client.post("/sessions", json=payload)
        self._raise_on_error(response)
        return Session.model_validate(response.json())


    @_retry
    async def get_session(self, session_id: str) -> Session:
        response = await self._client.get(f"/sessions/{session_id}")
        self._raise_on_error(response)
        return Session.model_validate(response.json())

    @_retry
    async def list_sessions(self, page_size: int = 30) -> list[Session]:
        response = await self._client.get("/sessions", params={"pageSize": page_size})
        self._raise_on_error(response)
        data = response.json()
        return [Session.model_validate(s) for s in data.get("sessions", [])]

    async def delete_session(self, session_id: str) -> None:
        response = await self._client.delete(f"/sessions/{session_id}")
        self._raise_on_error(response)

    @_retry
    async def send_message(self, session_id: str, prompt: str) -> None:
        response = await self._client.post(
            f"/sessions/{session_id}:sendMessage",
            json={"prompt": prompt},
        )
        self._raise_on_error(response)

    @_retry
    async def approve_plan(self, session_id: str) -> None:
        response = await self._client.post(
            f"/sessions/{session_id}:approvePlan",
            json={},
        )
        self._raise_on_error(response)

    @_retry
    async def list_activities(
        self, session_id: str, page_size: int = 50, since: str | None = None
    ) -> list[Activity]:
        params: dict = {"pageSize": page_size}
        if since:
            params["createTime"] = since
        response = await self._client.get(
            f"/sessions/{session_id}/activities",
            params=params,
        )
        self._raise_on_error(response)
        data = response.json()
        return [Activity.model_validate(a) for a in data.get("activities", [])]

    @_retry
    async def get_activity(self, session_id: str, activity_id: str) -> Activity:
        response = await self._client.get(
            f"/sessions/{session_id}/activities/{activity_id}"
        )
        self._raise_on_error(response)
        return Activity.model_validate(response.json())

    @_retry
    async def list_sources(self, page_size: int = 100) -> list[Source]:
        response = await self._client.get("/sources", params={"pageSize": page_size})
        self._raise_on_error(response)
        data = response.json()
        return [Source.model_validate(s) for s in data.get("sources", [])]
