# ADR-004: Pydantic Models for Data Validation

## Status
Accepted

## Context
The application handles complex data structures from multiple sources (GitHub API, AI providers, user input) that require validation, type checking, and serialization. Manual validation is error-prone and difficult to maintain.

## Decision
Use Pydantic v2 models throughout the application for:
- Request/response validation in API endpoints
- Data transfer objects between layers
- Configuration validation
- External API response parsing

## Implementation Patterns

1. **Base Models**: All models inherit from `pydantic.BaseModel`
2. **Type Annotations**: Use Python type hints for all fields
3. **Validators**: Use `@field_validator` for custom validation logic
4. **StrEnum**: Use `StrEnum` for fixed string values (status, types, etc.)
5. **Optional Fields**: Use `Optional[T]` or `T | None` for nullable fields
6. **Default Values**: Provide sensible defaults where appropriate

## Consequences

### Positive
- **Automatic Validation**: Input data validated on model instantiation
- **Type Safety**: IDE support and runtime type checking
- **Serialization**: Built-in JSON serialization/deserialization
- **Documentation**: Self-documenting data structures via type hints
- **Error Messages**: Clear validation error messages for debugging

### Negative
- **Dependency**: Additional dependency on Pydantic library
- **Performance**: Slight overhead for model instantiation (acceptable for I/O-bound app)
- **Learning Curve**: Team members unfamiliar with Pydantic need training

### Mitigation
- Pin Pydantic version to avoid breaking changes
- Use `model_config` for global configuration
- Create reusable validator functions for common patterns

## Example
```python
from pydantic import BaseModel, Field, field_validator
from enum import StrEnum

class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentTask(BaseModel):
    id: UUID
    description: str = Field(..., min_length=1, max_length=500)
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[UUID] = Field(default_factory=list)
    
    @field_validator('depends_on')
    @classmethod
    def validate_dependencies(cls, v):
        if len(v) > 10:
            raise ValueError('Too many dependencies')
        return v
```

## References
- Pydantic v2 documentation
- Python typing module documentation
- API design best practices
