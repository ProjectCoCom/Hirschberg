# Hirschberg (JAT-AI Fork) - Comprehensive Audit Remediation Plan

**Generated**: 2025-08-05  
**Scope**: Backend-only remediation + frontend removal  
**Goal**: Transform JAT-AI into Hirschberg core architecture ready for Theia IDE integration

---

## Executive Summary

This plan addresses all backend-related issues from the comprehensive audit report, organized into sequential phases with immediately verifiable tasks. The frontend (`dashboard/`) will be removed as it will be replaced by Eclipse Theia integration.

**Key Constraints**:
- Disk space: ~46MB available (critical constraint)
- All 60 existing tests must continue passing
- Each task must be verified before proceeding to the next

---

## Phase 0: Environment Stabilization (P0 Critical)

### Task 0.1: Fix MyPy Configuration
**File(s)**: `pyproject.toml`  
**Problem**: MyPy reports "Source file found twice under different module names" due to `packages = ["src"]` + `mypy_path = "src"`  
**Fix**: 
```toml
[tool.mypy]
python_version = "3.11"
strict = true
mypy_path = "."
explicit_package_bases = true
```
**Verify**: `python -m mypy src/` runs without the duplicate module error

### Task 0.2: Create .dockerignore for Future Containerization
**File(s)**: `.dockerignore` (new file)  
**Problem**: No exclusion rules for container builds, will bloat images  
**Fix**: Create `.dockerignore` with:
```
node_modules
__pycache__
.pytest_cache
*.pyc
.git
.env
data/*.db
```
**Verify**: File exists and contains all patterns

### Task 0.3: Add Cleanup Script
**File(s)**: `scripts/cleanup.sh` (new file)  
**Problem**: No automated cleanup for CI/CD pipelines  
**Fix**: Create shell script that removes:
- `__pycache__/` directories
- `.pytest_cache/`
- `*.pyc` files
- `data/*.db` (non-production)
**Verify**: Script runs successfully and removes target files

---

## Phase 1: Type Annotation & Linting (P0 Critical)

### Task 1.1: Run Ruff Auto-Fix on All Python Files
**File(s)**: All `.py` files in `src/`  
**Problem**: Import order violations and fixable linting issues  
**Fix**: Execute `ruff check src/ --fix`  
**Verify**: `ruff check src/` returns exit code 0

### Task 1.2: Fix Line Length Violations in chat.py
**File(s)**: `src/api/chat.py`  
**Problem**: 20+ line-length violations (>120 chars)  
**Fix**: Refactor long strings into constants or use parentheses for multi-line strings  
**Verify**: `ruff check src/api/chat.py` shows no E501 errors

### Task 1.3: Add Missing Type Annotations - High Priority Files
**File(s)**: `src/api/server.py`, `src/clients/ai_providers.py`, `src/core/context_store.py`  
**Problem**: 367 mypy errors across codebase, concentrated in these files  
**Fix**: 
- Add return type annotations to all functions
- Replace bare `dict` with `dict[str, Any]`
- Add missing imports for typing constructs
**Verify**: `python -m mypy src/api/server.py src/clients/ai_providers.py src/core/context_store.py` passes

### Task 1.4: Fix Generic Type Parameters Throughout Codebase
**File(s)**: All files with mypy errors  
**Problem**: Missing generic type parameters (`dict` → `dict[str, Any]`, `list` → `list[Any]`)  
**Fix**: Systematic replacement based on mypy output  
**Verify**: `python -m mypy src/` shows < 50 errors (down from 367)

---

## Phase 2: Error Handling & Reliability (P1 High Priority)

### Task 2.1: Replace Silent Exception Handlers in server.py
**File(s)**: `src/api/server.py`  
**Problem**: 15+ instances of bare `except Exception:` with silent failures  
**Fix**: Replace each with:
```python
except Exception as e:
    log.error("operation_failed", operation="operation_name", error=str(e))
    return None  # or re-raise as appropriate
```
**Verify**: Grep for `except Exception:` shows no instances without logging

### Task 2.2: Fix Async Resource Leaks
**File(s)**: `src/core/coordinator.py`, `src/api/server.py`  
**Problem**: Inconsistent use of async context managers for `httpx.AsyncClient`  
**Fix**: Ensure all `httpx.AsyncClient` usage follows pattern:
```python
async with httpx.AsyncClient() as client:
    # use client
```
**Verify**: Grep for `httpx.AsyncClient()` shows only `async with` patterns

### Task 2.3: Add Structured Logging to All API Endpoints
**File(s)**: All files in `src/api/`  
**Problem**: Inconsistent logging patterns  
**Fix**: Ensure every endpoint uses `structlog.get_logger()` and logs:
- Request start
- Key operations
- Errors with context
- Request completion  
**Verify**: Manual inspection of 3 random endpoints confirms pattern

### Task 2.4: Implement Request ID Tracking
**File(s)**: `src/api/server.py`, middleware  
**Problem**: No correlation IDs for debugging across async operations  
**Fix**: Add middleware that generates request ID and includes it in all log context  
**Verify**: Log output includes request_id field for API calls

---

## Phase 3: Code Architecture Improvements (P1 High Priority)

### Task 3.1: Split Monolithic server.py - Lifespan Events
**File(s)**: `src/api/server_lifespan.py` (new), `src/api/server.py`  
**Problem**: `server.py` is 878 lines handling too many concerns  
**Fix**: Extract lifespan events (startup/shutdown) into separate module  
**Verify**: Server starts successfully after refactor

### Task 3.2: Split server.py - Recovery Logic
**File(s)**: `src/api/server_recovery.py` (new), `src/api/server.py`  
**Problem**: Orphaned task recovery logic mixed with route handlers  
**Fix**: Extract recovery functions into dedicated module  
**Verify**: Recovery functionality works post-refactor

### Task 3.3: Split server.py - Prompt CRUD
**File(s)**: `src/api/prompts_api.py` (new), `src/api/server.py`  
**Problem**: Prompt management endpoints in monolithic file  
**Fix**: Extract prompt-related routes into FastAPI router  
**Verify**: All prompt endpoints respond correctly

### Task 3.4: Split server.py - Terminal Management
**File(s)**: `src/api/terminals_api.py` (new), `src/api/server.py`  
**Problem**: Terminal session endpoints in monolithic file  
**Fix**: Extract terminal routes into FastAPI router  
**Verify**: Terminal endpoints function post-refactor

### Task 3.5: Update server.py Imports After Splits
**File(s)**: `src/api/server.py`  
**Problem**: Must import and include routers from split files  
**Fix**: Add `app.include_router()` calls for each new router  
**Verify**: `python -c "from src.api import server"` succeeds

---

## Phase 4: Database Layer Improvements (P1 High Priority)

### Task 4.1: Audit Raw SQL for Injection Vulnerabilities
**File(s)**: `src/clients/local_db.py`, `src/clients/database.py`  
**Problem**: Raw SQL string concatenation  
**Fix**: Identify all instances, document findings (full SQLAlchemy migration is Phase 6)  
**Verify**: Document created listing all raw SQL locations

### Task 4.2: Add Parameterized Query Helper
**File(s)**: `src/clients/local_db.py`  
**Problem**: Some queries use string formatting  
**Fix**: Add helper method that enforces parameterized queries  
**Verify**: New helper used in at least 3 query locations

### Task 4.3: Document Migration Strategy
**File(s)**: `docs/migration-plan.md` (new)  
**Problem**: No migration framework for schema changes  
**Fix**: Create document outlining Alembic migration strategy  
**Verify**: Document exists with clear migration steps

---

## Phase 5: Configuration & Secret Management (P1 High Priority)

### Task 5.1: Move Hardcoded Values to Config
**File(s)**: `src/core/coordinator.py`, `src/clients/jules.py`, `src/api/server.py`  
**Problem**: Hardcoded values: `POLL_INTERVAL`, `SESSION_TIMEOUT`, `DEFAULT_TIMEOUT`, `timeout_minutes`  
**Fix**: Add to config system with sensible defaults  
**Verify**: Values can be overridden via environment variables

### Task 5.2: Document Key Rotation Procedure
**File(s)**: `docs/key-rotation.md` (new)  
**Problem**: No key rotation mechanism documented  
**Fix**: Create procedure document for encryption key rotation  
**Verify**: Document provides step-by-step rotation process

### Task 5.3: Add CORS Configuration
**File(s)**: `src/api/server.py`, `src/config.py`  
**Problem**: CORS set to `allow_origins=["*"]`  
**Fix**: Make configurable, default to restrictive list  
**Verify**: CORS can be configured via environment variable

---

## Phase 6: Frontend Removal (Pre-Theia Integration)

### Task 6.1: Verify Dashboard Directory Contents
**File(s)**: `dashboard/`  
**Problem**: Need to confirm what's being removed  
**Fix**: Already completed - dashboard removed during environment setup  
**Verify**: `ls dashboard/` shows directory doesn't exist ✓ DONE

### Task 6.2: Remove Dashboard References from Documentation
**File(s)**: `README.md`, `AGENTS.md`, `docs/*.md`  
**Problem**: Docs may reference frontend build/deploy commands  
**Fix**: Search and remove/update frontend references  
**Verify**: Grep for "dashboard", "pnpm", "vite" shows no build instructions

### Task 6.3: Remove Frontend Build Scripts
**File(s)**: Check `scripts/` directory  
**Problem**: May contain frontend build scripts  
**Fix**: Remove any frontend-related scripts  
**Verify**: No scripts reference pnpm/npm/vite

### Task 6.4: Update pyproject.toml if Needed
**File(s)**: `pyproject.toml`  
**Problem**: May have frontend-related metadata  
**Fix**: Review and clean up if needed  
**Verify**: File contains only backend configuration

---

## Phase 7: CLI Development for Testing (Replacement for Frontend)

### Task 7.1: Audit Existing CLI Commands
**File(s)**: `src/cli.py`, `src/cli_ai.py`  
**Problem**: Need to understand current CLI capabilities  
**Fix**: Document existing commands  
**Verify**: List of all available CLI commands created

### Task 7.2: Add Session Listing Command
**File(s)**: `src/cli.py`  
**Problem**: Need terminal-based way to view sessions  
**Fix**: Add `jat session list` command  
**Verify**: Command displays active sessions

### Task 7.3: Add Session Detail Command
**File(s)**: `src/cli.py`  
**Problem**: Need to inspect individual sessions  
**Fix**: Add `jat session show <id>` command  
**Verify**: Command displays session details

### Task 7.4: Add Prompt Management Commands
**File(s)**: `src/cli.py`  
**Problem**: Need CLI access to prompt CRUD  
**Fix**: Add `jat prompt list/create/update/delete` commands  
**Verify**: All CRUD operations work via CLI

### Task 7.5: Add Account Pool Status Command
**File(s)**: `src/cli.py`  
**Problem**: Need to monitor Jules account availability  
**Fix**: Add `jat accounts status` command  
**Verify**: Shows account health/scores

### Task 7.6: Add Workflow Execution Command
**File(s)**: `src/cli.py`  
**Problem**: Need to trigger workflows from CLI  
**Fix**: Add `jat workflow run <file>` command  
**Verify**: Executes workflow and shows progress

### Task 7.7: Add Health Check Command
**File(s)**: `src/cli.py`  
**Problem**: Need quick system status check  
**Fix**: Add `jat health` command  
**Verify**: Reports database, API, and external service status

---

## Phase 8: Test Coverage Improvements (P2 Medium Priority)

### Task 8.1: Add pytest-cov Configuration
**File(s)**: `pyproject.toml`  
**Problem**: No coverage reporting configured  
**Fix**: Add coverage settings to pytest options  
**Verify**: `pytest --cov=src` produces coverage report

### Task 8.2: Set Coverage Threshold
**File(s)**: `pyproject.toml`  
**Problem**: No minimum coverage requirement  
**Fix**: Add `--cov-fail-under=80`  
**Verify**: Test run fails if coverage < 80%

### Task 8.3: Add API Endpoint Tests
**File(s)**: `tests/test_api_*.py` (new)  
**Problem**: No integration tests for API endpoints  
**Fix**: Create tests using respx for HTTP mocking  
**Verify**: At least 10 new endpoint tests pass

### Task 8.4: Add Performance Test Skeleton
**File(s)**: `tests/test_performance.py` (new)  
**Problem**: No load testing infrastructure  
**Fix**: Create basic performance test structure  
**Verify**: Test file exists with placeholder tests

---

## Phase 9: Documentation Corrections (P2 Medium Priority)

### Task 9.1: Fix exceptions.py Header
**File(s)**: `src/exceptions.py`  
**Problem**: Docstring mentions `JATException`, actual class is `JatError`  
**Fix**: Update header to match actual content  
**Verify**: Header accurately describes file

### Task 9.2: Fix ai_interface.py Header
**File(s)**: `src/core/ai_interface.py`  
**Problem**: Described as LLM interface, actually implements key vault + provider CRUD  
**Fix**: Update header to reflect actual functionality  
**Verify**: Header matches implementation

### Task 9.3: Fix state_recovery.py Header
**File(s)**: `src/core/state_recovery.py`  
**Problem**: Claims to implement recovery, logic is in `server.py`  
**Fix**: Update header or consider merging with server_recovery  
**Verify**: Header is accurate

### Task 9.4: Regenerate docs/map.json
**File(s)**: `docs/map.json`, `scripts/generate_map.py`  
**Problem**: Map may be stale after file changes  
**Fix**: Run generator script  
**Verify**: Map includes all current files

---

## Phase 10: Dependency Management (P2 Medium Priority)

### Task 10.1: Audit Current Dependencies
**File(s)**: `pyproject.toml`, `uv.lock`  
**Problem**: Mixed version pinning approach  
**Fix**: Document which dependencies need exact pins  
**Verify**: List created of loose vs pinned dependencies

### Task 10.2: Pin Production Dependencies
**File(s)**: `pyproject.toml`  
**Problem**: Some dependencies use loose constraints (`chromadb>=0.5.0`)  
**Fix**: Change to exact versions after testing compatibility  
**Verify**: All production deps have exact pins

### Task 10.3: Add Security Scanning to Dev Dependencies
**File(s)**: `pyproject.toml`  
**Problem**: No security scanning tool  
**Fix**: Add `pip-audit` or `safety` to dev dependencies  
**Verify**: Tool can be installed and run

---

## Phase 11: Observability Foundation (Future-Proofing)

### Task 11.1: Enable OpenTelemetry Tracing
**File(s)**: Core coordinator and API endpoints  
**Problem**: No distributed tracing despite OTel being installed  
**Fix**: Add basic tracing spans to key operations  
**Verify**: Traces are generated (can export to console)

### Task 11.2: Add Metrics Collection Points
**File(s)**: Key business logic locations  
**Problem**: No metrics collection  
**Fix**: Add counters/timers for important operations  
**Verify**: Metrics can be exported

### Task 11.3: Configure Structured Log Output
**File(s)**: `src/config.py`  
**Problem**: Logs may not be in optimal format for aggregation  
**Fix**: Ensure JSON output option available  
**Verify**: Can switch between human-readable and JSON formats

---

## Phase 12: Security Hardening (P2 Medium Priority)

### Task 12.1: Add Input Validation Beyond Pydantic
**File(s)**: API endpoint handlers  
**Problem**: No validation beyond Pydantic models  
**Fix**: Add custom validators for complex business rules  
**Verify**: Invalid inputs rejected with clear errors

### Task 12.2: Implement Rate Limiting
**File(s)**: `src/api/server.py` or middleware  
**Problem**: No rate limiting configured  
**Fix**: Add slowapi or similar throttling  
**Verify**: Rate limits can be configured per endpoint

### Task 12.3: Add Audit Logging Table
**File(s)**: Database schema, logging code  
**Problem**: No audit trail for sensitive operations  
**Fix**: Create immutable append-only audit log table  
**Verify**: Sensitive operations logged to audit table

### Task 12.4: Restrict CORS Origins
**File(s)**: `src/api/server.py`  
**Problem**: Currently allows all origins  
**Fix**: Default to localhost only, make configurable  
**Verify**: Cross-origin requests blocked by default

---

## Verification Checklist

Before considering this plan complete:

- [ ] All 60 original tests still pass
- [ ] MyPy runs with < 50 errors (ideally 0)
- [ ] Ruff linting passes with 0 errors
- [ ] Dashboard directory removed
- [ ] CLI provides equivalent functionality to removed frontend
- [ ] No silent exception handlers remain
- [ ] All hardcoded values moved to config
- [ ] Documentation headers are accurate
- [ ] `docs/map.json` is current
- [ ] Server starts and serves API correctly

---

## Execution Notes

1. **Sequential Execution**: Tasks within each phase should be completed in order. Phases should be executed sequentially (Phase 0 before Phase 1, etc.)

2. **Verification Required**: Each task must be verified before moving to the next. If verification fails, fix before proceeding.

3. **Test Suite Protection**: The test suite must pass after EVERY task. If a task breaks tests, fix immediately before committing.

4. **Disk Space Monitoring**: Watch disk space throughout. Run cleanup script if space drops below 100MB.

5. **Documentation Updates**: Update this plan as tasks are completed. Mark each task with:
   - ✅ COMPLETED: [date]
   - ❌ BLOCKED: [reason]
   - 🔄 IN PROGRESS: [details]

6. **Commit Strategy**: One commit per task. Commit messages should reference task number (e.g., "Task 0.1: Fix MyPy configuration")

---

## Out of Scope (Per User Request)

The following audit items are explicitly excluded from this plan:

- Frontend development/maintenance (frontend is being removed)
- Multi-tenancy implementation (Phase 18 of audit)
- Billing/Stripe integration (Phase 18)
- Complete Theia migration (future phase)
- Horizontal scaling architecture (Phase 24)
- Advanced AI provider routing (Phase 21)
- Redis caching layer (Phase 23)
- Enterprise features (SSO, RBAC, audit logs beyond basic implementation)

These items may be addressed in future planning phases once the core backend is stable and Theia integration begins.

---

## Risk Mitigation

**Risk**: Disk space exhaustion during execution  
**Mitigation**: Run cleanup script after each phase, monitor with `df -h`

**Risk**: Breaking existing functionality during refactoring  
**Mitigation**: Full test suite run after every task, manual API testing for critical paths

**Risk**: MyPy errors blocking progress  
**Mitigation**: Use `# type: ignore` sparingly with explanatory comments for non-blocking errors

**Risk**: Losing CLI functionality during frontend removal  
**Mitigation**: Develop CLI commands in parallel with frontend removal, verify equivalence

---

## Deferred Items from Phase 1 (Out of Scope for Current Pass)

The following items from Phase 1 were identified but deferred to a future remediation pass:

### Task 1.3: Add Missing Type Annotations - High Priority Files
- **Status**: DEFERRED
- **Reason**: Requires significant refactoring across the codebase (583 MyPy errors remain)
- **Files Affected**: `src/api/server.py`, `src/clients/ai_providers.py`, `src/core/context_store.py`
- **Work Required**: 
  - Add return type annotations to all functions
  - Replace bare `dict` with `dict[str, Any]`
  - Add missing imports for typing constructs
- **Verification Criteria**: `python -m mypy src/api/server.py src/clients/ai_providers.py src/core/context_store.py` passes

### Task 1.4: Fix Generic Type Parameters Throughout Codebase
- **Status**: DEFERRED  
- **Reason**: Systematic replacement requires comprehensive pass through all files with mypy errors
- **Files Affected**: All files with mypy errors
- **Work Required**: Replace `dict` → `dict[str, Any]`, `list` → `list[Any]` throughout codebase
- **Verification Criteria**: `python -m mypy src/` shows < 50 errors (down from 583)

**Note**: These type annotation tasks will be revisited after completing Phases 2-6, once the core architecture and error handling improvements are in place.

---

*This plan is machine-actionable. Each task can be executed autonomously with clear verification criteria.*
