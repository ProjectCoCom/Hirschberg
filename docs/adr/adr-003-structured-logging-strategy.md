# ADR-003: Structured Logging Strategy

## Status
Accepted

## Context
The distributed, async nature of the application makes debugging challenging. Traditional unstructured logs make it difficult to correlate events across async operations, trace request flows, and diagnose issues in production.

## Decision
Adopt `structlog` for structured logging throughout the application with the following patterns:

1. **Logger Initialization**: Each module creates its logger via `structlog.get_logger()`
2. **Context Binding**: Bind relevant context (request_id, session_id, workflow_id) at operation start
3. **Event Naming**: Use snake_case event names that describe what happened (e.g., `request_started`, `task_completed`)
4. **Structured Data**: Log key-value pairs for all relevant context rather than embedding in message strings
5. **Log Levels**: 
   - `debug`: Detailed technical information for development
   - `info`: Normal operational events
   - `warning`: Unexpected but handled situations
   - `error`: Error conditions that require attention
   - `critical`: System-level failures

## Consequences

### Positive
- **Searchability**: Structured data enables efficient log querying and filtering
- **Correlation**: Request IDs enable tracing across async boundaries
- **Consistency**: Standardized format across all components
- **Integration**: Compatible with modern log aggregation systems (ELK, Splunk, etc.)

### Negative
- **Verbosity**: More boilerplate code for logging statements
- **Performance**: Slight overhead from JSON serialization (mitigated by async I/O)

### Mitigation
- Create helper functions for common logging patterns
- Use log sampling for high-volume debug logs in production
- Regular review of log output to ensure signal-to-noise ratio

## Implementation Example
```python
import structlog

log = structlog.get_logger()

async def process_request(request_id: str):
    log = log.bind(request_id=request_id)
    await log.ainfo("request_started", method="POST", path="/api/v1")
    try:
        # processing logic
        await log.ainfo("request_completed", duration_ms=duration)
    except Exception as e:
        await log.aerror("request_failed", error=str(e), exc_info=True)
        raise
```

## References
- structlog documentation
- Twelve-Factor App logging principles
- Google Cloud Logging best practices
