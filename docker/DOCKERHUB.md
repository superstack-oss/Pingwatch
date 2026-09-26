# Pingwatch on Docker Hub

Copy this file into the Docker Hub repository **Overview** for [`superstackinc/pingwatch`](https://hub.docker.com/r/superstackinc/pingwatch).

## Short description

Self-hosted uptime monitoring for NAS, storage, servers, DNS, APIs, and game servers.

## Overview

Pingwatch is a FastAPI dashboard with a MySQL check history. This image is the **web** service only. Run it with Compose so MySQL, health checks, and ICMP capabilities are set up the same way as the project.

**Architectures:** `linux/amd64`, `linux/arm64`

**Tags**

| Tag | Meaning |
| --- | --- |
| `latest` | Latest build from `main` |
| `1.2.0` | Release matching the app version |
| `1.2` | Major.minor of that release |
| `sha-<git>` | Immutable commit image |

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/superstack-oss/Pingwatch/main/install.sh | bash -s -- --yes
```

Or pull the published image and start the stack from a checkout:

```bash
git clone https://github.com/superstack-oss/Pingwatch.git
cd Pingwatch
cp .env.example .env
# set SECRET_KEY and database passwords
export PINGWATCH_IMAGE=superstackinc/pingwatch:1.2.0
docker compose --env-file .env -f docker-compose.image.yml up -d
```

Open http://127.0.0.1:8000

| | |
| --- | --- |
| Username | `admin` |
| Password | `Password@123` |

The first sign-in forces a password change.

## What is in the image

- Python 3.12, FastAPI/uvicorn
- `app/`, `templates/`, `static/`
- `ping` and `traceroute` for host checks
- Non-root user `pingwatch` (uid 1000)
- Health check: `GET /api/health`

MySQL is **not** in this image. Use `mysql:8.4` as in `docker-compose.image.yml`.

## Environment

The same variables as [the project README](https://github.com/superstack-oss/Pingwatch#configuration). Inside Compose, `MYSQL_HOST=mysql` and `MYSQL_PORT=3306`.

Required: `SECRET_KEY`, `MYSQL_PASSWORD`.

## Source and CI

- Source: https://github.com/superstack-oss/Pingwatch
- Image build: `.github/workflows/publish-image.yml`
- Also published to GHCR: `ghcr.io/superstack-oss/pingwatch`
