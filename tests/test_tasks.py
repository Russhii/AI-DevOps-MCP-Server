import pytest

from app.errors import AppError, ErrorCode
from app.services import task_service as svc


def test_crud_roundtrip():
    task = svc.create_task("Deploy API", "to staging", "high")
    assert task["status"] == "pending" and task["priority"] == "high"

    updated = svc.update_task(task["id"], status="in_progress")
    assert updated["status"] == "in_progress"

    assert [t["id"] for t in svc.list_tasks(status="in_progress")] == [task["id"]]
    assert svc.list_tasks(status="completed") == []

    svc.delete_task(task["id"])
    assert svc.list_tasks() == []


@pytest.mark.parametrize(
    "kwargs",
    [{"title": ""}, {"title": "x", "priority": "urgent"}, {"title": "x" * 201}],
)
def test_create_validation(kwargs):
    with pytest.raises(AppError) as exc:
        svc.create_task(**kwargs)
    assert exc.value.code == ErrorCode.INVALID_INPUT


def test_update_validation_and_missing():
    task = svc.create_task("a")
    with pytest.raises(AppError):
        svc.update_task(task["id"], status="done")
    with pytest.raises(AppError):
        svc.update_task(task["id"])  # nothing to change
    with pytest.raises(AppError):
        svc.update_task(999, title="x")  # not found


def test_filter_validation():
    with pytest.raises(AppError):
        svc.list_tasks(status="nope")
