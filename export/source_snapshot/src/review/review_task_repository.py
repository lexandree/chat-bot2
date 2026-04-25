"""Repository for operational review tasks."""

from __future__ import annotations

from uuid import uuid4


class ReviewTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, object]] = {}

    def save(self, task: dict[str, object]) -> dict[str, object]:
        self._tasks[str(task["review_task_id"])] = task
        return task

    def get(self, review_task_id: str) -> dict[str, object] | None:
        return self._tasks.get(review_task_id)

    def create_candidate_review_task(
        self,
        *,
        candidate_claim_id: str,
        run_id: str,
        assigned_reviewer: str = "moderator",
    ) -> dict[str, object]:
        task = {
            "review_task_id": str(uuid4()),
            "candidate_claim_id": candidate_claim_id,
            "run_id": run_id,
            "assigned_reviewer": assigned_reviewer,
            "status": "pending",
            "candidate_type": "candidate_claim",
        }
        return self.save(task)

    def create_proposition_review_task(
        self,
        *,
        proposition_candidate_id: str,
        run_id: str,
        assigned_reviewer: str = "moderator",
    ) -> dict[str, object]:
        task = {
            "review_task_id": str(uuid4()),
            "proposition_candidate_id": proposition_candidate_id,
            "run_id": run_id,
            "assigned_reviewer": assigned_reviewer,
            "status": "pending",
            "candidate_type": "proposition_candidate",
        }
        return self.save(task)

    def list_tasks(self) -> list[dict[str, object]]:
        return list(self._tasks.values())
