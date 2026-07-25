import asyncio
import structlog
from typing import Any, Callable

from clients.local_db import LocalDB

logger = structlog.get_logger()


class Database:
    def __init__(self, mode: str = "local", local_path: str = "./data/jat.db", sync_interval: int = 30):
        self._mode = "local"
        self._local = LocalDB(local_path)

    def select_sync(self, table: str, filters: dict[str, Any] | None = None, columns: str | None = None, order_by: str | None = None, limit: int | None = None) -> list[dict]:
        return self._local.select_sync(table, filters, columns, order_by, limit)

    def insert_sync(self, table: str, data: dict[str, Any]) -> dict:
        return self._local.insert_sync(table, data)

    async def select(self, table: str, filters: dict[str, Any] | None = None, columns: str | None = None, order_by: str | None = None, limit: int | None = None) -> list[dict]:
        return await self._local.select(table, filters, columns, order_by, limit)

    async def insert(self, table: str, data: dict[str, Any]) -> dict:
        return await self._local.insert(table, data)

    async def upsert(self, table: str, data: dict[str, Any]) -> dict:
        return await self._local.upsert(table, data)

    async def update(self, table: str, data: dict[str, Any], filters: dict[str, Any] | str | None = None) -> list[dict]:
        return await self._local.update(table, data, filters)

    async def delete(self, table: str, filters: dict[str, Any] | str | None = None) -> bool:
        return await self._local.delete(table, filters)

    def subscribe(self, table: str, event_type: str, callback: Callable[[dict], None], filter_fn: Callable[[dict], bool] | None = None) -> str:
        return self._local.subscribe(table, event_type, callback, filter_fn)

    def unsubscribe(self, sub_id: str) -> None:
        self._local.unsubscribe(sub_id)

    @property
    def mode(self) -> str:
        return self._mode

    def close(self) -> None:
        if self._local:
            self._local.close()
