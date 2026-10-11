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
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import requests
from flask import Response, current_app, has_request_context, request, send_from_directory

from .errors import ApiError

SCOPES = ("public", "private")
_GENERATED_PATH = re.compile(r"[0-9a-f]{2}/[0-9a-f]{32}\.(?:jpg|png|webp)\Z")
_PRIVATE_READ_KEY = "campus.private_evidence_authorized"

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
    if has_request_context():
        request.environ[_PRIVATE_READ_KEY] = True


def _require_private_read(scope: str) -> None:
    if scope == "private" and (
        not has_request_context() or not request.environ.get(_PRIVATE_READ_KEY)
    ):
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
        _require_private_read(scope)
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
    """Server-side Storage API adapter. The service key never reaches the browser.

    Buckets must be configured as public listings / private evidence in
    Supabase. Private files are returned only after a participant check in
    the same Flask request; no signed or public evidence URL is generated.
    """

    def __init__(self, url: str, service_role_key: str, public_bucket: str = "public-listings", private_bucket: str = "private-evidence", timeout: float = 10):
        self.url = url.rstrip("/") + "/storage/v1"
        self.service_role_key = service_role_key  # backend only
        self.buckets = {"public": public_bucket, "private": private_bucket}
        self.timeout = timeout

    def _bucket(self, scope: str) -> str:
        if scope not in SCOPES:
            raise ValueError(f"unknown scope {scope!r}")
        return self.buckets[scope]

    def _path(self, path: str) -> str:
        if not isinstance(path, str) or not _GENERATED_PATH.fullmatch(path):
            raise ApiError(404, "not_found", "file not found")
        return path

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.service_role_key, "Authorization": f"Bearer {self.service_role_key}"}

    def _request(self, method: str, url: str, **kwargs):
        try:
            return requests.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(503, "storage_unavailable", "File storage is unavailable") from exc

    def _check(self, response, *, not_found: bool = False) -> None:
        if 200 <= response.status_code < 300:
            return
        if not_found and response.status_code == 404:
            raise ApiError(404, "not_found", "file not found")
        raise ApiError(503, "storage_unavailable", "File storage is unavailable")

    def save(self, scope: str, stream: BinaryIO, max_bytes: int) -> StoredFile:
        bucket = self._bucket(scope)
        data, content_type, ext = read_image_upload(stream, max_bytes)
        name = uuid.uuid4().hex
        path = f"{name[:2]}/{name}.{ext}"
        response = self._request(
            "POST", f"{self.url}/object/{bucket}/{path}",
            headers={**self._headers(), "Content-Type": content_type, "x-upsert": "false"},
            data=data,
        )
        self._check(response)
        return StoredFile(scope=scope, path=path, content_type=content_type, size=len(data))

    def send(self, scope: str, path: str, content_type: str | None = None):
        bucket = self._bucket(scope)
        path = self._path(path)
        if scope == "private":
            _require_private_read(scope)
            url = f"{self.url}/object/authenticated/{bucket}/{path}"
            headers = self._headers()
        else:
            url = f"{self.url}/object/public/{bucket}/{path}"
            headers = {}
        response = self._request("GET", url, headers=headers)
        self._check(response, not_found=True)
        result = Response(response.content, mimetype=content_type or response.headers.get("Content-Type", "application/octet-stream"))
        result.headers["Cache-Control"] = "no-store" if scope == "private" else "public, max-age=3600"
        return result

    def delete(self, scope: str, path: str) -> None:
        bucket = self._bucket(scope)
        path = self._path(path)
        response = self._request(
            "DELETE", f"{self.url}/object/{bucket}",
            headers=self._headers(), json={"prefixes": [path]},
        )
        self._check(response)


def get_storage():
    config = current_app.config
    backend = config["STORAGE_BACKEND"]
    if backend == "local":
        return LocalStorage(config["UPLOAD_DIR"])
    if backend == "supabase":
        return SupabaseStorage(
            config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"],
            config["SUPABASE_PUBLIC_BUCKET"], config["SUPABASE_PRIVATE_BUCKET"],
            config["STORAGE_HTTP_TIMEOUT_SECONDS"],
        )
    raise RuntimeError(f"Unknown STORAGE_BACKEND {backend!r}")
