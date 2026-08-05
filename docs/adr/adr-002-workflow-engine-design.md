# ADR-002: Workflow Engine Design

## Status
Accepted

## Context
The application needs to orchestrate complex multi-agent workflows with parallel task execution, dependency management, and integration branching. Workflows must support DAG (Directed Acyclic Graph) structures where tasks can have multiple dependencies and execute in parallel when possible.

## Decision
Implement a `WorkflowEngine` class that:
- Validates workflow DAGs for cycles and missing dependencies before execution
- Manages parallel task execution using `asyncio.gather()` for independent tasks
- Tracks task status and propagates failures appropriately
- Coordinates with `AgentCoordinator` for agent session management
- Integrates with `ContextStore` for state persistence
- Supports blocking conditions (e.g., integrator review) that pause workflow execution

## Consequences

### Positive
- **Flexibility**: Supports arbitrary DAG structures for complex workflows
- **Parallelism**: Maximizes throughput by executing independent tasks concurrently
- **Reliability**: Validation prevents invalid workflows from executing
- **Observability**: Clear task status tracking enables monitoring and debugging

### Negative
- **Complexity**: DAG validation and parallel execution add implementation complexity
- **State Management**: Requires careful coordination of shared state across async tasks
- **Error Handling**: Failure propagation in parallel workflows requires thoughtful design

### Mitigation
- Comprehensive unit tests for cycle detection and dependency validation
- Use of immutable task models to prevent race conditions
- Structured logging at each workflow state transition
- Clear separation between workflow orchestration and task execution

## References
- WorkflowEngine implementation in `src/core/workflow_engine.py`
- DAG topological sort algorithms
- asyncio.gather() documentation
