"""Storage helper: magic-byte detection, size cap, private-read authorization."""

import io

import pytest

from server.errors import ApiError
from server.storage import LocalStorage, authorize_private_read, detect_image_type, read_image_upload


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
