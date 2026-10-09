"""Task business logic + validation. No MCP code in here."""

import functools
import logging
from collections import Counter
from collections.abc import Callable
from typing import Any, Literal, ParamSpec, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.database import session_scope
from app.errors import AppError, ErrorCode
from app.models.task import Task

log = logging.getLogger("devops_mcp")

Priority = Literal["low", "medium", "high"]
Status = Literal["pending", "in_progress", "completed"]

P = ParamSpec("P")
R = TypeVar("R")
M = TypeVar("M", bound=BaseModel)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: Priority = "medium"


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    status: Status | None = None


class TaskFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status | None = None
    priority: Priority | None = None


def _validate(model: type[M], **data: Any) -> M:
    try:
        return model(**data)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise AppError(ErrorCode.INVALID_INPUT, details, False) from None


def _db_errors(fn: Callable[P, R]) -> Callable[P, R]:
    """Translate SQLAlchemy failures into DATABASE_ERROR."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except OperationalError:
            raise AppError(ErrorCode.DATABASE_ERROR, "Database unavailable", True) from None
        except SQLAlchemyError:
            raise AppError(ErrorCode.DATABASE_ERROR, "Database error", False) from None

    return wrapper


def _get_or_404(session: Any, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise AppError(ErrorCode.INVALID_INPUT, f"Task {task_id} not found", False)
    return task


@_db_errors
def create_task(title: str, description: str = "", priority: str = "medium") -> dict[str, Any]:
    data = _validate(TaskCreate, title=title, description=description, priority=priority)
    with session_scope() as session:
        task = Task(**data.model_dump())
        session.add(task)
        session.flush()  # assigns the id
        return task.to_dict()


@_db_errors
def list_tasks(status: str | None = None, priority: str | None = None) -> list[dict[str, Any]]:
    f = _validate(TaskFilter, status=status, priority=priority)
    query = select(Task).order_by(Task.id)
    if f.status:
        query = query.where(Task.status == f.status)
    if f.priority:
        query = query.where(Task.priority == f.priority)
    with session_scope() as session:
        return [t.to_dict() for t in session.scalars(query)]


@_db_errors
def update_task(task_id: int, **fields: Any) -> dict[str, Any]:
    changes = {k: v for k, v in fields.items() if v is not None}
    if not changes:
        raise AppError(ErrorCode.INVALID_INPUT, "Provide at least one field to update", False)
    data = _validate(TaskUpdate, **changes)
    with session_scope() as session:
        task = _get_or_404(session, task_id)
        for name, value in data.model_dump(exclude_none=True).items():
            setattr(task, name, value)
        return task.to_dict()


@_db_errors
def get_task(task_id: int) -> dict[str, Any]:
    with session_scope() as session:
        return _get_or_404(session, task_id).to_dict()


@_db_errors
def delete_task(task_id: int) -> None:
    with session_scope() as session:
        session.delete(_get_or_404(session, task_id))


def summary() -> dict[str, Any]:
    tasks = list_tasks()
    return {"total": len(tasks), "by_status": dict(Counter(t["status"] for t in tasks))}
