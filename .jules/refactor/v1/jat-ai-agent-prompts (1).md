# JAT-AI Fork — Agent Prompts

Prompts for dispatching Jules "developer agent" sessions against your JAT-AI fork, one per build-order step. Each is meant to be pasted as the `prompt` field when creating a session, on its own branch, against the actual fork repo — not the control-plane repo.

Grounded against the real source (`account_pool.py`, `coordinator.py`, `workflow_engine.py`, `session_runner.py`, `auto_merge.py`, `models/workflow.py`, `prompts/system_prompts.py`, `supabase/schema.sql`, `clients/jules.py`, `context_store.py`, `tracker.py`, `prompt_builder.py`, `clients/github.py`, `mcp/server.py`, `plan_executor.py`, `config_loader.py`) rather than the README's summary. Where a file wasn't available, the prompt says so and tells the agent to inspect first instead of guessing.

Run these **in order, one at a time**. They touch overlapping files throughout; dispatching them in parallel will produce merge conflicts between your own agents. Merge each PR before starting the next.

**Step 4 is a harder dependency than the numbering alone suggests.** It retires `plan_executor.py`, a second, previously-unknown execution engine that runs independently of everything else in this document — including an unconditional auto-approve of every plan, which means Step 7's whole point (a human approval gate) silently does nothing until Step 4 is actually merged. Don't skip ahead to 7 while 4 is still pending.

1. Fork JAT-AI — just `git clone`, no prompt needed.
2. Remove Supabase, complete local database functionality.
3. Account roles + retire ai_providers planning.
4. Consolidate onto one execution engine (retires plan_executor.py's parallel system).
5. Wake-up loop: status relay, mid-task questions, fail-fast fix.
6. QA gate.
7. requirePlanApproval + audit trail.
8. Recursive dispatch to sub-orchestrators (stretch).
9. Backpressure-aware dispatch (performance/correctness).
10. SQLite write-concurrency tuning (performance).
11. Capacity-aware account routing (performance).
12. Query pattern fixes: context_store.py and tracker.py (performance).
13. Consolidate session polling into one shared engine (performance).
14. Reduce auto_merge.py's check-polling overhead (performance).
15. Fix the MCP server's per-call event loop creation (performance/correctness).
16. Cache prompt_builder.py's template reads (performance).

UI changes are intentionally excluded — that's your own work, last.

Steps 9-16 are additive fixes to functions Steps 2, 3, 5, and 6 already touch. Dispatch them
after 2-8 are merged, not interleaved with them, for the same merge-conflict reasons as
everything else in this document. Step 12 specifically should run after Step 2, since it
depends on Step 2's decision about context_messages' upsert conflict target. Step 13 is worth
considering out of order: if Steps 5 and 7 haven't been dispatched yet, doing Step 13 first
means they only touch one polling implementation instead of two. Step 15 is independent of
everything else and can run any time. Step 16 is independent too, but touches the same file
Step 3 redirects away from for planning (prompt_builder.py) — fine to run either order, just
not simultaneously.

---

## Step 2 — Remove Supabase, complete local database functionality

```
Replace Supabase with a fully-functional local SQLite database. No Supabase configuration,
client, or dependency should remain anywhere in the codebase.

CONTEXT
supabase/schema.sql defines at least twelve Postgres tables — treat this as a floor, not a
ceiling; two more (plans, token_usage) turned up in files outside this document's original
scope, so there may be others: accounts, account_sources, workflows, agent_tasks,
context_messages, merge_queue, session_activities, ai_providers, conversations,
conversation_messages, prompts (a seeded prompt library — security-audit, add-tests,
code-review, new-project, fix-issues), plans (conversation_id, title, plan_json, status —
draft plans saved from chat, see Step 4), and token_usage. It uses uuid_generate_v4()/
gen_random_uuid(), jsonb columns, a native uuid[] array column (agent_tasks.depends_on),
timestamptz, an idempotent index-creation block wrapped in "do $$ ... $$", and RLS-disable
statements at the end. Get an actual full table list directly from the file rather than
trusting this one to be complete.

config.example.json already has a database.mode setting with a "local" option pointing at
./data/jat.db and a sync_interval value — inspect src/config.py and src/clients/supabase.py
first to see how much of local mode already works versus how much is a stub, and what the
sync_interval is actually doing (it may imply local currently syncs to Supabase rather than
standing alone — confirm before assuming).

Resolved, not a risk after all: core/rag_store.py (used by api/chat.py for conversation/
context retrieval) runs on ChromaDB, a self-contained, file-based embedded vector store
(data/chromadb/) — not pgvector, not Postgres at all. It's already independent of whichever
relational database the rest of the app uses, already degrades gracefully to a no-op if
chromadb isn't installed, and needs no changes as part of this step.

Several files call a generic db.update(table, values, filter) / db.upsert(table, values) /
db.select(table, filters) / db.insert(table, values) / db.delete(table, filters) interface
interface on a SupabaseClient instance (confirmed in session_runner.py — search for the same
pattern elsewhere). If clients/supabase.py's full interface is a plain table/filter CRUD
surface like this, a SQLite-backed client implementing the identical method signatures can be
a largely mechanical swap at most call sites.

REQUIREMENTS
- Inspect src/clients/supabase.py fully first to get its complete method surface (not just
  update/upsert — also whatever select/read methods exist).
- Build src/clients/local_db.py implementing the same method surface against SQLite, so
  existing call sites need only a different import and constructor, not rewritten logic.
- Translate supabase/schema.sql to SQLite as a new local schema file, table for table:
    - UUID primary/foreign keys -> TEXT columns holding UUID strings, generated in Python
      (uuid4()) at insert time — SQLite has no native UUID generation.
    - jsonb columns (context_messages.message/context, session_activities.artifacts/raw_data,
      agent_tasks.context, conversation_messages.metadata, etc.) -> TEXT columns holding JSON
      strings.
    - agent_tasks.depends_on (currently a native uuid[] array) -> a JSON-encoded TEXT array,
      for consistency with every other JSON column above rather than a separate join table.
      Keep the application-level shape (a list of UUID strings) identical — only the storage
      encoding changes.
    - timestamptz -> TEXT storing ISO-8601, default (datetime('now')).
    - The "do $$ ... $$" idempotent index block -> plain CREATE INDEX IF NOT EXISTS
      statements, which SQLite supports directly with no wrapper needed.
    - "on conflict (...) do nothing" seed inserts -> SQLite supports the same ON CONFLICT
      syntax; keep the seeded prompts library (security-audit, add-tests, code-review,
      new-project, fix-issues) intact.
    - Drop the RLS-disable statements entirely — SQLite has no row-level security model, they
      don't translate to anything.
    - Ensure the app's SQLite connection setup runs PRAGMA foreign_keys = ON — SQLite doesn't
      enforce declared foreign keys unless this is set per connection.
- accounts' API key storage: confirmed via plan_executor.py and api/chat.py, not a guess
  anymore — it's read as a column (seen as api_key_encrypted in both places; check whether
  this is the same column referenced elsewhere as api_key_hash or whether both exist for
  different purposes) and decrypted through core.ai_interface.KeyVault.decrypt() before use.
  This is reversible, symmetric encryption, not a one-way hash. api/chat.py's _decrypt_key()
  also strips a leading "\x" before decrypting — that's Postgres's own hex representation of
  a bytea column when cast to text, not part of KeyVault's actual encryption format. That
  workaround is Postgres-specific and becomes dead weight (or a bug, if it strips a real
  leading "\x" out of a value that happens to start that way) once this runs against SQLite,
  which doesn't return binary columns that way — don't carry it forward unchanged. The local
  replacement must use the same KeyVault-based approach with the same key material handling —
  don't simplify this into a true one-way hash (which would break the ability to retrieve a
  usable key) or plaintext storage.
- tracker.py's subscribe_task_updates(), subscribe_activity_updates(), and
  subscribe_workflow_tasks() are built entirely on Supabase's realtime feature
  (self._db.client.channel(...).on_postgres_changes(...).subscribe()) — a websocket-based
  Postgres change feed with no SQLite equivalent. These will break the moment Supabase is
  removed unless replaced. Build an in-process pub/sub mechanism instead: local_db.py's
  insert/upsert methods should fire an in-process callback immediately after a successful
  write to the affected table, and tracker.py's three subscribe_* methods should register
  against that in-process emitter instead of a Supabase channel — same external interface
  (register a callback against a table, optionally filtered by workflow_id), different
  mechanism underneath. Separately, confirm whether the dashboard's frontend currently
  subscribes to Supabase realtime directly from the browser rather than through tracker.py —
  if it does, the app needs its own WebSocket or Server-Sent-Events endpoint to relay these
  in-process events to connected browser clients, since local SQLite has no browser-reachable
  equivalent to Supabase's hosted realtime infrastructure. Don't assume the in-process fix
  alone covers this without checking.
- context_store.py's save_result() upserts into context_messages using only task_id, with no
  visible unique constraint on that column in the current schema and no explicit ordering
  when it's read back (get_dependency_context takes rows[0], implicitly assuming either "one
  row per task_id" or "first row is authoritative"). Decide this explicitly during the schema
  translation: add a unique constraint on task_id if per-task upsert-not-insert is the
  intended behavior, and make sure local_db.py's upsert() actually enforces it — don't carry
  forward an implicit assumption that happened to hold by accident under Supabase's ordering.
- Remove the supabase section from config.example.json. Grep the whole codebase (not just
  files already named in this build order) for "clients.supabase" / "from clients import
  supabase" and remove every reference, including the sync_interval concept if it turns out
  to be Supabase-sync-specific. Confirmed concrete example: mcp/server.py's _get_db() builds
  a SupabaseClient directly from os.environ["SUPABASE_URL"]/["SUPABASE_KEY"] — this needs to
  point at local_db.py instead, or it'll crash outright the moment those env vars are gone.
- Make local the only mode — remove the mode switch entirely, don't leave a dead branch.

CONSTRAINTS
- Don't change table shapes beyond what SQLite requires — role/label columns for accounts are
  the next step's job, not this one.
- Keep the db interface identical to what callers already use, so touching those call sites
  is mechanical (swap the import/constructor) everywhere except local_db.py itself.

ACCEPTANCE CRITERIA
- The application runs end to end — account creation, a workflow with dependent tasks,
  session polling, activity storage, merge — with zero Supabase configuration present and no
  supabase package imported anywhere.
- PRAGMA foreign_keys is confirmed on, and an invalid foreign key insert is rejected.
- Subscribing to task/activity updates through tracker.py's three subscribe_* methods still
  delivers live callbacks with Supabase fully removed — verify this directly, not just that
  the methods don't error.
- A second save_result() call for the same task_id updates the existing context_messages row
  rather than creating a duplicate, and get_dependency_context returns the current value.
- Existing tests pass against the local DB; add a test confirming a workflow's tasks and
  their depends_on relationships round-trip correctly through the JSON-array encoding.
```

---

## Step 3 — Account roles + retire ai_providers planning

```
Add a role field to Jules accounts and stop routing plan construction through the ai_providers
pool.

CONTEXT
src/core/account_pool.py currently defines:

    class PlanTier(StrEnum):
        FREE = "free"
        PRO = "pro"
        ULTRA = "ultra"

    @dataclass
    class Account:
        id: UUID = field(default_factory=uuid4)
        name: str = ""
        api_key: str = ""
        plan: PlanTier = PlanTier.FREE
        active_sessions: int = 0
        daily_tasks_used: int = 0
        daily_reset_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        sources: list[str] = field(default_factory=list)
        enabled: bool = True

There is no role concept yet. AccountPool.acquire(source=None) filters to accounts with
has_capacity, optionally narrows to accounts whose sources list contains the requested source
(coordinator.py calls this with source formatted as "sources/github/{owner}/{repo}") — but
falls back to the full eligible list if none match, a soft preference, not a hard filter —
sorts by active_sessions ascending, and returns the least-loaded match.

Separately, src/prompts/system_prompts.py defines PLAN_MODE_SYSTEM and AUTO_MODE_SYSTEM: full
system prompts that make an ai_providers chat model (Groq/Gemini/etc.) act as "JAT-AI" and
decompose a goal directly into a JSON task plan with the user, entirely independent of Jules.
This is the mechanism we're retiring — plan authorship becomes the standing orchestrator
Jules session's job (Step 4), not a chat model's.

REQUIREMENTS
- In src/core/account_pool.py, add an AccountRole StrEnum next to PlanTier:

    class AccountRole(StrEnum):
        ORCHESTRATOR = "orchestrator"
        WORKER = "worker"
        QA = "qa"

- Add two fields to the Account dataclass, following its existing style:
    role: AccountRole = AccountRole.WORKER
    label: str = ""

- Change AccountPool.acquire() to accept role: AccountRole | None = None, applied before the
  existing source filter. Unlike source, role must be a hard requirement: if role is given
  and no eligible account has that role, raise AccountPoolExhausted with a role-aware
  message. Never fall back to returning an account of the wrong role.
- Add role to the dict returned by AccountPool.status(), alongside the existing fields — this
  is what the dashboard's account table will read.
- Update coordinator.py's account_pool.acquire(source) call in run_task() to also pass the
  role appropriate to the task being run.
- config_loader.py's build_jules_pool() is the confirmed function that constructs Account
  objects at startup and calls add_account() for each — pass role/label through here.
  It currently sources accounts from config.json's jules.accounts[], which is a separate,
  disconnected list from the accounts DB table the dashboard actually writes to (confirmed:
  plan_executor.py reads accounts straight from that table via a completely different path).
  Change build_jules_pool() to read from the accounts table instead of config.json, so
  there's one source of truth for accounts feeding account_pool.py — an account added through
  the dashboard should be visible here without also needing a config.json edit. This is
  related to but not blocking Step 4's bigger consolidation; do it here since you're already
  touching this function for role/label.
- Add role and label columns to whichever local SQLite schema Step 2 produced (not
  supabase/schema.sql, which Step 2 removes) — match its conventions, default existing rows
  to "worker".
- Update the dashboard's existing account form/table to expose role (dropdown) and label
  (text). Match the current form's patterns exactly — don't restyle anything else.
- No change needed to how plan/auto mode chat works — api/chat.py's chat_send() (ask/plan/
  build/auto, RAG context, summarization, skills injection, multi-key ai_providers failover)
  is confirmed to be legitimate, general-purpose chat infrastructure with nothing specific to
  retire here. What actually changes is what happens to a saved plan once someone wants it
  executed, which is Step 4's job, not this one — see Step 4's context for the full picture.

CONSTRAINTS
- Don't touch workflow_engine.py, session_runner.py, or anything outside
  account/config/schema/dashboard-form scope.
- Don't redesign the dashboard visually.
- Preserve acquire()'s existing behavior exactly when role is not passed (None).

ACCEPTANCE CRITERIA
- An operator can tag each connected account as orchestrator/worker/qa from the dashboard.
- acquire(role=AccountRole.WORKER) never returns an orchestrator- or qa-tagged account, and
  raises AccountPoolExhausted — not a silent fallback — when none are available.
- Existing calls to acquire() with no role argument behave exactly as before.
- Chat-based plan drafting (api/chat.py's plan/auto modes) still works exactly as before —
  this step doesn't touch it.
- Existing tests pass; add tests covering role-filtered acquisition, including the
  no-fallback-on-miss behavior.
```

---

## Step 4 — Consolidate onto one execution engine

```
There are two independent, non-integrated systems for running Jules tasks in this codebase.
Consolidate onto the one with persistence, retries, and dependency-aware parallelism, and
retire the other's execution machinery.

CONTEXT
System A: workflow_engine.py + coordinator.py + account_pool.py + clients/jules.py +
context_store.py. Accounts sourced from config.json via config_loader.build_jules_pool() —
being repointed at the accounts table in Step 3. Tasks persisted to agent_tasks/workflows via
the shared db interface. Proper retries (tenacity), proper connection reuse (per-account
cached JulesClient), dependency-aware parallel execution, and — once Steps 2, 3, 5, 6, 7, 9,
11, and 13 land — local-DB backed, role-aware, capacity-aware, QA-gated, and
backpressure-safe. Every other step in this document builds on top of this system.

System B: core/plan_executor.py. api/chat.py is confirmed NOT to be its caller, despite being
the reasonable guess — chat_send() handles ask/plan/build/auto mode chat (RAG context
retrieval, conversation summarization, skills injection, multi-key ai_providers failover, all
of it legitimate and unrelated to orchestration, none of it needing to change) and, when a
plan/auto response includes a [ACTION:PLAN_SAVE:title|json] tag, saves the raw plan JSON into
a plans table (conversation_id, title, plan_json, status) as a draft. It never calls
parse_plan() or create_jules_session(). api/plans.py is confirmed to be plain CRUD on that
same table (list/get/create/update/delete) — no execute action, no call to parse_plan() or
create_jules_session() there either. Two reasonable candidates checked and ruled out; the
actual trigger, if it exists as a complete working flow anywhere, is unlocated — cli.py is
the remaining plausible candidate. It's equally possible plan_executor.py's execution
functions are built but never fully wired into a callable end-to-end flow yet. If so, that's
good news for this step: there's nothing working to carefully migrate away from, only
building blocks to assemble correctly using workflow_engine.py from the start.

This changes the design, for the better regardless of which is true: plan/auto mode chat
stays exactly as it is — a cheap, fast way for a human to rough out a plan and get it saved
as a draft. What this step actually changes is what happens after that draft exists. Instead
of a saved plan getting parsed and dispatched directly (whether that currently happens
somewhere unfound or has simply never been finished), a saved plan becomes an input a human
hands to the standing orchestrator Jules session — "here's a draft, refine and run it" —
rather than something auto-executed the moment it's saved. The fast/cheap model stays good at
what it's good at; the accountable, code-verifying decision of what actually gets built moves
to Jules.

parse_plan() reads the same JSON shape PLAN_MODE_SYSTEM/AUTO_MODE_SYSTEM produce:

    {
      "tasks": [
        {
          "id": "agent-1",
          "description": "What this agent does",
          "prompt_id": "skill-name-from-available-skills-or-null",
          "dependencies": [],
          "exit_criteria": "How to verify this is done",
          "branch": "jat/agent-1-description"
        }
      ],
      "execution_mode": "hybrid"
    }

into plan_executor's own lightweight AgentTask dataclass — structurally different from
models/workflow.py's AgentTask (string IDs vs UUIDs, no workflow_id/parent_task_id/
account_id, no TaskStatus enum). From there, System B runs entirely on its own:
- get_jules_key() picks an account by querying the accounts table directly and taking
  whichever enabled row has the lowest sessions_today — no role awareness, no source
  matching, nothing from account_pool.py. Once Step 3 adds a role column, this function has
  no way to know it exists and would happily hand out an orchestrator or QA account for
  ordinary task dispatch.
- create_jules_session(), send_message_to_session(), _approve_plan(), poll_session_status(),
  and _fetch_recent_activities() all make raw httpx calls straight to
  https://jules.googleapis.com, duplicating clients/jules.py's JulesClient with less
  robustness — most of these calls have no retry logic at all.
- poll_session_status() is a fourth independent session-polling loop, on top of the two Step
  13 already consolidates and the mcp/server.py call site Step 13 confirmed delegates to one
  of them.
- poll_session_status() auto-approves every AWAITING_PLAN_APPROVAL unconditionally — no
  condition, no human involved. This is the exact state Step 7 adds human gating for. Left
  running, Step 7's require_plan_approval gate does nothing for anything dispatched through
  System B — it gets rubber-stamped before a human ever sees it.
- poll_session_status() answers a worker's mid-task question via _answer_jules_question(),
  which calls the ai_providers pool directly. This is the real call site Step 5 needs to
  redirect — more concrete than system_prompts.py's JULES_QUESTION_HANDLER in isolation.
- None of System B's task execution touches agent_tasks, workflows, context_messages, or
  session_activities — only accounts.sessions_today gets written. Nothing dispatched this way
  is visible to the dashboard's task views, Step 7's audit trail, or Step 6's QA gate, because
  none of those are looking at this code path.
- create_jules_session() builds its prompt directly, without going through
  prompt_builder.py — sessions dispatched this way never get the rules/gates/anti-patterns/
  context injection Step 16 caches. They get a bare prompt.

Recommendation: retire System B's execution machinery — get_jules_key(),
create_jules_session(), send_message_to_session(), _approve_plan(), poll_session_status(),
_fetch_recent_activities(), _answer_jules_question(), and the raw httpx layer under all of
them — and keep only parse_plan() for what it's actually good at: turning the chat
interface's JSON output into structured data. Retarget that output at models/workflow.py's
Workflow/AgentTask shape and hand it to workflow_engine.py instead of driving a second, weaker
execution path. This is a real architectural call, not a small refactor — if there's a reason
to keep two separate engines that isn't visible from the code alone, say so before this gets
built, since Steps 5, 7, 13, and 16 all assume there's exactly one by the time they land.

REQUIREMENTS
- Add assign_to: str (account name or label) to the plan JSON shape above. Everything else
  (id, description, dependencies, exit_criteria, branch, prompt_id, execution_mode) stays
  exactly as-is.
- Change parse_plan() to build models/workflow.py's Workflow/AgentTask objects — translating
  string dependency references like "agent-1" into the UUID-based depends_on list once real
  task UUIDs are assigned — instead of plan_executor's own AgentTask dataclass.
- Locate wherever a saved plans row's plan_json currently gets handed to parse_plan() and
  looped through create_jules_session() — confirmed not to be api/chat.py or api/plans.py
  (the latter is plain CRUD, no execute action); grep for parse_plan( to settle it, or check
  cli.py next. If nothing turns up a complete, callable version of this flow, don't build one
  that mimics System B's approach — go straight to building it the way this step already
  describes (parse_plan() output as a Workflow, executed by workflow_engine.run()), since
  there'd be no existing working behavior to preserve compatibility with.
- Resolve assign_to through the role-aware account_pool.py (Step 3).
- Delete get_jules_key(), create_jules_session(), send_message_to_session(), _approve_plan(),
  poll_session_status(), _fetch_recent_activities(), _answer_jules_question(), and
  _increment_sessions_today()/reset_daily_sessions() if nothing else needs them once this
  lands — account_pool.py's daily_tasks_used/daily_reset_at already covers the same job.
- AgentTask.context is currently dict[str, str]. Step 6's QA verdict needs structured data.
  Decide once, here, whether to JSON-encode structured values into that dict's string values
  or widen the type — apply that decision consistently, don't let later steps make a
  different choice.

CONSTRAINTS
- Don't touch how dependencies already resolves within workflow_engine.py — only add the
  assign_to -> account_id resolution and the parse_plan() retargeting.
- Malformed or partial plan output should log and wait for a corrected version, not crash
  anything downstream.
- If retiring System B's execution functions breaks something not visible from the files
  inspected so far — a caller expecting plan_executor's specific dataclass shape, for
  instance — stop and flag it rather than silently working around it.

ACCEPTANCE CRITERIA
- A plan produced via the chat interface (or a Jules orchestrator session, once later steps
  add that) results in real Workflow/AgentTask rows in agent_tasks/workflows, executed by
  workflow_engine.py with dependency-aware parallelism — not plan_executor's own loop.
- assign_to correctly resolves to account_id via the role-aware pool.
- A plan dispatched this way is visible in the same places a workflow_parallel.json-driven
  run already is: agent_tasks rows, session_activities rows, dashboard task views.
- get_jules_key() and poll_session_status() are gone, or a clear, documented reason exists
  for keeping either one.
```

---

## Step 5 — Wake-up loop: status relay, mid-task questions, fail-fast fix

```
Give the standing orchestrator session visibility into what its dispatched tasks are doing,
without stopping unrelated work every time one thing fails.

CONTEXT
clients/jules.py already implements send_message(session_id, prompt), calling
POST /sessions/{id}:sendMessage — the client-level capability exists. What's missing is
anything that calls it: neither coordinator.py's _poll_session nor session_runner.py's
_poll_until_done ever does, both being one-shot "create, poll to a terminal state, return"
loops. There is currently no mechanism for a standing session to be told anything after it
starts, not because the API wrapper is missing, but because nothing in the polling logic
reaches for it.

workflow_engine.py's run() cancels every other running task in the workflow the moment any
single task reaches FAILED — full workflow-wide cancellation, no distinction between a
failure that actually blocks a sibling and one that doesn't.

session_runner.py's _store_activity() always writes raw_data: {} — the schema has the column,
nothing populates it, so anything reading activity content back from the DB later gets
nothing useful.

system_prompts.py's JULES_QUESTION_HANDLER describes answering a worker's mid-task question
via the ai_providers pool — Step 4 confirmed the actual call site: plan_executor.py's
poll_session_status() calls _answer_jules_question() for exactly this, and Step 4 retires it
as part of retiring System B. What's left for this step is making sure the surviving,
consolidated polling engine (Step 13) handles this state going forward instead of leaving a
gap where nothing does.

REQUIREMENTS
- Change workflow_engine.py's failure handling from workflow-wide cancellation to
  dependency-scoped cancellation: when a task reaches FAILED, cancel only tasks that
  transitively depend on it, not every running task in the workflow.
- Add a notify_orchestrator() call, fired once per state transition (not once per poll tick),
  when a tracked task reaches COMPLETED, FAILED, or needs input. Hook this into
  coordinator.py's _poll_session for DAG-run tasks and confirm whether the standing
  orchestrator's own session is driven through session_runner.py's _poll_until_done or a
  separate path, and hook there too. Include task id/description, resulting status, PR URL if
  any, and a short summary — not the full diff.
- Call the existing JulesClient.send_message(session_id, prompt) to deliver the digest above
  to the standing orchestrator's session id — no new client method needed.
- Route a worker session reaching AWAITING_USER_FEEDBACK to the standing orchestrator via the
  same sendMessage mechanism, and relay the orchestrator's answer back to the worker session
  via sendMessage on the worker's session id. This replaces _answer_jules_question(), which
  Step 4 already removes as part of retiring System B — nothing extra to retire here, just
  make sure this state is actually handled once that function is gone, so there's no gap
  between "the old path is deleted" and "the new path exists."
- Fix _store_activity() in session_runner.py to actually populate raw_data with the real
  activity content instead of {}. Step 6's QA-verdict parsing and Step 7's audit trail both
  need this.
- Persist which orchestrator session is responsible for which dispatched task — new state,
  inspect context_store.py's current interface and extend it there.

CONSTRAINTS
- The relay makes no decisions from digest content — it only delivers it and relays the
  reply. Whatever happens next is the orchestrator's call.
- Preserve existing single-task polling behavior exactly when there's no standing orchestrator
  to notify (the static workflow_parallel.json CLI path) — notification is additive.

ACCEPTANCE CRITERIA
- A task with two independent siblings and one dependent: failing one sibling cancels only
  the dependent, not the independent sibling.
- Completing a tracked task fires exactly one sendMessage to the correct orchestrator session;
  two rapid transitions don't duplicate it.
- A worker session entering AWAITING_USER_FEEDBACK results in a message to the orchestrator
  and, once answered, a sendMessage back to the worker — no ai_providers call in that path.
- A newly stored session_activities row's raw_data contains the real activity payload, not {}.
```

---

## Step 6 — QA gate

```
Add a mandatory, pre-merge, report-only QA review using a dedicated qa-role Jules account,
and fix the merge check it needs to rely on.

CONTEXT
auto_merge.py's _wait_for_checks() never actually blocks a merge: on failed or timed-out
checks it logs a warning and returns normally, and merge_when_ready() then merges regardless.
The "merges after CI passes" behavior described in the README isn't what the code does today.

Separately, system_prompts.py already has REVIEW_SESSION_PROMPT — an existing "final
reviewer" prompt that runs after agent work is merged, and is explicitly told to fix import
errors and type mismatches, not just report them. That's a different job than a strict,
pre-merge, never-fixes-anything QA gate. Recommendation: have the new QA role supersede
REVIEW_SESSION_PROMPT's current usage rather than run both — a reviewer allowed to silently
patch things post-merge undercuts the point of a strict pre-merge gate. If you want to keep a
separate post-merge integration pass too, leave REVIEW_SESSION_PROMPT's call site alone and
note that explicitly in the PR description instead of removing it.

REQUIREMENTS
- Fix _wait_for_checks() / merge_when_ready() in auto_merge.py so failed or timed-out checks
  actually prevent the merge: return a result indicating pass/fail/timeout instead of always
  falling through, and have merge_when_ready() return MergeResult(merged=False, ...) —
  matching its existing pattern for the "already merged" case — instead of calling
  merge_pull_request regardless.
- When a worker task completes with a PR (detected via Step 5), dispatch a QA session on an
  available qa-role account, sourceContext pointed at the PR's head branch, automationMode
  unset. Pass the task's exit_criteria field into the QA prompt explicitly.
- Save the file below as prompts/qa_reviewer.md and load it as this session's prompt,
  interpolating {exit_criteria} and {task_description} the same way JULES_MASTER_PROMPT's
  placeholders already get filled elsewhere:

  -----BEGIN prompts/qa_reviewer.md-----
  <identity>
  You are the QA reviewer for a pull request produced by another AI coding agent on this
  project. You did not write this code and have no stake in it being merged — your only job
  is to find every legitimate reason it should NOT ship yet.
  </identity>

  <context>
  <exit_criteria>{exit_criteria}</exit_criteria>
  <original_task>{task_description}</original_task>
  </context>

  <constraints>
  <rule>Do not fix anything. Do not write or modify code, even trivial typos.</rule>
  <rule>Do not open a PR. Your output is a verdict, nothing else.</rule>
  <rule>Never use emojis in your responses.</rule>
  </constraints>

  <review_checklist>
  <item>Check the PR against exit_criteria first, specifically and literally. Failing this is
  a blocking issue on its own.</item>
  <item>Run the existing test suite. A pass alone isn't enough — check whether the new code
  paths actually have coverage, or existing tests just didn't touch them.</item>
  <item>Look for what isn't there: missing error handling, unhandled edge cases, race
  conditions, missing input validation, silent failure modes.</item>
  <item>Look for what conflicts: does this change contradict, duplicate, or destabilize
  something elsewhere in the codebase? Check callers of anything changed.</item>
  <item>Security and secrets: this project handles API keys and tokens — check for anything
  logged, committed, or passed somewhere it shouldn't be.</item>
  <item>Be skeptical of anything that looks too clean. If a hard problem was solved in
  suspiciously few lines, check whether it was actually solved or just no longer triggers the
  specific case in the prompt.</item>
  </review_checklist>

  <output_format>
  Be specific. "Looks fine" is not a review. Every issue needs a file, a reason, and — if
  you're not certain it's actually a problem — say so plainly rather than padding the list to
  look thorough.

  End your final message with exactly this block and nothing after it:

  {
    "verdict": "approve" or "reject",
    "blocking_issues": [
      { "file": "path/to/file", "issue": "description", "severity": "blocking" or "minor" }
    ],
    "summary": "one or two sentences"
  }

  Use "reject" if there is at least one "blocking" issue. Minor issues alone don't block, but
  list them anyway.
  </output_format>
  -----END prompts/qa_reviewer.md-----

- Parse the QA session's final message for that verdict block directly during polling (the
  same point _log_activity already reads activity.agent_messaged.agent_message), rather than
  round-tripping through the DB.
- Change merge eligibility to "CI green (from the auto_merge.py fix above) AND qa_verdict ==
  approve". On reject, don't merge — send the blocking issues to the responsible orchestrator
  session via Step 5's sendMessage mechanism.
- Look the QA verdict up from persisted state (keyed by PR or task identity) inside
  merge_when_ready() itself, rather than accepting it as an optional parameter from the
  caller. mcp/server.py's jat_merge_pr tool calls merge_when_ready() directly, bypassing the
  wake-up-loop path entirely — if the QA check only fires when a caller remembers to pass a
  verdict in, that tool becomes a way to skip QA by accident. Looking it up internally means
  every call path gets the same gate with no way to forget it.
- A QA task's TaskStatus must be COMPLETED regardless of verdict — COMPLETED means "the QA
  agent finished its review," not "the PR passed." Never set it to FAILED for a reject
  verdict: workflow_engine.py treats FAILED as a cancellation trigger, and a normal review
  outcome shouldn't route through the failure path at all. Store the verdict in context, not
  in status.

CONSTRAINTS
- QA sessions never write code and never merge anything — only produce a verdict.
- The CI-check fix and the QA gate are both hard-coded policy in auto_merge.py, not something
  the orchestrator can opt out of.

ACCEPTANCE CRITERIA
- A PR with a failing or timed-out check no longer merges — test this against the current
  soft-fail behavior specifically, to confirm it's actually fixed and not just bypassed by
  the new QA check.
- A worker PR with passing CI does not merge until a QA session returns "approve".
- A "reject" verdict blocks the merge, reaches the orchestrator with the specific blocking
  issues, and leaves the QA task's own status as COMPLETED, not FAILED.
- Add test doubles for both verdicts plus a failed-CI-check case, and confirm auto_merge.py
  handles all three correctly.
- Calling merge_when_ready() the way mcp/server.py's jat_merge_pr does — directly, no verdict
  passed in — is still blocked on a pending or reject verdict, confirming there's no bypass.
```

---

## Step 7 — requirePlanApproval + audit trail

```
Give a human a review gate on orchestration decisions specifically, and make the
orchestrator's decision history visible without building new UI.

CONTEXT
clients/jules.py's create_session() already accepts require_plan_approval: bool = False, and
approve_plan(session_id) is already implemented. Both client-level pieces exist. The actual
gap is that neither coordinator.py's _poll_session nor session_runner.py's _poll_until_done
handle AWAITING_PLAN_APPROVAL as a state — anything outside {COMPLETED, FAILED, PAUSED} just
keeps polling until SESSION_TIMEOUT (30 minutes) and returns a timeout result. Setting
require_plan_approval=True without also fixing this means the orchestrator session would
silently hang until timeout instead of ever actually waiting for approval — the polling loop,
not the client, is what needs work here. Separately, note approve_plan() isn't wrapped in
clients/jules.py's retry decorator the way most other methods are — a transient 5xx on
approval would fail outright rather than retry; worth fixing alongside this while you're in
that file.

More important than either of those: plan_executor.py's poll_session_status() — being
retired in Step 4 — currently auto-approves every AWAITING_PLAN_APPROVAL unconditionally,
with no human involved at all. If Step 4 hasn't actually landed by the time this step runs,
this gate does nothing for anything dispatched through that path — it gets rubber-stamped
before a human ever sees it, silently. Confirm Step 4 is done first, or this step will appear
to work in testing while providing no real protection in the path that matters most.

REQUIREMENTS
- When creating the standing orchestrator session, pass require_plan_approval=True — this
  parameter already exists on create_session(), no client change needed.
- Add explicit handling for AWAITING_PLAN_APPROVAL in both polling loops: surface it (to the
  dashboard's existing session-state display, and/or via Step 5's notification mechanism)
  rather than silently polling to timeout, and call the existing approve_plan(session_id) on
  human approval so the session actually resumes instead of timing out regardless.
- Add or extend an endpoint (inspect src/cli.py and the dashboard's API layer) returning the
  orchestration decision history for a project — reuse whichever mechanism Step 4 ended up
  using (context.xml history in the target repo, or conversation_messages history).
- Surface a pending-approval count in the existing dashboard session-state display.

CONSTRAINTS
- No new dashboard page or visual design — expose the data, keep presentation minimal.

ACCEPTANCE CRITERIA
- An orchestrator session's first plan requires explicit approval before it can dispatch
  anything, and actually resumes on approval rather than timing out.
- Orchestration decision history for a given project is retrievable via an API call.
```

---

## Step 8 — Recursive dispatch to sub-orchestrators (stretch)

```
Let assign_to resolve to another orchestrator-role account, not just a worker, so a top-level
orchestrator can delegate "coordinate this subtree" instead of only "write this code."

CONTEXT
models/workflow.py's AgentTask already has parent_task_id: UUID | None — the tree-structure
primitive this needs already exists. This step is mostly dispatch behavior, not schema.

REQUIREMENTS
- In directive_parser.py / account_pool.py (Steps 3-4), allow assign_to to resolve to an
  orchestrator-role account. When it does, set the new task's parent_task_id to the
  delegating orchestrator's own task/session reference, and frame its prompt as a delegation
  ("you are responsible for this subtree of the goal: ...") rather than a coding task. It
  becomes a new standing orchestrator in its own right — Step 5's notification and Step 6's
  QA gate apply to whatever it eventually produces, same as any other branch.
- Guard against runaway recursion: cap delegation depth with a config value (default
  conservative, e.g. 2) and refuse to resolve assign_to to an orchestrator account beyond
  that depth.

CONSTRAINTS
- Stretch step — don't let it block or complicate Steps 2-7. Build it as an additive
  capability that's off by default (max_delegation_depth: 0 disables it entirely).

ACCEPTANCE CRITERIA
- A task whose assign_to targets an orchestrator account results in a nested standing
  session with parent_task_id correctly set, tracked the same way top-level tasks are.
- max_delegation_depth: 0 fully disables the behavior with no other code path changes
  required.
```

---

## Step 9 — Backpressure-aware dispatch

```
Stop treating account-pool exhaustion as a task failure. Dispatch only as many ready tasks as
there's real capacity for, and back off gracefully when capacity is temporarily unavailable.

CONTEXT
AccountPool.acquire() raises AccountPoolExhausted when no eligible account has capacity.
coordinator.py's run_task() doesn't handle this exception specifically — it falls into the
general except-all block that marks the task FAILED. Separately, workflow_engine.py's run()
spawns an asyncio.create_task() for every ready task at once, with no check against actual
account capacity first. Combined, this means: any workflow with more tasks becoming ready
simultaneously than there's account concurrency for will have some of those tasks fail
outright — not wait, not queue, fail — purely from dispatch timing, not from anything wrong
with the task itself. After Step 5's fix, a FAILED task cancels everything that depends on
it, so a transient capacity crunch can cascade into cancelled downstream work that had
nothing to do with the actual shortage.

REQUIREMENTS
- In workflow_engine.py's run(), before spawning tasks for the current batch of ready tasks,
  check available capacity (matching each task's required role/source) against the pool.
  Only start as many concurrent asyncio tasks as there's real room for; hold the rest in the
  ready set rather than spawning them to fail. Re-check as running tasks complete and free up
  capacity — the existing FIRST_COMPLETED wait loop is the natural point to re-evaluate.
- As a backstop for the inherent race between checking capacity and actually acquiring it
  (another dispatcher could take the last slot in between), have coordinator.py's run_task()
  catch AccountPoolExhausted specifically — not let it fall into the general except-all — and
  retry with a short backoff a small, bounded number of times before treating it as a real
  failure.
- Distinguish these two failure modes clearly in whatever gets logged/surfaced to the
  orchestrator (Step 5's notification mechanism): "waiting on capacity" is not the same event
  as "this task's execution failed," and the orchestrator (or a human) shouldn't have to
  infer which one happened from a generic error string.

CONSTRAINTS
- Don't change how tasks get selected as "ready" (dependency resolution stays as-is) — only
  change how many of the ready set actually get dispatched at once.
- Keep the bounded-retry count and backoff small enough that a genuinely exhausted pool (all
  accounts near their daily cap, not just momentarily busy) still surfaces as a real,
  actionable signal rather than retrying silently for a long time.

ACCEPTANCE CRITERIA
- A workflow with more ready tasks than available account concurrency dispatches only as many
  as there's capacity for, and dispatches the rest as capacity frees up — none of them fail
  due to pool exhaustion alone.
- A task that fails for an actual execution reason (not pool exhaustion) still fails and still
  cancels its dependents, unchanged from Step 5's behavior.
- Add a test that oversubscribes the pool relative to ready tasks and confirms zero spurious
  failures, only staggered dispatch.
```

---

## Step 10 — SQLite write-concurrency tuning

```
Configure the local database from Step 2 for concurrent write access instead of leaving it on
SQLite's default journal mode.

CONTEXT
Once Step 2 lands, the orchestrator, every worker session's poll loop, QA sessions, and the
wake-up loop's status writes all read and write the same local SQLite file concurrently —
session_activities rows get written on roughly every 15-second poll tick per active session,
on top of task/workflow status updates. SQLite's default rollback-journal mode serializes all
writers; under this project's actual concurrency (a handful of simultaneous sessions, not
thousands), that may not be a real bottleneck yet, but it's cheap to fix now and expensive to
diagnose later as a source of intermittent "database is locked" errors once usage grows.

REQUIREMENTS
- On the local DB connection(s) from Step 2's local_db.py, set:
    PRAGMA journal_mode=WAL;
    PRAGMA busy_timeout=5000;
  (or a similarly reasoned timeout — pick a value and document why) so concurrent writers
  queue briefly instead of raising immediately on contention, and readers aren't blocked by
  writers.
- Inspect whether local_db.py currently opens one connection per caller/request or shares a
  single connection/pool. If it's per-caller with a high potential concurrent-connection
  count, consider whether a bounded connection pool or a single serialized writer queue fits
  this codebase's existing async patterns better — pick one, don't leave it ad hoc.
- Add indexes appropriate to the actual query patterns in coordinator.py and session_runner.py
  (e.g., agent_tasks by workflow_id and by status, session_activities by task_id and
  session_id) if Step 2's schema translation didn't already carry these over from
  supabase/schema.sql's original indexes — inspect the translated schema to confirm what
  already exists before adding duplicates.

CONSTRAINTS
- This is a configuration and indexing pass, not a schema redesign — don't change table
  shapes here.

ACCEPTANCE CRITERIA
- WAL mode is confirmed active on the local database file.
- A test that performs concurrent writes from multiple simulated sessions (e.g., several
  session_activities upserts firing at once) completes without "database is locked" errors.
```

---

## Step 11 — Capacity-aware account routing

```
Route worker/QA dispatch toward accounts with the most remaining daily budget, not just the
fewest currently-active sessions, so accounts don't hit their daily cap unevenly while
same-tier siblings sit underused.

CONTEXT
AccountPool.acquire() currently sorts eligible accounts by active_sessions ascending only:

    eligible.sort(key=lambda a: a.active_sessions)

This spreads concurrent load well, but ignores daily_tasks_used entirely. Two accounts on the
same plan tier with the same active_sessions count get treated identically even if one is at
2 of its 15 daily tasks and the other is at 14 of 15 — the second will hit
AccountPoolExhausted for the rest of the day well before the first does, and nothing about
today's sort order avoids steering load toward it.

REQUIREMENTS
- Change the sort key to weigh both dimensions — for example, sort primarily by remaining
  daily budget (daily_task_limit - daily_tasks_used, using the same PLAN_LIMITS this file
  already defines) descending, with active_sessions ascending as the tiebreaker, or a
  combined score if that reads more clearly in context. Pick one, and comment why.
- This applies to both the source-matched and fallback-to-full-pool branches of acquire(), and
  to the role filter added in Step 3 — the ordering logic is shared across all of them.

CONSTRAINTS
- Don't change has_capacity's definition or the daily-reset logic — only the ordering used to
  pick among already-eligible accounts.
- Preserve existing behavior when all eligible accounts have equal remaining budget — should
  reduce to the current active_sessions-based ordering in that case, not introduce
  nondeterminism.

ACCEPTANCE CRITERIA
- Given two same-tier eligible accounts with equal active_sessions but different
  daily_tasks_used, acquire() prefers the one with more remaining daily budget.
- Existing tests covering the current least-active-sessions behavior still pass where
  daily_tasks_used is equal across candidates.
```

---

## Step 12 — Query pattern fixes: context_store.py and tracker.py

```
Fix two query patterns that don't scale with the data they're already accumulating: an N+1
select loop in context_store.py, and a fetch-everything-then-sort-in-Python pattern in
tracker.py.

CONTEXT
context_store.py's get_dependency_context() loops over each dependency task ID and issues a
separate select() call per ID:

    async def get_dependency_context(self, dep_task_ids: list[UUID]) -> list[dict]:
        results = []
        for tid in dep_task_ids:
            rows = await self._db.select("context_messages", filters={"task_id": str(tid)})
            if rows:
                results.append(rows[0].get("context", {}))
        return results

For a task with several dependencies, this is one query per dependency instead of one query
total. coordinator.py calls this on every task that has dependencies, so it scales with both
the size of the dependency graph and how often tasks run.

tracker.py's get_recent_activities() fetches the entire session_activities table on every
call, with no filter, then sorts and slices in Python:

    async def get_recent_activities(self, limit: int = 50) -> list[dict]:
        rows = await self._db.select("session_activities")
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        ...
        return rows[:limit]

session_activities grows continuously (a row roughly every 15-second poll tick per active
session), so this gets more expensive every day the system runs, for a query that's really
just "give me the most recent 50 rows."

REQUIREMENTS
- Change get_dependency_context() to a single query across all dependency IDs (an IN clause
  or equivalent — extend local_db.py's select() to accept a list of values for a filter
  column if it doesn't already) instead of one query per ID.
- This depends on Step 2's fix to context_messages' upsert conflict target and row ordering —
  confirm that landed correctly first; get_dependency_context (and the loop it replaces) both
  implicitly assume "one row per task_id, and it's the current one."
- Change get_recent_activities() to push ordering and limit into the query itself (ORDER BY
  created_at DESC LIMIT n) instead of fetching the full table and sorting in Python. This
  needs an index on session_activities.created_at to actually be fast — check whether Step
  10's indexing pass already added one before adding a duplicate.

CONSTRAINTS
- Keep both methods' external signatures and return shapes unchanged — this is a query
  efficiency fix, not an interface change for callers in coordinator.py or the dashboard.

ACCEPTANCE CRITERIA
- get_dependency_context issues one query regardless of how many dependency IDs it's given —
  verify with a test asserting call count, not just correct results.
- get_recent_activities returns the same results as before against a small dataset, and a
  test with a large session_activities table (a few thousand rows) confirms it no longer
  loads the full table into memory.
```

---

## Step 13 — Consolidate session polling into one shared engine

```
Replace coordinator.py's _poll_session and session_runner.py's _poll_until_done — two
separate implementations of the same "poll a session to a terminal state" loop — with one
shared engine, and give it adaptive backoff instead of a fixed interval.

CONTEXT
Both loops do fundamentally the same thing: call get_session() and list_activities() on a
timer, store new activities, and return once the session reaches a terminal state. They
differ in interval (coordinator.py polls every 30 seconds, session_runner.py every 15) for no
stated reason, and any fix has to be applied twice — Steps 5 and 7 both already have to say
"hook this into coordinator.py's _poll_session... and confirm whether session_runner.py's
_poll_until_done needs the same change" because there are genuinely two places to change.

mcp/server.py's jat_run_session tool was a candidate for a third independent implementation,
but it isn't — it calls core.session_runner.run_session() directly, so it's already covered
by whatever this step does to session_runner.py.

plan_executor.py's poll_session_status() is a real fourth one, but it isn't being folded in
here — Step 4 retires it entirely as part of retiring System B's execution machinery. If
Step 4 hasn't landed yet when this step runs, confirm that first: consolidating two loops
while a fourth, soon-to-be-deleted one still runs independently just adds a third thing to
keep in sync temporarily, for no benefit.

REQUIREMENTS
- Extract the shared logic into one polling engine (e.g. src/core/session_poller.py):
  create/attach to a session, poll get_session() + list_activities(since=...) on a loop,
  store activities via whatever Step 2 landed as the local equivalent of _store_activity,
  detect terminal states (COMPLETED, FAILED, PAUSED) and AWAITING_PLAN_APPROVAL /
  AWAITING_USER_FEEDBACK (per Step 7 and Step 5's fixes), and expose hooks for "on state
  change" that both the DAG-task path (coordinator.py) and the standalone-session path
  (session_runner.py, which mcp/server.py already routes through) can register against,
  rather than each maintaining its own copy of this loop.
- Replace the fixed poll interval with adaptive backoff: start short (a few seconds) since
  many sessions finish quickly, and back off toward a capped interval (comparable to today's
  15-30s) for sessions that are clearly going to take a while, rather than polling at a flat
  rate for the entire duration regardless of how long a session has already been running.
- Once this exists, Step 5's notify_orchestrator() hook and Step 7's AWAITING_PLAN_APPROVAL
  handling should each need to be wired in one place, not two.

CONSTRAINTS
- This is a structural consolidation, not a behavior change beyond the backoff itself — every
  state transition coordinator.py and session_runner.py currently detect and act on needs to
  keep being detected and acted on exactly the same way, just from one implementation.

ACCEPTANCE CRITERIA
- coordinator.py's DAG-task execution and session_runner.py's standalone session execution
  (and therefore mcp/server.py's jat_run_session) all run through the same polling engine,
  with no behavior regressions in any of them.
- A short-lived test session (completes within the first few poll attempts) uses meaningfully
  fewer API calls under the new backoff than it would have under a flat 15s interval.
- Existing tests for both call sites pass against the consolidated engine.
```

---

## Step 14 — Reduce auto_merge.py's check-polling overhead

```
Cut the number of GitHub API calls auto_merge.py makes per merge by backing off instead of
polling at a fixed interval, and fix a retry gap on the one call that matters most.

CONTEXT
auto_merge.py's _wait_for_checks() polls list_check_runs() every CHECK_POLL_INTERVAL (30
seconds) for up to CHECK_TIMEOUT (600 seconds) — up to 20 GitHub API calls for a single
merge's check-wait, even though most of that waiting time is typically CI actually running,
not something that needs checking every 30 seconds specifically. With multiple PRs merging
around the same time (worker + QA producing PRs in parallel, per Steps 5-6), this adds up
against GitHub's per-token rate limit.

clients/github.py already has rate-limit awareness — _check_rate_limit() logs a warning when
x-ratelimit-remaining drops below 10 — so nothing needs to be built there, just used. It also
already wraps get_pull_request, list_check_runs, and list_pr_comments in a tenacity-based
retry decorator (@_retry, exponential backoff, 3 attempts) — but merge_pull_request itself
isn't decorated. That's backwards: the read-only polling calls retry automatically, but the
one call that actually matters — the merge itself — doesn't, so a transient 5xx on a fully
approved, QA-passed, CI-green PR fails outright instead of retrying.

No webhook infrastructure exists in this codebase, so switching check-detection from polling
to webhooks would be new infrastructure (a publicly reachable endpoint, signature
verification), not a small fix. Backoff is the pragmatic option here, not webhooks.

REQUIREMENTS
- Apply adaptive backoff to _wait_for_checks(), the same idea as Step 13: start with shorter
  polls, back off toward a capped interval for checks that are clearly still running, rather
  than a flat 30s for the full 10 minutes.
- Add the @_retry decorator to merge_pull_request() in clients/github.py, matching the same
  pattern already used on the other methods in that file.

CONSTRAINTS
- Don't change what counts as a passing/failing check set — only how often status gets
  checked and whether the merge call itself retries on transient failure.
- Don't build webhook infrastructure as part of this step — that's a bigger, separate
  decision if you want it later.

ACCEPTANCE CRITERIA
- A check-wait that resolves quickly (checks complete within the first poll or two) uses
  fewer API calls than today's flat-30s version would have for the same timeline.
- A check-wait that genuinely takes the full timeout window doesn't exceed today's total call
  count by more than the adaptive schedule's early, shorter polls account for.
- A simulated transient 5xx on the merge call itself now retries instead of failing outright.
```

---

## Step 15 — Fix the MCP server's per-call event loop creation

```
Stop creating and tearing down a fresh event loop on every MCP tool call, and stop blocking
the entire server on long-running tool calls.

CONTEXT
Every tool in mcp/server.py follows the same pattern: a synchronous function (not async def)
defines an inner async _run() coroutine and executes it via asyncio.run(_run()). asyncio.run()
creates a new event loop, runs the coroutine to completion, and tears the loop down — for
every single tool invocation. For most tools (jat_list_sources, jat_get_session, etc.) this is
wasteful but not damaging, since they return quickly. jat_run_session is a different story: it
calls session_runner.run_session(), which polls for up to SESSION_TIMEOUT (30 minutes). Since
that entire call happens inside one asyncio.run(), whatever process is hosting this MCP server
is occupied by that single call for up to 30 minutes. Depending on how the underlying
transport dispatches concurrent requests, that plausibly means no other tool call — including
jat_get_session or jat_list_sessions, the tools you'd actually want to use to check on
progress while a long session runs — can be served until it returns. That defeats the purpose
of having separate observability tools available during a long-running session.

REQUIREMENTS
- Convert each @mcp.tool()-decorated function to an actual async def, and await client calls
  directly instead of wrapping them in an inner _run() coroutine passed to asyncio.run().
  Confirm the installed version of FastMCP (mcp.server.fastmcp) supports async tool functions
  directly before assuming — it very likely does, but verify against what's actually pinned
  in this project rather than against general knowledge of the library.
- For jat_run_session specifically: once this is async, confirm whether long-running tool
  calls actually block other concurrent tool calls under this server's transport (stdio vs.
  SSE — inspect how mcp.run() is invoked and what transport this deploys with). If they do,
  consider whether jat_run_session should return immediately with a session id and let the
  caller poll jat_get_session separately, rather than blocking the tool call for the session's
  entire duration. That's a bigger behavioral change than the async conversion alone — treat
  it as a separate decision if the async fix by itself doesn't resolve the blocking.
- _get_jules(), _get_github(), and _get_db() currently construct a fresh client on every tool
  call and close it at the end of that single call — unlike account_pool.py's per-account
  client caching, there's no reuse across calls here. Given MCP tool calls are likely
  interactive rather than high-frequency, this is lower priority than the event-loop fix
  above — worth a look while you're in this file, not worth its own step.

CONSTRAINTS
- Don't change what each tool returns or its parameters — this is about how the call executes
  internally, not its external contract, except for the jat_run_session blocking-call decision
  above if it turns out to be necessary.

ACCEPTANCE CRITERIA
- No tool function calls asyncio.run() internally.
- With jat_run_session in flight against a long-running session, jat_get_session and
  jat_list_sessions both still return promptly when called — verify this directly with a
  concurrent test, not just code review, since it's the actual behavior in question.
```

---

## Step 16 — Cache prompt_builder.py's template reads

```
Stop re-reading rules.xml, gates.xml, anti_patterns.xml, environment.xml, and context.xml
from disk on every single session dispatch, and stop doing blocking file I/O inside an async
codebase.

CONTEXT
build_session_prompt() calls _load_template() once per enabled injection flag (inject_rules,
inject_gates, inject_anti_patterns, inject_environment, inject_context — all default to true
in config.example.json), and _load_template() does a synchronous path.read_text() every time,
with zero caching. That's up to five blocking disk reads on every worker, orchestrator, and
QA session dispatch — and build_session_prompt() is itself a plain synchronous function,
called from async code (session_runner.py), so those reads block the event loop for their
duration rather than yielding to other concurrent work. rules.xml, gates.xml, and
anti_patterns.xml have no per-call substitution at all — they're loaded and used completely
unchanged every time. environment.xml and context.xml do have per-call substitution (plan
tier, daily/concurrent usage, dependency context), but only the substitution needs to happen
per call — the template text underneath doesn't.

Also confirmed, not just suspected: build_session_prompt() imports
core.config_loader.load_config() on every call, and load_config() re-reads and re-parses
config.json from disk on every single call — no caching at all. That's a sixth redundant disk
read per dispatch in the same function, worth fixing alongside this rather than separately.

Separately: prompt_builder.py also defines build_agent_xml_prompt(), a second prompt-building
function using xml_agent_template.xml, with parameters (agent_index, total_agents,
files_scope, acceptance_criteria) that look like per-agent prompt construction for a
decomposed plan. Confirmed: plan_executor.py does not call it — create_jules_session() there
takes a raw prompt string directly, with no reference to prompt_builder.py at all, which is
itself part of why System B's sessions skip rules/gates/context injection (see Step 4). If
nothing else calls build_agent_xml_prompt() either, it may simply be dead code — worth a
quick grep before deciding whether it needs the same caching fix.

REQUIREMENTS
- Cache the raw template text for all five files in memory the first time each is loaded (a
  module-level dict keyed by filename is enough), and read from the cache on subsequent calls
  instead of hitting disk again. Substitution (for environment.xml and context.xml) still
  happens per call, against the cached template text.
- Add a way to invalidate the cache — at minimum on process restart is fine given how rarely
  these files change; a file-watch or explicit reload trigger is a nice-to-have, not required.
- Cache config_loader.load_config()'s result the same way — confirmed re-reading from disk on
  every call, not just suspected.
- Grep for build_agent_xml_prompt() across the codebase. If something calls it, apply the
  same template-caching fix there too. If nothing does, leave it alone — fixing dead code
  isn't worth the scope here.

CONSTRAINTS
- The output of build_session_prompt() for a given set of inputs must be byte-for-byte
  identical before and after this change — this is a caching fix, not a behavior change.

ACCEPTANCE CRITERIA
- Calling build_session_prompt() twice in a row with the same flags results in only one disk
  read per template file, not two.
- Output is identical to the pre-change version for the same inputs — add a test that pins
  this down explicitly.
```
