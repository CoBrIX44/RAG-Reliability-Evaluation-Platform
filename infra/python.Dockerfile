FROM ghcr.io/astral-sh/uv:0.12.2 AS uv
FROM python:3.12.13-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY packages/rag_core ./packages/rag_core
COPY services/api ./services/api
COPY services/worker ./services/worker
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev \
    && adduser --disabled-password --gecos "" --uid 10001 app \
    && mkdir -p /app/data/artifacts /app/data/models \
    && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "rag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
