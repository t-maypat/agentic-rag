# Loupe backend — multi-stage uv build, non-root runtime (REVAMP_PLAN §13).
# Build context is the REPO ROOT so the image mirrors the repo layout: app code
# under /repo/backend and the committed corpus/index under /repo/data. The runtime
# resolves data paths relative to the repo root (app/agent/runtime.py), so this
# layout must be preserved.

# ---- Stage 1: resolve + install dependencies into a self-contained .venv ----
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /repo/backend

# Install deps first (cached layer) using only the lock + manifest.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the app itself.
COPY backend/ /repo/backend/
RUN uv sync --frozen --no-dev

# ---- Stage 2: slim runtime image ----
FROM python:3.11-slim

RUN useradd --create-home --uid 1000 appuser

WORKDIR /repo
COPY --from=builder /repo/backend /repo/backend
COPY data/ /repo/data/

# The checkpointer + index paths live under /repo/data; make them writable.
RUN chown -R appuser:appuser /repo
USER appuser

# Put the venv on PATH (uv created it in-place at /repo/backend/.venv).
ENV PATH="/repo/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /repo/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
