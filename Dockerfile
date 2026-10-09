FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Secrets are NOT baked in: they arrive as environment variables at runtime.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app.server"]
