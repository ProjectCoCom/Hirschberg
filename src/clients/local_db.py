import sqlite3
import uuid
import json
from pathlib import Path
from typing import Any, Callable


def _serialize_val(v: Any) -> Any:
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def _deserialize_row(row: dict) -> dict:
    row_dict = dict(row)
    json_cols = {"context", "artifacts", "raw_data", "message", "metadata", "value"}
    array_cols = {"depends_on", "image_urls"}
    for k, v in row_dict.items():
        if k in json_cols:
            if v is None or v == "":
                row_dict[k] = {}
            elif isinstance(v, str):
                try:
                    row_dict[k] = json.loads(v)
                except Exception:
                    row_dict[k] = {}
        elif k in array_cols:
            if v is None or v == "":
                row_dict[k] = []
            elif isinstance(v, str):
                try:
                    row_dict[k] = json.loads(v)
                except Exception:
                    row_dict[k] = []
    return row_dict


class LocalDB:
    def __init__(self, db_path: str = "./data/jat.db"):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._listeners: list[dict[str, Any]] = []

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_tables()
        return self._conn

    def _schema(self) -> str:
        return """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key_encrypted TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                plan_tier TEXT DEFAULT 'free',
                role TEXT NOT NULL DEFAULT 'worker',
                label TEXT NOT NULL DEFAULT '',
                max_concurrent INTEGER DEFAULT 3,
                max_daily_tasks INTEGER DEFAULT 15,
                enabled INTEGER DEFAULT 1,
                sessions_today INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS orchestrator_sessions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS account_sources (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                source_name TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (account_id, source_name)
            );

            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'created',
                execution_mode TEXT DEFAULT 'sequential',
                integration_branch TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agent_tasks (
                id TEXT PRIMARY KEY,
                workflow_id TEXT REFERENCES workflows(id) ON DELETE CASCADE,
                parent_task_id TEXT REFERENCES agent_tasks(id) ON DELETE SET NULL,
                account_id TEXT REFERENCES accounts(id) ON DELETE SET NULL,
                session_id TEXT,
                prompt TEXT NOT NULL,
                repo_owner TEXT NOT NULL DEFAULT '',
                repo_name TEXT NOT NULL DEFAULT '',
                branch TEXT NOT NULL DEFAULT 'main',
                status TEXT NOT NULL DEFAULT 'pending',
                depends_on TEXT NOT NULL DEFAULT '[]',
                pr_url TEXT NOT NULL DEFAULT '',
                context TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                assign_to TEXT NOT NULL DEFAULT '',
                prompt_id TEXT,
                exit_criteria TEXT NOT NULL DEFAULT '',
                orchestrator_session_id TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS context_messages (
                id TEXT PRIMARY KEY,
                from_task_id TEXT REFERENCES agent_tasks(id) ON DELETE CASCADE,
                to_task_id TEXT REFERENCES agent_tasks(id) ON DELETE CASCADE,
                task_id TEXT UNIQUE REFERENCES agent_tasks(id) ON DELETE CASCADE,
                message TEXT NOT NULL DEFAULT '{}',
                context TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS merge_queue (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                pr_url TEXT NOT NULL DEFAULT '',
                head_ref TEXT NOT NULL DEFAULT '',
                merge_strategy TEXT NOT NULL DEFAULT 'squash',
                ci_status TEXT NOT NULL DEFAULT 'pending',
                merged INTEGER DEFAULT 0,
                merge_sha TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS session_activities (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL,
                activity_id TEXT NOT NULL,
                originator TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                activity_type TEXT NOT NULL DEFAULT '',
                artifacts TEXT NOT NULL DEFAULT '[]',
                raw_data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (session_id, activity_id)
            );

            CREATE TABLE IF NOT EXISTS ai_providers (
                id TEXT PRIMARY KEY,
                provider_type TEXT NOT NULL,
                name TEXT NOT NULL UNIQUE,
                api_key_encrypted TEXT,
                model TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                enabled INTEGER DEFAULT 1,
                daily_limit INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Conversation',
                provider_id TEXT REFERENCES ai_providers(id) ON DELETE SET NULL,
                model TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL DEFAULT 'ask',
                repo_owner TEXT NOT NULL DEFAULT '',
                repo_name TEXT NOT NULL DEFAULT '',
                template TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                image_urls TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL DEFAULT 'user',
                content TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT 'xml',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id TEXT PRIMARY KEY,
                provider_type TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                conversation_id TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                plan_json TEXT NOT NULL DEFAULT '{}',
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_agent_tasks_workflow ON agent_tasks(workflow_id);
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_orchestrator ON agent_tasks(orchestrator_session_id);
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_context_messages_to ON context_messages(to_task_id);
            CREATE INDEX IF NOT EXISTS idx_merge_queue_task ON merge_queue(task_id);
            CREATE INDEX IF NOT EXISTS idx_session_activities_task ON session_activities(task_id);
            CREATE INDEX IF NOT EXISTS idx_session_activities_session ON session_activities(session_id);
            CREATE INDEX IF NOT EXISTS idx_session_activities_created ON session_activities(created_at);
            CREATE INDEX IF NOT EXISTS idx_conv_messages_conv ON conversation_messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
            CREATE INDEX IF NOT EXISTS idx_ai_providers_type ON ai_providers(provider_type);
            CREATE INDEX IF NOT EXISTS idx_prompts_source ON prompts(source);
        """

    def _seed_prompts(self) -> None:
        conn = self._get_conn()
        seeds = [
            ("security-audit", "Perform a security audit following OWASP Top 10", "builtin"),
            ("add-tests", "Add comprehensive test coverage", "builtin"),
            ("code-review", "Review code for correctness, performance, and security", "builtin"),
            ("new-project", "Scaffold a new project with best practices", "builtin"),
            ("fix-issues", "Diagnose and fix reported issues", "builtin"),
        ]
        for name, content, source in seeds:
            conn.execute(
                "INSERT OR IGNORE INTO prompts (id, name, content, source) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), name, content, source),
            )
        conn.commit()

    def _migrate_tables(self) -> None:
        conn = self._conn
        assert conn is not None

        # Migrate accounts
        cursor = conn.execute("PRAGMA table_info(accounts)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "plan_tier" not in columns:
            conn.execute("ALTER TABLE accounts ADD COLUMN plan_tier TEXT DEFAULT 'free'")
        if "role" not in columns:
            conn.execute("ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'worker'")
        if "label" not in columns:
            conn.execute("ALTER TABLE accounts ADD COLUMN label TEXT NOT NULL DEFAULT ''")

        # Migrate workflows
        cursor = conn.execute("PRAGMA table_info(workflows)")
        wf_columns = [row["name"] for row in cursor.fetchall()]
        if "execution_mode" not in wf_columns:
            conn.execute("ALTER TABLE workflows ADD COLUMN execution_mode TEXT DEFAULT 'sequential'")
        if "integration_branch" not in wf_columns:
            conn.execute("ALTER TABLE workflows ADD COLUMN integration_branch TEXT DEFAULT ''")

        # Migrate orchestrator_sessions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_sessions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Migrate agent_tasks
        cursor = conn.execute("PRAGMA table_info(agent_tasks)")
        task_columns = [row["name"] for row in cursor.fetchall()]
        if "assign_to" not in task_columns:
            conn.execute("ALTER TABLE agent_tasks ADD COLUMN assign_to TEXT NOT NULL DEFAULT ''")
        if "prompt_id" not in task_columns:
            conn.execute("ALTER TABLE agent_tasks ADD COLUMN prompt_id TEXT")
        if "exit_criteria" not in task_columns:
            conn.execute("ALTER TABLE agent_tasks ADD COLUMN exit_criteria TEXT NOT NULL DEFAULT ''")
        if "orchestrator_session_id" not in task_columns:
            conn.execute("ALTER TABLE agent_tasks ADD COLUMN orchestrator_session_id TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_orchestrator ON agent_tasks(orchestrator_session_id);")

        conn.commit()

    def _init_tables(self) -> None:
        conn = self._conn
        assert conn is not None
        conn.executescript(self._schema())
        conn.commit()
        self._migrate_tables()
        self._seed_prompts()

    def select_sync(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        conn = self._get_conn()
        cols = columns if columns else "*"
        where = ""
        params: list[Any] = []
        if filters:
            clauses = []
            for k, v in filters.items():
                if isinstance(v, (list, tuple, set)):
                    if not v:
                        clauses.append("1 = 0")
                    else:
                        serialized_vals = [_serialize_val(item) for item in v]
                        placeholders = ", ".join(["?"] * len(serialized_vals))
                        clauses.append(f"{k} IN ({placeholders})")
                        params.extend(serialized_vals)
                else:
                    clauses.append(f"{k} = ?")
                    params.append(_serialize_val(v))
            where = " WHERE " + " AND ".join(clauses)
        order = f" ORDER BY {order_by}" if order_by else ""
        lim = f" LIMIT {limit}" if limit is not None else ""
        cursor = conn.execute(f"SELECT {cols} FROM {table}{where}{order}{lim}", params)
        rows = cursor.fetchall()
        return [_deserialize_row(row) for row in rows]

    async def select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self.select_sync(table, filters, columns, order_by, limit)

    def insert_sync(self, table: str, data: dict[str, Any]) -> dict:
        conn = self._get_conn()
        if "id" not in data and table != "app_settings":
            data["id"] = str(uuid.uuid4())

        serialized_data = {k: _serialize_val(v) for k, v in data.items()}
        keys = list(serialized_data.keys())
        placeholders = ", ".join(["?"] * len(keys))
        cols = ", ".join(keys)

        conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(serialized_data.values()))
        conn.commit()

        # Notify
        self._notify(table, "INSERT", data)
        return data

    async def insert(self, table: str, data: dict[str, Any]) -> dict:
        res = self.insert_sync(table, data)
        # Notify
        self._notify(table, "INSERT", data)
        return res

    async def upsert(self, table: str, data: dict[str, Any]) -> dict:
        filters = {}
        if table == "app_settings" and "key" in data:
            filters = {"key": data["key"]}
        elif table == "context_messages" and "task_id" in data:
            filters = {"task_id": data["task_id"]}
        elif table == "session_activities" and "session_id" in data and "activity_id" in data:
            filters = {"session_id": data["session_id"], "activity_id": data["activity_id"]}
        elif "id" in data:
            filters = {"id": data["id"]}
        elif "name" in data and table in ("accounts", "ai_providers", "prompts"):
            filters = {"name": data["name"]}

        existing = []
        if filters:
            existing = await self.select(table, filters=filters)

        if existing:
            await self.update(table, data, filters=filters)
            rows = await self.select(table, filters=filters)
            updated_row = rows[0] if rows else data
            self._notify(table, "UPDATE", updated_row, existing[0])
            return updated_row
        else:
            return await self.insert(table, data)

    async def update(self, table: str, data: dict[str, Any], filters: dict[str, Any] | str | None = None) -> list[dict]:
        conn = self._get_conn()
        if isinstance(filters, str):
            filters = {"id": filters}

        old_rows = []
        if filters:
            old_rows = await self.select(table, filters=filters)

        serialized_data = {k: _serialize_val(v) for k, v in data.items()}
        sets = ", ".join([f"{k} = ?" for k in serialized_data])
        params = list(serialized_data.values())

        where = ""
        if filters:
            serialized_filters = {k: _serialize_val(v) for k, v in filters.items()}
            clauses = [f"{k} = ?" for k in serialized_filters]
            where = " WHERE " + " AND ".join(clauses)
            params.extend(serialized_filters.values())

        conn.execute(f"UPDATE {table} SET {sets}{where}", params)
        conn.commit()

        new_rows = []
        if filters:
            new_rows = await self.select(table, filters=filters)
            for i, new_row in enumerate(new_rows):
                old_row = old_rows[i] if i < len(old_rows) else None
                self._notify(table, "UPDATE", new_row, old_row)

        return new_rows if new_rows else [data]

    async def delete(self, table: str, filters: dict[str, Any] | str | None = None) -> bool:
        conn = self._get_conn()
        if isinstance(filters, str):
            filters = {"id": filters}

        old_rows = []
        if filters:
            old_rows = await self.select(table, filters=filters)

        where = ""
        params: list[Any] = []
        if filters:
            serialized_filters = {k: _serialize_val(v) for k, v in filters.items()}
            clauses = [f"{k} = ?" for k in serialized_filters]
            where = " WHERE " + " AND ".join(clauses)
            params = list(serialized_filters.values())

        conn.execute(f"DELETE FROM {table}{where}", params)
        conn.commit()

        for old_row in old_rows:
            self._notify(table, "DELETE", None, old_row)

        return True

    def subscribe(self, table: str, event_type: str, callback: Callable[[dict], None], filter_fn: Callable[[dict], bool] | None = None) -> str:
        sub_id = str(uuid.uuid4())
        self._listeners.append({
            "id": sub_id,
            "table": table,
            "event_type": event_type,
            "callback": callback,
            "filter_fn": filter_fn
        })
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        self._listeners = [l for l in self._listeners if l["id"] != sub_id]

    def _notify(self, table: str, event_type: str, new_data: dict | None, old_data: dict | None = None) -> None:
        payload = {
            "schema": "public",
            "table": table,
            "eventType": event_type,
            "new": new_data or {},
            "old": old_data or {}
        }
        for listener in list(self._listeners):
            if listener["table"] == table or listener["table"] == "*":
                if listener["event_type"] == "*" or listener["event_type"] == event_type:
                    if listener["filter_fn"] is None or listener["filter_fn"](payload):
                        try:
                            listener["callback"](payload)
                        except Exception:
                            pass

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
