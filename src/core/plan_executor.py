"""
Script-level plan executor.

Responsibilities:
- Triggers serial plan run execution for manual plans.

Coupling:
- Used by legacy CLI runner.
"""


from __future__ import annotations

import json
from uuid import UUID, uuid4

from models.workflow import AgentTask, TaskStatus, Workflow, WorkflowStatus


def parse_plan(plan_json: str, repo_owner: str, repo_name: str) -> Workflow:
    """Parses plan JSON and returns a models.workflow.Workflow object.

    Translates string dependency references like "agent-1" into the UUID-based
    depends_on list once real task UUIDs are assigned.
    """
    data = json.loads(plan_json)
    tasks_raw = data.get("tasks", [])

    id_map: dict[str, UUID] = {}
    task_tuples: list[tuple[AgentTask, list[str]]] = []

    for i, t in enumerate(tasks_raw):
        task_uuid = uuid4()
        str_id = t.get("id", f"agent-{i+1}")
        id_map[str_id] = task_uuid

        prompt = t.get("description", "")
        branch_name = t.get("branch", f"jat/{str_id}")

        task = AgentTask(
            id=task_uuid,
            prompt=prompt,
            repo_owner=repo_owner,
            repo_name=repo_name,
            branch=branch_name,
            status=TaskStatus.PENDING,
            assign_to=t.get("assign_to", ""),
            prompt_id=t.get("prompt_id"),
            exit_criteria=t.get("exit_criteria", ""),
            context={},
        )
        task_tuples.append((task, t.get("dependencies", [])))

    # Resolve string dependencies into UUID depends_on lists
    for task, dep_ids in task_tuples:
        task.depends_on = [id_map[dep_id] for dep_id in dep_ids if dep_id in id_map]

    return Workflow(
        id=uuid4(),
        name=data.get("title", "Execution Plan"),
        description=data.get("description", ""),
        status=WorkflowStatus.CREATED,
        tasks=[t for t, _ in task_tuples],
        execution_mode=data.get("execution_mode", "sequential"),
    )
