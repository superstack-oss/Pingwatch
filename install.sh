#!/usr/bin/env bash
# Pingwatch installer — checks the host, installs missing tools, clones the repo, starts Compose.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/superstack-oss/Pingwatch/main/install.sh | bash
#   ./install.sh --dir ~/pingwatch --engine docker
set -euo pipefail

REPO_URL="${PINGWATCH_REPO:-https://github.com/superstack-oss/Pingwatch.git}"
REPO_REF="${PINGWATCH_REF:-main}"
INSTALL_DIR="${PINGWATCH_DIR:-$HOME/pingwatch}"
ENGINE="${PINGWATCH_ENGINE:-}"
HUB_IMAGE_NS="${PINGWATCH_HUB_IMAGE:-superstackinc/pingwatch}"
FORCE_BUILD=0
SKIP_START=0
ASSUME_YES=0
LOCAL_ONLY=0
APP_PORT="${APP_PORT:-8000}"
MYSQL_PUBLISH_PORT="${MYSQL_PUBLISH_PORT:-3307}"
MIN_DISK_MB=2048
MIN_MEM_MB=768

COMPOSE_CMD=()
COMPOSE_FILES=()
NEED_INSTALL=()
OS_KIND=""
PKG=""
SUDO=""

log() { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
ok() { printf '    ok  %s\n' "$*"; }
warn() { printf '    warn  %s\n' "$*" >&2; }
fail() { printf '    error  %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
  cat <<'EOF'
Pingwatch installer

  --dir DIR          Clone / use this directory (default: ~/pingwatch)
  --engine NAME      docker or podman (default: auto)
  --ref REF          Git branch or tag (default: main)
  --build            Build the web image locally instead of pulling Docker Hub
  --local            Use the current checkout; do not clone
  --no-start         Stop after clone / .env; do not start containers
  --yes              Do not prompt (needed for curl | bash package installs)
  -h, --help         Show this help

Environment: PINGWATCH_DIR, PINGWATCH_ENGINE, PINGWATCH_REPO, PINGWATCH_REF,
             PINGWATCH_IMAGE, APP_PORT, MYSQL_PUBLISH_PORT
EOF
}

prompt_yes() {
  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi
  if [ ! -r /dev/tty ]; then
    fail "Non-interactive shell. Re-run with --yes to install missing packages."
  fi
  printf '    %s [y/N] ' "$1" >/dev/tty
  local reply
  read -r reply </dev/tty || true
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif [ -n "$SUDO" ]; then
    "$SUDO" "$@"
  else
    fail "Need root or sudo to run: $*"
  fi
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir) INSTALL_DIR="$2"; shift 2 ;;
      --engine) ENGINE="$2"; shift 2 ;;
      --ref) REPO_REF="$2"; shift 2 ;;
      --build) FORCE_BUILD=1; shift ;;
      --local) LOCAL_ONLY=1; shift ;;
      --no-start) SKIP_START=1; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) fail "Unknown option: $1" ;;
    esac
  done
}

detect_os() {
  local uname_s uname_m
  uname_s="$(uname -s)"
  uname_m="$(uname -m)"
  case "$uname_s" in
    Linux) OS_KIND="linux" ;;
    Darwin) OS_KIND="darwin" ;;
    *) fail "Unsupported OS: $uname_s (Linux or macOS required)" ;;
  esac
  case "$uname_m" in
    x86_64|amd64|arm64|aarch64) ok "architecture $uname_m" ;;
    *) fail "Unsupported architecture: $uname_m (need x86_64 or arm64)" ;;
  esac
  if [ "$OS_KIND" = "linux" ] && [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    ok "os ${PRETTY_NAME:-$ID}"
    case "${ID_LIKE:-$ID}" in
      *debian*|*ubuntu*) PKG="apt" ;;
      *rhel*|*fedora*|*centos*|*rocky*|*alma*) PKG="dnf" ;;
      *suse*) PKG="zypper" ;;
      *arch*) PKG="pacman" ;;
      *) PKG="${ID:-unknown}" ;;
    esac
    if [ "$PKG" = "dnf" ] && ! have dnf && have yum; then
      PKG="yum"
    fi
  elif [ "$OS_KIND" = "darwin" ]; then
    ok "os macOS $(uname -r)"
    PKG="brew"
  fi
  if have sudo && [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
  fi
}

mem_mb() {
  if [ "$OS_KIND" = "darwin" ]; then
    local bytes
    bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
    echo $((bytes / 1024 / 1024))
    return
  fi
  if [ -f /proc/meminfo ]; then
    awk '/MemTotal:/ { printf "%d", $2 / 1024 }' /proc/meminfo
    return
  fi
  echo 0
}

disk_mb() {
  local target="$1"
  mkdir -p "$target" 2>/dev/null || true
  df -Pm "$target" 2>/dev/null | awk 'NR==2 { print $4 }'
}

port_in_use() {
  local port="$1"
  if have ss; then
    ss -ltn 2>/dev/null | grep -qE ":${port}[[:space:]]"
    return $?
  fi
  if have lsof; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if have netstat; then
    netstat -an 2>/dev/null | grep -qE "[.:]${port}[[:space:]].*LISTEN"
    return $?
  fi
  return 1
}

check_system() {
  step "1/5  Checking system configuration"
  detect_os
  ok "user $(id -un) (uid $(id -u))"

  local mem disk
  mem="$(mem_mb)"
  disk="$(disk_mb "$INSTALL_DIR")"
  if [ "${mem:-0}" -gt 0 ] && [ "$mem" -lt "$MIN_MEM_MB" ]; then
    fail "Need at least ${MIN_MEM_MB} MB RAM (found ${mem} MB)"
  fi
  [ "${mem:-0}" -gt 0 ] && ok "memory ${mem} MB"
  if [ "${disk:-0}" -gt 0 ] && [ "$disk" -lt "$MIN_DISK_MB" ]; then
    fail "Need at least ${MIN_DISK_MB} MB free disk at $INSTALL_DIR (found ${disk} MB)"
  fi
  [ "${disk:-0}" -gt 0 ] && ok "free disk ${disk} MB at $INSTALL_DIR"

  if port_in_use "$APP_PORT"; then
    warn "port $APP_PORT is already listening — set APP_PORT if Pingwatch cannot bind"
  else
    ok "port $APP_PORT is free"
  fi
  if port_in_use "$MYSQL_PUBLISH_PORT"; then
    warn "port $MYSQL_PUBLISH_PORT is already listening — MySQL publish port may collide"
  else
    ok "port $MYSQL_PUBLISH_PORT is free"
  fi

  if [ "$OS_KIND" = "linux" ]; then
    if [ -d /sys/fs/cgroup ]; then
      ok "cgroup present"
    else
      warn "cgroup filesystem not found — containers may fail to start"
    fi
  fi
}

engine_ready() {
  local name="$1"
  if [ "$name" = "docker" ]; then
    have docker || return 1
    docker info >/dev/null 2>&1 || return 1
    docker compose version >/dev/null 2>&1 || return 1
    return 0
  fi
  if [ "$name" = "podman" ]; then
    have podman || return 1
    podman info >/dev/null 2>&1 || return 1
    if podman compose version >/dev/null 2>&1; then
      return 0
    fi
    have podman-compose || return 1
    return 0
  fi
  return 1
}

pick_engine() {
  if [ -n "$ENGINE" ]; then
    case "$ENGINE" in
      docker|podman) ;;
      *) fail "Engine must be docker or podman (got $ENGINE)" ;;
    esac
    return
  fi
  if engine_ready docker; then
    ENGINE="docker"
  elif engine_ready podman; then
    ENGINE="podman"
  else
    ENGINE="docker"
  fi
}

validate_requirements() {
  step "2/5  Validating project requirements"
  pick_engine
  NEED_INSTALL=""
  have curl || NEED_INSTALL="$NEED_INSTALL curl"
  have git || NEED_INSTALL="$NEED_INSTALL git"
  if [ "$ENGINE" = "docker" ]; then
    if ! have docker; then
      NEED_INSTALL="$NEED_INSTALL docker"
    elif ! docker info >/dev/null 2>&1; then
      warn "Docker CLI is installed but the engine is not running"
      if [ "$SKIP_START" -eq 0 ]; then
        NEED_INSTALL="$NEED_INSTALL docker-engine"
      fi
    fi
    if have docker && ! docker compose version >/dev/null 2>&1; then
      NEED_INSTALL="$NEED_INSTALL docker-compose"
    fi
  else
    have podman || NEED_INSTALL="$NEED_INSTALL podman"
    if have podman && ! podman compose version >/dev/null 2>&1 && ! have podman-compose; then
      NEED_INSTALL="$NEED_INSTALL podman-compose"
    fi
    if have podman && ! podman info >/dev/null 2>&1; then
      warn "Podman is installed but the engine is not ready"
      if [ "$SKIP_START" -eq 0 ]; then
        NEED_INSTALL="$NEED_INSTALL podman-engine"
      fi
    fi
  fi
  if [ -z "$(echo "$NEED_INSTALL" | tr -d ' ')" ]; then
    ok "git, curl, and $ENGINE compose are ready"
  else
    log "    missing:${NEED_INSTALL}"
  fi
  ok "container engine target: $ENGINE"
}

apt_install() {
  as_root apt-get update -y
  as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git
  case "$NEED_INSTALL" in
    *docker*|*docker-compose*|*docker-engine*)
      as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 || \
        as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose
      if have systemctl; then
        as_root systemctl enable --now docker 2>/dev/null || as_root service docker start || true
      fi
      if [ "$(id -u)" -ne 0 ]; then
        as_root usermod -aG docker "$(id -un)" 2>/dev/null || true
        warn "added $(id -un) to the docker group — this session may still need sudo"
      fi
      ;;
  esac
  case "$NEED_INSTALL" in
    *podman*)
      as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y podman
      as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y podman-compose 2>/dev/null || true
      ;;
  esac
}

dnf_install() {
  local bin="$PKG"
  as_root "$bin" install -y curl git ca-certificates
  case "$NEED_INSTALL" in
    *docker*|*docker-compose*|*docker-engine*)
      as_root "$bin" install -y docker docker-compose || as_root "$bin" install -y moby-engine docker-compose
      if have systemctl; then
        as_root systemctl enable --now docker 2>/dev/null || true
      fi
      if [ "$(id -u)" -ne 0 ]; then
        as_root usermod -aG docker "$(id -un)" 2>/dev/null || true
      fi
      ;;
  esac
  case "$NEED_INSTALL" in
    *podman*)
      as_root "$bin" install -y podman
      as_root "$bin" install -y podman-compose 2>/dev/null || true
      ;;
  esac
}

pacman_install() {
  as_root pacman -Sy --noconfirm curl git
  case "$NEED_INSTALL" in
    *docker*) as_root pacman -S --noconfirm docker docker-compose; as_root systemctl enable --now docker 2>/dev/null || true ;;
  esac
  case "$NEED_INSTALL" in
    *podman*) as_root pacman -S --noconfirm podman podman-compose ;;
  esac
}

zypper_install() {
  as_root zypper --non-interactive install curl git
  case "$NEED_INSTALL" in
    *docker*) as_root zypper --non-interactive install docker docker-compose; as_root systemctl enable --now docker 2>/dev/null || true ;;
  esac
  case "$NEED_INSTALL" in
    *podman*) as_root zypper --non-interactive install podman python3-podman-compose 2>/dev/null || as_root zypper --non-interactive install podman ;;
  esac
}

install_macos() {
  if ! have git || ! have curl; then
    if have brew; then
      brew install git curl
    else
      fail "Install Xcode Command Line Tools (xcode-select --install) or Homebrew, then re-run"
    fi
  fi
  if [ "$ENGINE" = "docker" ] && ! engine_ready docker; then
    if [ "$SKIP_START" -eq 1 ]; then
      warn "Docker engine is not running; containers will not be started"
      return
    fi
    fail "Install Docker Desktop for Mac from https://www.docker.com/products/docker-desktop/ and start it, then re-run"
  fi
  if [ "$ENGINE" = "podman" ] && ! engine_ready podman; then
    if have brew; then
      prompt_yes "Install Podman with Homebrew?" || fail "Podman is required"
      brew install podman
      podman machine inspect >/dev/null 2>&1 || podman machine init
      podman machine start 2>/dev/null || true
    else
      fail "Install Podman Desktop from https://podman-desktop.io/ and re-run"
    fi
  fi
}

install_missing() {
  step "3/5  Installing missing requirements"
  if [ -z "$(echo "$NEED_INSTALL" | tr -d ' ')" ] && { [ "$ENGINE" != "docker" ] || docker info >/dev/null 2>&1; }; then
    ok "nothing to install"
    return
  fi
  if [ "$OS_KIND" = "darwin" ]; then
    install_macos
    return
  fi
  prompt_yes "Install missing packages (${NEED_INSTALL} ) with $PKG?" || fail "Aborted"
  case "$PKG" in
    apt) apt_install ;;
    dnf|yum) dnf_install ;;
    pacman) pacman_install ;;
    zypper) zypper_install ;;
    *)
      fail "Unknown package manager. Install git, curl, and $ENGINE compose, then re-run."
      ;;
  esac
  if [ "$ENGINE" = "docker" ] && ! docker info >/dev/null 2>&1; then
    if [ -n "$SUDO" ] && "$SUDO" docker info >/dev/null 2>&1; then
      warn "using sudo for Docker (log out and back in to use docker without sudo)"
    else
      fail "Docker engine is not running. Start it and re-run."
    fi
  fi
  ok "runtime tools installed"
}

set_compose_cmd() {
  if [ "$ENGINE" = "docker" ]; then
    if docker info >/dev/null 2>&1; then
      COMPOSE_CMD=(docker compose)
    else
      COMPOSE_CMD=(sudo docker compose)
    fi
    return
  fi
  if podman compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(podman compose)
  else
    COMPOSE_CMD=(podman-compose)
  fi
}

compose() {
  (
    cd "$INSTALL_DIR"
    "${COMPOSE_CMD[@]}" --env-file .env "${COMPOSE_FILES[@]}" "$@"
  )
}

is_checkout() {
  local dir="$1"
  [ -f "$dir/docker-compose.yml" ] && [ -f "$dir/app/main.py" ] && [ -f "$dir/Dockerfile" ]
}

download_repo() {
  step "4/5  Downloading the repository"
  if [ "$LOCAL_ONLY" -eq 1 ]; then
    if is_checkout "$(pwd)"; then
      INSTALL_DIR="$(pwd)"
      ok "using current checkout $INSTALL_DIR"
      return
    fi
    fail "--local requires a Pingwatch checkout (docker-compose.yml + app/main.py)"
  fi
  if is_checkout "$(pwd)" && [ "$INSTALL_DIR" = "$HOME/pingwatch" ]; then
    INSTALL_DIR="$(pwd)"
    ok "already inside Pingwatch at $INSTALL_DIR"
    return
  fi
  if is_checkout "$INSTALL_DIR"; then
    ok "found existing checkout $INSTALL_DIR"
    if have git && [ -d "$INSTALL_DIR/.git" ]; then
      git -C "$INSTALL_DIR" fetch --quiet origin 2>/dev/null || true
      git -C "$INSTALL_DIR" checkout --quiet "$REPO_REF" 2>/dev/null || true
      git -C "$INSTALL_DIR" pull --ff-only --quiet origin "$REPO_REF" 2>/dev/null || true
      ok "updated $REPO_REF"
    fi
    return
  fi
  have git || fail "git is required to clone $REPO_URL"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [ -e "$INSTALL_DIR" ] && [ ! -d "$INSTALL_DIR/.git" ]; then
    fail "$INSTALL_DIR exists and is not a git checkout"
  fi
  log "    cloning $REPO_URL ($REPO_REF) → $INSTALL_DIR"
  git clone --branch "$REPO_REF" --depth 1 "$REPO_URL" "$INSTALL_DIR"
  ok "cloned $INSTALL_DIR"
}

random_secret() {
  if have openssl; then
    openssl rand -hex 32
    return
  fi
  LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64
}

ensure_env() {
  if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    local secret
    secret="$(random_secret)"
    if [ -n "$secret" ]; then
      if have python3; then
        SECRET_KEY="$secret" python3 - "$INSTALL_DIR/.env" <<'PY'
import os, pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
text = re.sub(r"^SECRET_KEY=.*$", "SECRET_KEY=" + os.environ["SECRET_KEY"], text, count=1, flags=re.M)
path.write_text(text)
PY
      else
        # Fallback: rewrite SECRET_KEY line without python
        local tmp
        tmp="$(mktemp)"
        awk -v key="$secret" 'BEGIN{done=0} /^SECRET_KEY=/{print "SECRET_KEY=" key; done=1; next} {print} END{if(!done) print "SECRET_KEY=" key}' "$INSTALL_DIR/.env" >"$tmp"
        mv "$tmp" "$INSTALL_DIR/.env"
      fi
    fi
    ok "wrote $INSTALL_DIR/.env (generated SECRET_KEY)"
  else
    ok "keeping existing $INSTALL_DIR/.env"
  fi
  if [ -n "${APP_PORT:-}" ]; then
    grep -q '^APP_PORT=' "$INSTALL_DIR/.env" 2>/dev/null || echo "APP_PORT=$APP_PORT" >>"$INSTALL_DIR/.env"
  fi
}

read_version() {
  if [ -f "$INSTALL_DIR/VERSION" ]; then
    tr -d '[:space:]' <"$INSTALL_DIR/VERSION"
  else
    echo "1.2.0"
  fi
}

read_env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1==key { sub(/^[^=]+=/,""); print; exit }' "$INSTALL_DIR/.env" 2>/dev/null || true
}

wait_health() {
  local port="$1"
  local tries=45
  local i url
  url="http://127.0.0.1:${port}/api/health"
  i=0
  while [ "$i" -lt "$tries" ]; do
    if have curl && curl -fsS "$url" >/dev/null 2>&1; then
      ok "healthy at $url"
      return 0
    fi
    i=$((i + 1))
    sleep 2
  done
  warn "timed out waiting for $url — check: ${COMPOSE_CMD[*]} -f ${COMPOSE_FILES[*]} logs"
  return 1
}

start_stack() {
  step "5/5  Starting Pingwatch in $ENGINE"
  set_compose_cmd
  ensure_env
  local version image pulled tmp
  version="$(read_version)"
  image="${PINGWATCH_IMAGE:-$HUB_IMAGE_NS:$version}"
  pulled=0

  if [ "$ENGINE" = "podman" ]; then
    COMPOSE_FILES=(-f podman-compose.yml)
  else
    COMPOSE_FILES=(-f docker-compose.yml)
  fi

  if [ "$FORCE_BUILD" -eq 0 ]; then
    log "    pulling $image"
    COMPOSE_FILES=(-f docker-compose.image.yml)
    if PINGWATCH_IMAGE="$image" compose pull web; then
      pulled=1
      ok "using Docker Hub image $image"
      if grep -q '^PINGWATCH_IMAGE=' "$INSTALL_DIR/.env"; then
        tmp="$(mktemp)"
        awk -v img="$image" 'BEGIN{done=0} /^PINGWATCH_IMAGE=/{print "PINGWATCH_IMAGE=" img; done=1; next} {print} END{if(!done) print "PINGWATCH_IMAGE=" img}' "$INSTALL_DIR/.env" >"$tmp"
        mv "$tmp" "$INSTALL_DIR/.env"
      else
        echo "PINGWATCH_IMAGE=$image" >>"$INSTALL_DIR/.env"
      fi
    else
      warn "Hub image not available yet — building from source"
      if [ "$ENGINE" = "podman" ]; then
        COMPOSE_FILES=(-f podman-compose.yml)
      else
        COMPOSE_FILES=(-f docker-compose.yml)
      fi
    fi
  fi

  if [ "$pulled" -eq 1 ]; then
    compose up -d --remove-orphans --no-build
  elif [ "$ENGINE" = "podman" ]; then
    COMPOSE_FILES=(-f podman-compose.yml)
    compose up --build -d --remove-orphans
  else
    COMPOSE_FILES=(-f docker-compose.yml)
    compose up --build -d --remove-orphans
  fi
  compose ps
  local port
  port="$(read_env_value APP_PORT)"
  [ -n "$port" ] || port="$APP_PORT"
  wait_health "$port" || true
  log ""
  log "Pingwatch is starting."
  log "  URL:      http://127.0.0.1:${port}"
  log "  Username: $(read_env_value DEFAULT_ADMIN_USERNAME)"
  log "  Password: $(read_env_value DEFAULT_ADMIN_PASSWORD)"
  log "Change the admin password on first sign-in. Edit $INSTALL_DIR/.env before production use."
}

main() {
  parse_args "$@"
  log "Pingwatch installer"
  check_system
  validate_requirements
  install_missing
  download_repo
  if [ "$SKIP_START" -eq 1 ]; then
    ensure_env
    ok "checkout ready at $INSTALL_DIR (--no-start)"
    return
  fi
  start_stack
}

main "$@"
