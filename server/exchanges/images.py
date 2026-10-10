"""Decode private condition photos before using the shared storage helper."""

import base64
from io import BytesIO
import warnings

from ..errors import ApiError
from ..storage import read_image_upload

MAX_IMAGE_PIXELS = 16_000_000


def _decode(data):
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        raise ApiError(503, "image_validation_unavailable", "Image uploads need the Pillow dependency installed") from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ApiError(400, "unsupported_image", "Photo must be at most 16 megapixels", {"photo": "reduce image dimensions"})
                if getattr(image, "n_frames", 1) != 1:
                    raise ApiError(400, "unsupported_image", "Choose a still photo rather than an animation")
                image.verify()
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                image.load()  # A valid signature/header alone is insufficient.
                with ImageOps.exif_transpose(image) as oriented:
                    return oriented.copy()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ApiError(400, "unsupported_image", "The file is not a complete, valid JPEG, PNG, or WebP photo", {"photo": "invalid image content"}) from None


def validated_image_stream(stream, max_bytes):
    data, _, _ = read_image_upload(stream, max_bytes)
    with _decode(data):
        pass
    return BytesIO(data)


def private_preview(data):
    with _decode(data) as image:
        image.thumbnail((480, 480))
        with image.convert("RGB") as preview:
            output = BytesIO()
            preview.save(output, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
