# Build from repo root: docker build -f GuidePostPythonContainer/Dockerfile .
# Context must be repo root so both GuidePostPythonContainer and ui are available.

# ---- Python dependency builder ----
FROM python:3.11-slim AS builder

ARG APP_DIR=/app
WORKDIR ${APP_DIR}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH=/root/.local/bin:$PATH

COPY GuidePostPythonContainer/pyproject.toml GuidePostPythonContainer/poetry.lock ./
RUN poetry install --no-root --no-ansi

ENV PATH=${APP_DIR}/.venv/bin:$PATH

RUN python -m nltk.downloader vader_lexicon -d /usr/local/share/nltk_data

COPY GuidePostPythonContainer/src ./src
COPY GuidePostPythonContainer/chunk_texts ./chunk_texts

# ---- UI build ----
FROM node:20-alpine AS ui-builder
WORKDIR /ui
COPY ui/package.json ./
RUN npm install
COPY ui/ ./
RUN npm run build

# ---- Runtime (production) ----
FROM python:3.11-slim AS runtime

ARG APP_DIR=/app
WORKDIR ${APP_DIR}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=${APP_DIR}/.venv/bin:$PATH \
    NLTK_DATA=/usr/local/share/nltk_data

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder ${APP_DIR}/.venv ${APP_DIR}/.venv
COPY --from=builder /usr/local/share/nltk_data /usr/local/share/nltk_data
COPY --from=builder ${APP_DIR}/src ${APP_DIR}/src
COPY --from=builder ${APP_DIR}/chunk_texts ${APP_DIR}/chunk_texts
COPY --from=ui-builder /ui/dist ${APP_DIR}/static

EXPOSE 8000

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
