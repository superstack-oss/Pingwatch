<p align="center">
  <img src="static/public/penguin-svgrepo-.svg" alt="Pingwatch" width="112" height="112">
</p>

<h1 align="center">Pingwatch</h1>

<p align="center">
  Self-hosted uptime monitoring for NAS, storage, servers, DNS, APIs, and game servers.<br>
  Know whether an endpoint is reachable, and how it has behaved over time.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/MySQL-8.x-4479A1?logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/Podman-Compose-892CA0?logo=podman&logoColor=white" alt="Podman">
  <a href="https://hub.docker.com/r/superstackinc/pingwatch"><img src="https://img.shields.io/badge/Docker%20Hub-superstackinc%2Fpingwatch-2496ED?logo=docker&logoColor=white" alt="Docker Hub"></a>
</p>

<p align="center">
  <a href="https://demo-pingwatch.superstack.in">Live demo</a>
  ·
  <a href="https://superstack.in">superstack.in</a>
  ·
  <a href="#quick-start">Quick start</a>
</p>

---

Pingwatch is a FastAPI dashboard with a MySQL check history. You add a configuration item (CI), choose a **monitor type**, and a background sweep records up/down, response time, and errors. It is not an APM, SNMP manager, or full observability suite.

**Asset type** (NAS, storage, SAN, network, server, other) is separate from **monitor type** (Ping, TCP Port, DNS, WebSocket, gRPC, Game).

## Features

- **Six monitor types** on one fleet table: Ping, TCP Port, DNS, WebSocket, gRPC health, and 100+ native game-server queries
- **Certificate and domain expiry** on HTTPS and hostname monitors, read from the live certificate and registration record
- **Uptime dashboard** with CI, status, response time, sparklines, filters, and 25 rows per page
- **Warning** when latency crosses the configured threshold (200 ms by default)
- **Device detail** with availability, last down, outages, and check history (24h / 7d / 30d)
- **Incidents** with work notes when repeated failures need a timeline
- **Alert channels** for Microsoft Teams, Slack, Discord, Telegram, WhatsApp, PagerDuty, generic webhooks, and email
- **Analytics**, **Finder** (NAS shares / storage volumes), **Archives**, and **Notifications**
- **Admin console** for devices, users, access requests, audit logs, and settings
- **CSV bulk import** and a downloadable template
- **Service mode** to pause a monitor without deleting it
- Self-hosted with Docker Compose or uvicorn on the host

## Monitor types

| Monitor | What it checks |
| --- | --- |
| **Ping** | ICMP echo request to a host or IP (default) |
| **TCP Port** | TCP handshake to a host and port (default port 443) |
| **DNS** | Lookup of a name and record type against the resolver you choose |
| **WebSocket** | HTTP 101 upgrade to a `ws://` or `wss://` endpoint |
| **gRPC** | Standard gRPC health protocol; anything but `SERVING` is down (default port 50051) |
| **Game server** | Native query for 100+ game types (A2S, Minecraft, Bedrock, GameSpy, Quake 3, FiveM, and related) |

## Certificate and domain expiry

HTTPS-style monitors (TCP 443/8443, `wss://`, and hostname Ping/DNS checks) read the **certificate the server presents** and show its expiry on the monitor detail page. There is no separate SSL product and no extra hostname list.

Because the date comes from the live handshake, a renewal that ran while the web server never reloaded still shows the old date.

Hostname monitors also look up **domain registration expiry** (RDAP) so the certificate date and the registration date live on the same page.

## Quick start

One-line install (checks the host, installs missing tools, clones this repo, starts Compose):

```bash
curl -fsSL https://raw.githubusercontent.com/superstack-oss/Pingwatch/main/install.sh | bash -s -- --yes
```

Or clone and start yourself:

```bash
git clone https://github.com/superstack-oss/Pingwatch.git
cd Pingwatch
cp .env.example .env
docker compose up --build
```

Pull the published image from Docker Hub (no local image build):

```bash
cp .env.example .env
# set SECRET_KEY and database passwords
docker compose --env-file .env -f docker-compose.image.yml up -d
```

Podman:

```bash
cp .env.example .env
podman compose --env-file .env -f podman-compose.yml up --build -d
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign in.

| | |
| --- | --- |
| Username | `admin` |
| Password | `Password@123` |

The first sign-in forces a password change. Compose starts MySQL (persistent volume) and the app, waits for database health, then serves the dashboard, APIs, and background monitor.

```bash
docker compose down
```

Change `SECRET_KEY` and database passwords in `.env` before any shared or production use.

## Requirements

- Python 3.9+ on the host (3.12 in the container image)
- MySQL 8.x
- Docker and Docker Compose, **or** Podman and Podman Compose (recommended)
- `ping` on the host for Ping / ICMP monitors when you run uvicorn outside a container

## Container images

The web image is published to [Docker Hub](https://hub.docker.com/r/superstackinc/pingwatch) as `superstackinc/pingwatch` and to GHCR as `ghcr.io/superstack-oss/pingwatch`. Tags follow `VERSION` (`1.2.0`, `latest` on `main`, and `sha-…`).

GitHub Actions workflow `.github/workflows/publish-image.yml` builds `linux/amd64` and `linux/arm64`. Add repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` so Hub is updated; GHCR publishes with `GITHUB_TOKEN`. Paste `docker/DOCKERHUB.md` into the Hub repository overview.

`install.sh` pulls `superstackinc/pingwatch:<version>` when that tag exists, and otherwise builds from the Dockerfile.

## Installer

`install.sh` is safe to pipe from GitHub. It:

1. Checks OS, architecture, memory, disk, and ports `8000` / `3307`
2. Validates git, curl, and Docker or Podman Compose
3. Installs missing packages (`apt` / `dnf` / `yum` / `pacman` / `zypper`; macOS expects Docker Desktop or Homebrew Podman)
4. Clones `https://github.com/superstack-oss/Pingwatch.git` (or uses the current checkout)
5. Writes `.env` if needed and starts the stack

```bash
./install.sh --help
./install.sh --local --engine docker
./install.sh --dir ~/pingwatch --engine podman --build
```

## Alert channels

When a monitor goes down — and, if you allow it, when it recovers — Pingwatch can notify operators on:

| Channel | Connection |
| --- | --- |
| **Microsoft Teams** | Incoming webhook URL |
| **Slack** | Incoming webhook URL |
| **Webhook** | JSON POST to your endpoint (optional HMAC-SHA256 signature) |
| **PagerDuty** | Events API v2 routing key (trigger on down, resolve on recovery) |
| **Discord** | Incoming webhook URL |
| **Telegram** | Bot token and chat ID |
| **WhatsApp** | Cloud API token, phone number ID, recipient; optional Utility template |
| **Email** | SMTP, configured separately |

Turn on **Status alerts** in **Admin → Settings**, choose a channel from the dropdown, enable it, save, then **Send test**. The info icon next to the dropdown shows setup steps for that channel. Access-request notices still use email only.

## Sign in and access

Unauthenticated visits redirect to `/login`.

New people can submit an **access request** (name, email, phone, password). An admin approves or rejects it from **Admin → Users**. Device add/update/remove, user management, audit logs, and settings are admin-only.

## Run on the host

Useful when Docker Desktop on macOS cannot ICMP-ping LAN NAS/servers from the `web` container.

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d mysql
make dev
```

Production-style uvicorn (no reload):

```bash
make start
```

There is no frontend compile step. Jinja templates and `static/` are served directly.

| Make target | What it runs |
| --- | --- |
| `make install` | Create `.venv` and install `requirements.txt` |
| `make dev` | Uvicorn with reload on `127.0.0.1:8000` |
| `make start` | Uvicorn on `0.0.0.0:8000` |
| `make test` | `pytest` |
| `make docker` | `docker compose up --build` |
| `make podman` | `podman compose -f podman-compose.yml up --build` |

Point `.env` at MySQL. Host `.env.example` publishes MySQL on **3307** so it does not collide with a local MySQL on 3306. Inside Compose the app uses host `mysql` and port `3306`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYSQL_HOST` | `127.0.0.1` | Database host (`mysql` in Compose) |
| `MYSQL_PORT` | `3306` (`3307` in `.env.example` on the host) | Database port |
| `MYSQL_USER` | `pingwatch` | Database user |
| `MYSQL_PASSWORD` | `pingwatch` | Database password |
| `MYSQL_DATABASE` | `pingwatch` | Database name |
| `MYSQL_ROOT_PASSWORD` | `pingwatch` | Compose MySQL root password |
| `MYSQL_PUBLISH_PORT` | `3307` | Host port mapped to MySQL |
| `APP_PORT` | `8000` | Host port mapped to the app |
| `APP_BIND` | `0.0.0.0` | Address Compose binds on the host |
| `PINGWATCH_IMAGE` | (build locally) | Published web image, e.g. `superstackinc/pingwatch:1.2.0` |
| `PINGWATCH_VERSION` | `1.2.0` | Image / app version label |
| `PING_INTERVAL` | `30` | Seconds between fleet sweeps |
| `PING_TIMEOUT` | `2.0` | ICMP timeout in seconds |
| `PING_CONCURRENCY` | `40` | Max parallel probes |
| `HISTORY_KEEP_DAYS` | `31` | How long check samples are retained |
| `WARNING_RTT_MS` | `200` | Latency threshold for Warning |
| `DNS_CACHE_TTL` | `300` | DNS diagnostic cache, seconds |
| `SECRET_KEY` | `pingwatch-dev-secret-change-me` | Signs session cookies |
| `DEFAULT_ADMIN_USERNAME` | `admin` | First-boot admin user |
| `DEFAULT_ADMIN_PASSWORD` | `Password@123` | First-boot admin password |

The Docker image is a multi-stage Python 3.12 build, runs as a non-root user, includes `GET /api/health`, and shuts down uvicorn gracefully.

## Project layout

```
app/            FastAPI, models, monitors, sweep, APIs
templates/      Dashboard, admin, auth (Jinja)
static/         CSS, JS, icons
website/        Commercial marketing site (Vite + React)
tests/          pytest
```

## Troubleshooting

- **App waits on MySQL** — confirm `MYSQL_HOST` / `MYSQL_PORT`. In Compose the app must use host `mysql` and port `3306`.
- **Port 3306 already in use** — `.env.example` publishes MySQL on `3307`.
- **Health check fails** — `GET /api/health` requires a live database.
- **Duplicate monitor** — the same monitor target (type + host + port/spec) returns HTTP 409. You can still Ping and TCP-check the same host.
- **LAN Ping fails from Docker** — run MySQL in Compose and the app on the host with `make dev`.
- **No 7d / 30d history yet** — samples accumulate from the sweep interval; older data is kept for `HISTORY_KEEP_DAYS`.

## Built by Superstack

Pingwatch is developed by [Superstack](https://superstack.in). Try the public demo at [demo-pingwatch.superstack.in](https://demo-pingwatch.superstack.in).

