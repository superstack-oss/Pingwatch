# syntax=docker/dockerfile:1
# Podman Containerfile — keep in sync with Dockerfile.
# Pingwatch web image on Docker Hardened Images.
# Builder: dhi.io/python dev variant (shell, apt, pip).
# Runtime: minimal DHI Python image — no shell, no package manager.
# https://docs.docker.com/dhi/

FROM dhi.io/python:3.12-debian13 AS runtime-base

FROM dhi.io/python:3.12-debian13-dev AS builder

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

# ping and traceroute are copied into the shell-less runtime. libc stays in the
# base image; only the extra shared libraries are staged.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping traceroute \
    && rm -rf /var/lib/apt/lists/*
RUN python - <<'PY'
import os
import shutil
import subprocess

def stage_path(path: str) -> str:
    # /lib and /bin are symlinks in the runtime image. Stage under /usr
    # so the copy does not try to replace those symlinks with directories.
    if path.startswith("/lib/"):
        return "/usr" + path
    if path.startswith("/bin/"):
        return "/usr" + path
    return path

def copy_bin(src: str, name: str) -> None:
    real = os.path.realpath(src)
    dest_dir = "/opt/nettools/usr/bin"
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, name)
    shutil.copy2(real, dest)
    os.chmod(dest, 0o755)
    out = subprocess.check_output(["ldd", real], text=True)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[1] != "=>" or not parts[2].startswith("/"):
            continue
        lib = parts[2]
        if "libc.so" in lib or "ld-linux" in lib:
            continue
        libreal = stage_path(os.path.realpath(lib))
        soname = stage_path(lib)
        os.makedirs("/opt/nettools" + os.path.dirname(libreal), exist_ok=True)
        shutil.copy2(os.path.realpath(lib), "/opt/nettools" + libreal)
        os.chmod("/opt/nettools" + libreal, 0o644)
        if soname != libreal:
            link_dir = "/opt/nettools" + os.path.dirname(soname)
            os.makedirs(link_dir, exist_ok=True)
            link = "/opt/nettools" + soname
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(os.path.basename(libreal), link)

copy_bin("/usr/bin/ping", "ping")
copy_bin("/usr/bin/traceroute", "traceroute")
PY

COPY --from=runtime-base /etc/passwd /tmp/runtime-passwd
COPY --from=runtime-base /etc/group /tmp/runtime-group
RUN mkdir -p /opt/identity /home/pingwatch /app/data/incident-attachments \
    && cp /tmp/runtime-passwd /opt/identity/passwd \
    && printf '%s\n' 'pingwatch:x:1000:1000:Pingwatch:/home/pingwatch:/usr/sbin/nologin' >> /opt/identity/passwd \
    && cp /tmp/runtime-group /opt/identity/group \
    && printf '%s\n' 'pingwatch:x:1000:' >> /opt/identity/group \
    && chmod 644 /opt/identity/passwd /opt/identity/group \
    && chown -R 1000:1000 /home/pingwatch /app/data \
    && chmod 755 /home/pingwatch /app /app/data /app/data/incident-attachments


FROM dhi.io/python:3.12-debian13

# The runtime image has no shell. Drop unused interpreters and CLIs as root,
# then switch back to the non-root application user below.
USER 0
RUN ["/usr/bin/python", "-c", "import glob, os, shutil\npaths=['/usr/bin/pip','/usr/bin/pip3','/usr/bin/idle','/usr/bin/idle3','/usr/bin/idle3.12','/usr/bin/pydoc','/usr/bin/pydoc3','/usr/bin/pydoc3.12','/usr/bin/openssl','/usr/bin/c_rehash','/usr/bin/clear','/usr/bin/reset','/usr/bin/tabs','/usr/bin/tic','/usr/bin/toe','/usr/bin/tput','/usr/bin/tset','/usr/bin/captoinfo','/usr/bin/infocmp','/usr/bin/infotocap','/usr/bin/debconf','/usr/bin/debconf-apt-progress','/usr/bin/debconf-communicate','/usr/bin/debconf-copydb','/usr/bin/debconf-escape','/usr/bin/debconf-set-selections','/usr/bin/debconf-show','/usr/sbin/dpkg-preconfigure','/usr/sbin/dpkg-reconfigure','/usr/sbin/update-ca-certificates']\nfor path in paths:\n    if os.path.lexists(path):\n        os.remove(path)\nfor pattern in ['/usr/lib/python3/dist-packages/pip','/usr/lib/python3/dist-packages/pip-*.dist-info','/usr/lib/python3/dist-packages/setuptools','/usr/lib/python3/dist-packages/setuptools-*.dist-info','/usr/lib/python3/dist-packages/wheel','/usr/lib/python3/dist-packages/wheel-*.dist-info','/usr/lib/python3.12/idlelib','/usr/lib/python3.12/pydoc_data']:\n    for path in glob.glob(pattern):\n        shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)\n"]

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
      org.opencontainers.image.version="${PINGWATCH_VERSION}" \
      org.opencontainers.image.base.name="dhi.io/python:3.12-debian13"

WORKDIR /app

COPY --from=builder /opt/identity/passwd /etc/passwd
COPY --from=builder /opt/identity/group /etc/group
COPY --from=builder /opt/nettools/ /
COPY --from=builder --chown=1000:1000 /venv /venv
COPY --from=builder --chown=1000:1000 /home/pingwatch /home/pingwatch
COPY --from=builder --chown=1000:1000 /app/data /app/data
COPY --chown=1000:1000 app ./app
COPY --chown=1000:1000 templates ./templates
COPY --chown=1000:1000 static ./static

USER pingwatch

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

# Single worker: the in-process sweep must not be duplicated.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "20"]
