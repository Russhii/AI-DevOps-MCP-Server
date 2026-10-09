from sqlalchemy import select

from app.database import engine, init_db, session_scope
from app.models.task import Task

print("Using database:", engine.url)  # password is hidden automatically
try:
    init_db()
    with session_scope() as session:
        print("OK, tasks in table:", len(session.scalars(select(Task)).all()))
except Exception as exc:
    print(type(exc).__name__, "->", exc)