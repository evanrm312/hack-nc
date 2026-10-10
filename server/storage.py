"""Image storage helpers. Owned by Person 1; consumed by Person 4 for evidence.

Two scopes:
- ``public``  listing photos, served at /media/public/<path> by catalog.py
- ``private`` condition evidence, only readable through an endpoint that has
              checked the caller is a participant (``authorize_private_read``).

Rules: image type is detected from magic bytes (never the filename or the
client's Content-Type), size is capped, and the stored name is generated
server-side, so uploaded filenames are never trusted.

Usage:
    storage = get_storage()
    stored = storage.save("public", request.files["photo"].stream, max_bytes)
    listing.public_photo_path = stored.path

    authorize_private_read(current_profile().id, exchange.participant_ids)
    return storage.send("private", evidence.private_storage_path, evidence.content_type)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from flask import current_app, send_from_directory

from .errors import ApiError

SCOPES = ("public", "private")

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)


@dataclass(frozen=True)
class StoredFile:
    scope: str
    path: str  # relative, server-generated, e.g. "ab/abcd1234....jpg"
    content_type: str
    size: int


def detect_image_type(head: bytes) -> tuple[str, str] | None:
    """Return (content_type, extension) for JPEG/PNG/WebP, else None."""
    for magic, content_type, ext in _MAGIC:
        if head.startswith(magic):
            return content_type, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def read_image_upload(stream: BinaryIO, max_bytes: int) -> tuple[bytes, str, str]:
    """Read and validate an uploaded image. Raises ApiError on bad input."""
    data = stream.read(max_bytes + 1)
    if not data:
        raise ApiError(400, "validation_error", "Invalid upload", {"file": "empty file"})
    if len(data) > max_bytes:
        raise ApiError(413, "payload_too_large", f"Image must be at most {max_bytes} bytes", {"file": "too large"})
    detected = detect_image_type(data[:16])
    if detected is None:
        raise ApiError(
            400,
            "unsupported_image",
            "Only JPEG, PNG, or WebP images are accepted",
            {"file": "unrecognized image format"},
        )
    content_type, ext = detected
    return data, content_type, ext


def authorize_private_read(viewer_id: str | None, participant_ids) -> None:
    """Raise 403 unless the viewer is one of the participants."""
    if viewer_id is None or viewer_id not in set(participant_ids):
        raise ApiError(403, "forbidden", "Only participants can view this evidence")


class LocalStorage:
    """Filesystem backend under UPLOAD_DIR/{public,private}."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)

    def _scope_dir(self, scope: str) -> Path:
        if scope not in SCOPES:
            raise ValueError(f"unknown scope {scope!r}")
        return self.root / scope

    def save(self, scope: str, stream: BinaryIO, max_bytes: int) -> StoredFile:
        data, content_type, ext = read_image_upload(stream, max_bytes)
        name = uuid.uuid4().hex
        rel = Path(name[:2]) / f"{name}.{ext}"
        target = self._scope_dir(scope) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredFile(scope=scope, path=rel.as_posix(), content_type=content_type, size=len(data))

    def send(self, scope: str, path: str, content_type: str | None = None):
        """Flask response streaming the stored file. Path traversal is refused."""
        directory = self._scope_dir(scope).resolve()
        resolved = (directory / path).resolve()
        if directory not in resolved.parents or not resolved.is_file():
            raise ApiError(404, "not_found", "file not found")
        return send_from_directory(directory, path, mimetype=content_type, conditional=True)

    def delete(self, scope: str, path: str) -> None:
        target = (self._scope_dir(scope) / path).resolve()
        if self._scope_dir(scope).resolve() in target.parents and target.is_file():
            target.unlink()


class SupabaseStorage:
    """Interface for Supabase Storage buckets (public-listings / private-evidence).

    Not implemented yet; tracked in docs/tasks.md. Same method signatures as
    LocalStorage so Person 4 code does not change when it lands.
    """

    def __init__(self, url: str, service_role_key: str):
        self.url = url
        self.service_role_key = service_role_key  # backend only

    def save(self, scope: str, stream: BinaryIO, max_bytes: int) -> StoredFile:
        raise NotImplementedError("SupabaseStorage.save is not implemented; set STORAGE_BACKEND=local")

    def send(self, scope: str, path: str, content_type: str | None = None):
        raise NotImplementedError("SupabaseStorage.send is not implemented; set STORAGE_BACKEND=local")

    def delete(self, scope: str, path: str) -> None:
        raise NotImplementedError("SupabaseStorage.delete is not implemented; set STORAGE_BACKEND=local")


def get_storage():
    config = current_app.config
    backend = config["STORAGE_BACKEND"]
    if backend == "local":
        return LocalStorage(config["UPLOAD_DIR"])
    if backend == "supabase":
        return SupabaseStorage(config["SUPABASE_URL"] or "", config["SUPABASE_SERVICE_ROLE_KEY"] or "")
    raise RuntimeError(f"Unknown STORAGE_BACKEND {backend!r}")
