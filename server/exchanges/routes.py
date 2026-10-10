"""Person 4 endpoints: STUBS created by Person 1. Replace in place.

Reads return labeled fixtures (``"fixture": true``). Writes return
501 not_implemented in the standard error shape, because a fake 200 from
/accept or /handoff would be an invented transaction.

All endpoints already require a verified user, matching the final contract.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import require_verified_user
from ..errors import ApiError
from .fixtures import FIXTURE_EVIDENCE, FIXTURE_EXCHANGE, FIXTURE_MESSAGES, exchange_detail_fixture

bp = Blueprint("exchanges", __name__, url_prefix="/api/exchanges")


def _not_implemented(action: str):
    raise ApiError(501, "not_implemented", f"{action} is not implemented yet (Person 4)")


@bp.get("")
@require_verified_user
def list_exchanges():
    return jsonify({"fixture": True, "exchanges": [FIXTURE_EXCHANGE]})


@bp.post("")
@require_verified_user
def create_exchange():
    _not_implemented("POST /api/exchanges")


@bp.get("/<exchange_id>")
@require_verified_user
def get_exchange(exchange_id: str):
    return jsonify(exchange_detail_fixture())


@bp.get("/<exchange_id>/messages")
@require_verified_user
def list_messages(exchange_id: str):
    return jsonify({"fixture": True, "messages": FIXTURE_MESSAGES})


@bp.post("/<exchange_id>/messages")
@require_verified_user
def post_message(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/messages")


@bp.post("/<exchange_id>/offers")
@require_verified_user
def post_offer(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/offers")


@bp.post("/<exchange_id>/accept")
@require_verified_user
def accept_offer(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/accept")


@bp.get("/<exchange_id>/evidence")
@require_verified_user
def list_evidence(exchange_id: str):
    return jsonify({"fixture": True, "evidence": FIXTURE_EVIDENCE})


@bp.post("/<exchange_id>/evidence")
@require_verified_user
def upload_evidence(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/evidence")


@bp.get("/<exchange_id>/evidence/<evidence_id>")
@require_verified_user
def get_evidence_file(exchange_id: str, evidence_id: str):
    _not_implemented("GET /api/exchanges/{id}/evidence/{evidence_id}")


@bp.post("/<exchange_id>/handoff")
@require_verified_user
def confirm_handoff(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/handoff")


@bp.post("/<exchange_id>/return")
@require_verified_user
def confirm_return(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/return")


@bp.post("/<exchange_id>/review")
@require_verified_user
def post_review(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/review")


@bp.post("/<exchange_id>/cancel")
@require_verified_user
def cancel_exchange(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/cancel")


@bp.post("/<exchange_id>/dispute")
@require_verified_user
def dispute_exchange(exchange_id: str):
    _not_implemented("POST /api/exchanges/{id}/dispute")
