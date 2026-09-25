from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
FILE_EXTS = {
    ".pdf",
    ".txt",
    ".csv",
    ".log",
    ".zip",
    ".json",
    ".xml",
    ".docx",
    ".xlsx",
    ".doc",
    ".xls",
    ".pptx",
    ".pcap",
    ".cap",
}
ALLOWED_EXTS = IMAGE_EXTS | FILE_EXTS
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS = 40

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def attachment_root() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def incident_dir(incident_id: int) -> Path:
    path = attachment_root() / str(int(incident_id))
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def attachment_kind(filename: str) -> Optional[str]:
    ext = extension(filename)
    if ext in IMAGE_EXTS:
        return "image"
    if ext in FILE_EXTS:
        return "file"
    return None


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "attachment").name
    cleaned = _SAFE_NAME.sub("_", name).strip("._") or "attachment"
    return cleaned[:120]


def store_name(filename: str) -> str:
    return "%s_%s" % (uuid.uuid4().hex, sanitize_filename(filename))


def save_bytes(incident_id: int, filename: str, payload: bytes) -> Tuple[str, Path]:
    stored = store_name(filename)
    path = incident_dir(incident_id) / stored
    path.write_bytes(payload)
    return stored, path


def stored_path(incident_id: int, stored_name: str) -> Path:
    name = Path(stored_name).name
    return incident_dir(incident_id) / name


def delete_stored(incident_id: int, stored_name: str) -> None:
    path = stored_path(incident_id, stored_name)
    if path.is_file():
        path.unlink()


def purge_incident_files(incident_id: int) -> None:
    path = attachment_root() / str(int(incident_id))
    if not path.is_dir():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
    try:
        path.rmdir()
    except OSError:
        pass
