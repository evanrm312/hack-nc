"""Labeled fixture payloads for the Person 4 endpoints until they are real.

Every payload carries ``"fixture": true`` and ids prefixed ``fixture-`` so no
UI or test can mistake them for persisted records. Shapes match
docs/contracts.md exactly; keep them in sync if the contract changes.
"""

from __future__ import annotations

SIMULATION_NOTICE = "Simulated: no real funds are reserved or charged."

FIXTURE_EXCHANGE = {
    "id": "fixture-exchange-1",
    "listing_id": "fixture-listing-1",
    "owner_id": "fixture-profile-owner",
    "requester_id": "fixture-profile-requester",
    "source_request_id": "fixture-request-1",
    "mode": "borrow",
    "status": "negotiating",
    "current_offer_revision": 2,
    "cancellation_reason": None,
    "dispute_reason": None,
    "created_at": "2026-10-10T15:00:00Z",
    "updated_at": "2026-10-10T15:20:00Z",
}

FIXTURE_OFFER = {
    "id": "fixture-offer-2",
    "exchange_id": "fixture-exchange-1",
    "version": 2,
    "created_by": "fixture-profile-requester",
    "sale_price_cents": None,
    "rental_fee_cents": 1500,
    "agreed_item_value_cents": 20000,
    "deposit_cents": 6000,
    "uncovered_value_cents": 14000,
    "lower_deposit_acknowledged": False,
    "condition_snapshot": {"condition": "good", "accessories": ["garment bag"], "known_defects": []},
    "pickup_meeting_spot_id": "fixture-spot-1",
    "pickup_at": "2026-10-12T18:00:00Z",
    "return_meeting_spot_id": "fixture-spot-1",
    "return_deadline": "2026-10-15T22:00:00Z",
    "pricing_range_version": None,
    "price_reference_id": None,
    "owner_accepted_at": None,
    "requester_accepted_at": "2026-10-10T15:20:00Z",
    "created_at": "2026-10-10T15:20:00Z",
}

FIXTURE_MESSAGES = [
    {
        "id": "fixture-message-1",
        "exchange_id": "fixture-exchange-1",
        "sender_id": "fixture-profile-requester",
        "body": "Hi! Is the suit available Monday through Wednesday?",
        "created_at": "2026-10-10T15:05:00Z",
    },
    {
        "id": "fixture-message-2",
        "exchange_id": "fixture-exchange-1",
        "sender_id": "fixture-profile-owner",
        "body": "Yes. I can meet at the Union after 2pm.",
        "created_at": "2026-10-10T15:07:00Z",
    },
]

FIXTURE_EVIDENCE = [
    {
        "id": "fixture-evidence-1",
        "exchange_id": "fixture-exchange-1",
        "uploader_id": "fixture-profile-owner",
        "stage": "pre_handoff",
        "content_type": "image/jpeg",
        "acknowledged_by": {},
        "url": "/api/exchanges/fixture-exchange-1/evidence/fixture-evidence-1",
        "created_at": "2026-10-12T17:50:00Z",
    }
]


def exchange_detail_fixture() -> dict:
    return {
        "fixture": True,
        "simulation_notice": SIMULATION_NOTICE,
        "exchange": FIXTURE_EXCHANGE,
        "current_offer": FIXTURE_OFFER,
        "offers": [FIXTURE_OFFER],
        "deposit_status": {"state": "simulated_pending", "label": SIMULATION_NOTICE},
        "participants": {
            "owner": {"id": "fixture-profile-owner", "display_name": "Demo Lender", "badge": "Sandbox identity (not verified)"},
            "requester": {"id": "fixture-profile-requester", "display_name": "Demo Borrower", "badge": "Sandbox identity (not verified)"},
        },
    }
