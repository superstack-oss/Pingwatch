# Pingwatch

Uptime monitoring for ping, TCP ports, DNS, WebSocket, gRPC health, and game servers. FastAPI serves the dashboard and APIs; MySQL stores devices and check history.

## Requirements

- Python 3.9+ (3.12 recommended)
- MySQL 8.x
- Docker and Docker Compose (optional, recommended)
- ICMP ping available on the host (`ping`) for Ping monitors

## Monitor types

| Monitor | What it checks |
| --- | --- |
| Ping | ICMP echo request to a host or IP |
| TCP Port | TCP handshake to a host and port |
| DNS | Lookup of a name/type against a chosen resolver |
| WebSocket | HTTP 101 upgrade to a `ws://` or `wss://` endpoint |
| gRPC | Standard gRPC health protocol; anything but `SERVING` is down |
| Game server | Native query for 100+ game types (A2S, Minecraft, Bedrock, FiveM, GameSpy, Quake 3, and related) |

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYSQL_HOST` | `127.0.0.1` | Database host |
| `MYSQL_PORT` | `3306` (`3307` in `.env.example` for Docker publish) | Database port |
| `MYSQL_USER` | `pingwatch` | Database user |
| `MYSQL_PASSWORD` | `pingwatch` | Database password |
| `MYSQL_DATABASE` | `pingwatch` | Database name |
| `MYSQL_ROOT_PASSWORD` | `pingwatch` | Compose MySQL root password |
| `MYSQL_PUBLISH_PORT` | `3307` | Host port mapped to MySQL |
| `APP_PORT` | `8000` | Host port mapped to the app |
| `PING_INTERVAL` | `30` | Seconds between fleet sweeps |
| `PING_TIMEOUT` | `2.0` | ICMP timeout in seconds |
| `PING_CONCURRENCY` | `20` | Max parallel pings |
| `HISTORY_KEEP_DAYS` | `31` | How long check samples are retained |
| `WARNING_RTT_MS` | `200` | Latency threshold for Warning |
| `DNS_CACHE_TTL` | `300` | DNS diagnostic cache, seconds |
| `SECRET_KEY` | `pingwatch-dev-secret-change-me` | Signs session cookies. Change this in any shared environment. |

Copy `.env.example` to `.env` and change passwords before any shared or production use.

## Sign in

Default administrator (created on first boot):

- Username: `admin`
- Password: `Password@123`

The first sign-in forces a password change. New people can submit an access request (name, email, phone, password); an admin approves or rejects it from **Admin → Users**. Device add/update/remove, user management, audit logs, and settings live in the admin console.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Unauthenticated visits redirect to `/login`.

## Docker setup

```bash
cp .env.example .env
docker compose up --build
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign in. Compose starts MySQL (persistent volume) and the web app, waits for database health, then serves the dashboard, APIs, and background ping monitor.

```bash
docker compose down
```

## Non-Docker setup

Equivalent to `npm install` / `npm run dev`:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start MySQL (Compose database only is fine):

```bash
docker compose up -d mysql
```

Development server (`npm run dev` equivalent):

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Production server (`npm run start` equivalent):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 15
```

There is no frontend compile step. Templates and static files are served directly.

Makefile shortcuts: `make install`, `make dev`, `make start`, `make test`.

## Development commands

```bash
make test          # pytest
make dev           # reload server
make docker        # docker compose up --build
```

## Production build / run

Docker is the production artifact:

```bash
docker compose up --build -d
```

The image is a multi-stage Python 3.12 build, runs as a non-root user, includes a health check, and shuts down uvicorn gracefully.

Direct production run: install dependencies, point `.env` at MySQL, then `make start`.

## LAN devices

Docker Desktop on macOS often cannot ICMP-ping LAN addresses from the `web` container. For local NAS/server monitoring, run MySQL in Compose and the app on the host with `make dev`.

## Troubleshooting

- **App waits on MySQL**: confirm `MYSQL_HOST` / `MYSQL_PORT`. In Compose the app must use host `mysql` and port `3306`.
- **Port 3306 already in use**: `.env.example` publishes MySQL on `3307`.
- **Health check fails**: `GET /api/health` requires a live database.
- **Duplicate host**: adding the same hostname/IP twice returns HTTP 409.
- **No 7d/30d history yet**: samples accumulate from the monitor interval; older data is kept for `HISTORY_KEEP_DAYS`.
