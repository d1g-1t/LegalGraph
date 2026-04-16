FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && \
    pip install --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r legalops && useradd -r -g legalops legalops

COPY --from=builder /install /usr/local
COPY src/ ./src/
COPY alembic.ini ./

RUN chown -R legalops:legalops /app
USER legalops

EXPOSE 8079

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8079/api/v1/health/live || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8079", "--workers", "2"]
