"""Uniform JSON error shape for every /api/* response.

    {"error": {"code": "...", "message": "...", "fields": {}}}

Raise ``ApiError`` anywhere inside a request; ``register_error_handlers``
turns it (and any Werkzeug HTTP error under /api/) into that shape.
"""

from __future__ import annotations

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}

    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message, "fields": self.fields}}
        return jsonify(body), self.status


def not_found(what: str = "resource") -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


def forbidden(message: str = "You do not have permission to do that") -> ApiError:
    return ApiError(403, "forbidden", message)


def validation_error(fields: dict, message: str = "Invalid request") -> ApiError:
    return ApiError(400, "validation_error", message, fields)


_HTTP_CODES = {
    400: "bad_request",
    401: "auth_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    500: "internal_error",
    501: "not_implemented",
}


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.path.startswith("/media/")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return err.to_response()

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        if not _wants_json():
            return err
        code = _HTTP_CODES.get(err.code or 500, "http_error")
        body = {"error": {"code": code, "message": err.description or err.name, "fields": {}}}
        return jsonify(body), err.code or 500

    @app.errorhandler(Exception)
    def _unhandled(err: Exception):
        if not _wants_json():
            raise err
        app.logger.exception("Unhandled error on %s", request.path)
        body = {"error": {"code": "internal_error", "message": "Internal server error", "fields": {}}}
        return jsonify(body), 500
