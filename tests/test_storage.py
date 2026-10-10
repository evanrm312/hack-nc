"""Storage helper: magic-byte detection, size cap, private-read authorization."""

import io

import pytest

from server.errors import ApiError
from server.storage import LocalStorage, SupabaseStorage, authorize_private_read, detect_image_type, read_image_upload


def test_detect_image_type():
    assert detect_image_type(b"\xff\xd8\xff\xe0" + b"\x00" * 12) == ("image/jpeg", "jpg")
    assert detect_image_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) == ("image/png", "png")
    assert detect_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == ("image/webp", "webp")
    assert detect_image_type(b"MZ\x90\x00" + b"\x00" * 12) is None
    assert detect_image_type(b"GIF89a" + b"\x00" * 10) is None  # GIF intentionally not accepted
    assert detect_image_type(b"") is None


def test_read_image_upload_rejects_renamed_executable():
    with pytest.raises(ApiError) as excinfo:
        read_image_upload(io.BytesIO(b"MZ\x90\x00" + b"\x00" * 100), max_bytes=1000)
    assert excinfo.value.status == 400
    assert excinfo.value.code == "unsupported_image"


def test_read_image_upload_enforces_size_cap():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000
    with pytest.raises(ApiError) as excinfo:
        read_image_upload(io.BytesIO(big), max_bytes=1000)
    assert excinfo.value.status == 413


def test_read_image_upload_rejects_empty():
    with pytest.raises(ApiError) as excinfo:
        read_image_upload(io.BytesIO(b""), max_bytes=1000)
    assert excinfo.value.status == 400


def test_local_storage_generates_names_and_separates_scopes(tmp_path):
    storage = LocalStorage(tmp_path)
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    public = storage.save("public", io.BytesIO(data), max_bytes=1000)
    private = storage.save("private", io.BytesIO(data), max_bytes=1000)
    assert public.path.endswith(".png") and private.path.endswith(".png")
    assert public.path != private.path
    assert (tmp_path / "public" / public.path).read_bytes() == data
    assert (tmp_path / "private" / private.path).read_bytes() == data
    assert not (tmp_path / "public" / private.path).exists()
    storage.delete("public", public.path)
    assert not (tmp_path / "public" / public.path).exists()


def test_local_storage_rejects_unknown_scope(tmp_path):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).save("secret", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8), 100)


def test_authorize_private_read():
    authorize_private_read("owner", {"owner", "requester"})
    for viewer in ("third-party", None):
        with pytest.raises(ApiError) as excinfo:
            authorize_private_read(viewer, {"owner", "requester"})
        assert excinfo.value.status == 403


def test_local_private_send_requires_participant_check(tmp_path, app):
    storage = LocalStorage(tmp_path)
    image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    saved = storage.save("private", io.BytesIO(image), 100)
    with app.test_request_context():
        with pytest.raises(ApiError) as denied:
            storage.send("private", saved.path)
        assert denied.value.status == 403
        authorize_private_read("owner", {"owner", "borrower"})
        response = storage.send("private", saved.path)
        response.direct_passthrough = False
        assert response.data == image


class ProviderResponse:
    def __init__(self, status_code=200, content=b"", content_type="image/png"):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}


def test_supabase_storage_public_upload_download_delete(monkeypatch, app):
    calls = []
    image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return ProviderResponse(content=image)

    monkeypatch.setattr("server.storage.requests.request", fake_request)
    storage = SupabaseStorage("https://example.supabase.co", "service-secret", timeout=7)
    saved = storage.save("public", io.BytesIO(image), 100)
    assert saved.scope == "public" and saved.content_type == "image/png" and saved.size == len(image)
    assert calls[0][0] == "POST"
    assert calls[0][1] == f"https://example.supabase.co/storage/v1/object/public-listings/{saved.path}"
    assert calls[0][2]["headers"]["Authorization"] == "Bearer service-secret"
    assert calls[0][2]["headers"]["x-upsert"] == "false"
    assert calls[0][2]["data"] == image
    assert calls[0][2]["timeout"] == 7

    with app.test_request_context():
        response = storage.send("public", saved.path)
    assert response.status_code == 200 and response.data == image
    assert "service-secret" not in str(response.headers)
    assert calls[1][1] == f"https://example.supabase.co/storage/v1/object/public/public-listings/{saved.path}"
    assert calls[1][2]["headers"] == {}

    storage.delete("public", saved.path)
    assert calls[2][0] == "DELETE"
    assert calls[2][1] == "https://example.supabase.co/storage/v1/object/public-listings"
    assert calls[2][2]["json"] == {"prefixes": [saved.path]}


def test_supabase_storage_private_requires_participant_check(monkeypatch, app):
    calls = []
    image = b"\xff\xd8\xff" + b"\x00" * 32
    monkeypatch.setattr("server.storage.requests.request", lambda method, url, **kwargs: (calls.append((method, url, kwargs)) or ProviderResponse(content=image, content_type="image/jpeg")))
    storage = SupabaseStorage("https://example.supabase.co", "service-secret")
    saved = storage.save("private", io.BytesIO(image), 100)
    assert "/object/private-evidence/" in calls[0][1]
    with app.test_request_context():
        with pytest.raises(ApiError) as blocked:
            storage.send("private", saved.path)
        assert blocked.value.status == 403
        with pytest.raises(ApiError):
            authorize_private_read("stranger", {"owner", "borrower"})
        assert len(calls) == 1
        authorize_private_read("owner", {"owner", "borrower"})
        response = storage.send("private", saved.path)
        assert response.data == image
        assert response.headers["Cache-Control"] == "no-store"
    assert calls[1][1] == f"https://example.supabase.co/storage/v1/object/authenticated/private-evidence/{saved.path}"
    assert calls[1][2]["headers"]["Authorization"] == "Bearer service-secret"


def test_supabase_storage_rejects_invalid_paths_and_provider_errors(monkeypatch, app):
    storage = SupabaseStorage("https://example.supabase.co", "service-secret")
    with app.test_request_context():
        with pytest.raises(ApiError) as bad_path:
            storage.send("public", "../private-evidence/file.jpg")
        assert bad_path.value.status == 404
    with pytest.raises(ValueError):
        storage.save("other", io.BytesIO(b"\x89PNG\r\n\x1a\n"), 100)
    monkeypatch.setattr("server.storage.requests.request", lambda *_args, **_kwargs: ProviderResponse(status_code=503))
    with pytest.raises(ApiError) as unavailable:
        storage.save("public", io.BytesIO(b"\x89PNG\r\n\x1a\n"), 100)
    assert unavailable.value.status == 503
    monkeypatch.setattr("server.storage.requests.request", lambda *_args, **_kwargs: ProviderResponse(status_code=404))
    with app.test_request_context():
        with pytest.raises(ApiError) as missing:
            storage.send("public", "ab/" + "a" * 32 + ".png")
    assert missing.value.status == 404
