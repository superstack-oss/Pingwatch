# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /venv \
    && grep -vE '^pytest([=<>]|$)' requirements.txt > /tmp/requirements.runtime.txt \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r /tmp/requirements.runtime.txt


FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iputils-ping \
        traceroute \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 pingwatch \
    && useradd --create-home --uid 1000 --gid pingwatch --shell /usr/sbin/nologin pingwatch

COPY --from=builder --chown=pingwatch:pingwatch /venv /venv
COPY --chown=pingwatch:pingwatch app ./app
COPY --chown=pingwatch:pingwatch templates ./templates
COPY --chown=pingwatch:pingwatch static ./static

RUN mkdir -p /app/data/incident-attachments \
    && chown -R pingwatch:pingwatch /app/data

USER pingwatch

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# Single worker: the in-process sweep must not be duplicated.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "20"]
