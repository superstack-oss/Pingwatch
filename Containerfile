# syntax=docker/dockerfile:1
# Podman Containerfile — keep in sync with Dockerfile.


FROM python:3.12-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /venv \
    && grep -vE '^pytest([=<>]|$)' requirements.txt > /tmp/requirements.runtime.txt \
    && /venv/bin/pip install --upgrade "pip>=26.1.2" "setuptools>=83.0.0" wheel \
    && /venv/bin/pip install --no-cache-dir -r /tmp/requirements.runtime.txt \
    && /venv/bin/pip uninstall -y pip setuptools wheel


FROM python:3.12-slim-trixie

ARG PINGWATCH_VERSION=1.2.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/venv/bin:$PATH"

LABEL org.opencontainers.image.title="Pingwatch" \
      org.opencontainers.image.description="Self-hosted uptime monitoring for NAS, storage, servers, DNS, APIs, and game servers." \
      org.opencontainers.image.url="https://superstack.in" \
      org.opencontainers.image.source="https://github.com/superstack-oss/Pingwatch" \
      org.opencontainers.image.documentation="https://github.com/superstack-oss/Pingwatch#readme" \
      org.opencontainers.image.vendor="Superstack" \
      org.opencontainers.image.version="${PINGWATCH_VERSION}"

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        iputils-ping \
        traceroute \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/local/bin/python3 -m pip uninstall -y pip setuptools wheel \
    && rm -rf /usr/local/lib/python*/ensurepip \
              /usr/local/lib/python*/site-packages/pip* \
              /usr/local/lib/python*/site-packages/setuptools* \
              /usr/local/lib/python*/site-packages/wheel* \
              /usr/local/bin/pip \
              /usr/local/bin/pip3 \
              /usr/local/bin/pip3.* \
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
