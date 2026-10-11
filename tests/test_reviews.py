"""Participant-only structured reviews after actual pickup/return completion."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from server.db import db
from server.models import Exchange, Review
from server.models.review import REVIEW_FIELDS
from tests.test_exchanges import (
    handoff, pending_return, photo_upload, ready_exchange,
    reserved_exchange, return_action, spot, third_party,
)


def review_body(**overrides):
    return {"stars": 4, "structured_answers": {field: "not_applicable" for field in REVIEW_FIELDS},
            "comment": "Clear communication.", **overrides}


def completed_exchange(client, alice, bob, spot, mode="sale"):
    if mode == "sale":
        exchange = reserved_exchange(client, alice, bob, spot, mode=mode)
        assert photo_upload(client, exchange["id"], alice).status_code == 201
        assert handoff(client, exchange["id"], alice).status_code == 200
        assert handoff(client, exchange["id"], bob).get_json()["exchange"]["status"] == "completed"
    else:
        exchange = pending_return(client, alice, bob, spot)
        assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
        assert return_action(client, exchange["id"], alice, "accept").status_code == 200
        assert return_action(client, exchange["id"], bob, "accept").get_json()["exchange"]["status"] == "completed"
    return exchange


@pytest.mark.parametrize("mode", ["sale", "borrow"])
def test_only_completed_participants_review_and_identity_is_server_derived(client, alice, bob, third_party, spot, mode):
    exchange = completed_exchange(client, alice, bob, spot, mode)
    url = f"/api/exchanges/{exchange['id']}/review"
    assert client.post(url, json=review_body()).status_code == 401
    assert client.post(url, headers=third_party, json=review_body()).status_code == 403
    for headers, reviewer_id, reviewee_id in ((alice, exchange["owner_id"], exchange["requester_id"]),
                                            (bob, exchange["requester_id"], exchange["owner_id"])):
        response = client.post(url, headers=headers, json=review_body(reviewer_id="forged", reviewee_id="forged"))
        assert response.status_code == 201
        review = response.get_json()["review"]
        assert review["reviewer_id"] == reviewer_id and review["reviewee_id"] == reviewee_id
        assert all(answer == "not_applicable" for answer in review["structured_answers"].values())
        row = client.get("/api/exchanges", headers=headers).get_json()["exchanges"][0]
        assert row["my_review"] == review and row["can_review"] is False
        assert client.post(url, headers=headers, json=review_body()).get_json()["error"]["code"] == "already_reviewed"
    assert len(db.session.scalars(db.select(Review)).all()) == 2


@pytest.mark.parametrize("status", ["negotiating", "reserved", "on_loan", "return_pending", "disputed", "cancelled"])
def test_review_rejects_every_incomplete_state(client, alice, bob, spot, status):
    exchange = ready_exchange(client, alice, bob, spot)
    db.session.get(Exchange, exchange["id"]).status = status
    db.session.commit()
    response = client.post(f"/api/exchanges/{exchange['id']}/review", headers=bob, json=review_body())
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "exchange_not_completed"
    assert db.session.scalar(db.select(Review)) is None


def test_loan_review_waits_for_both_return_confirmations(client, alice, bob, spot):
    exchange = pending_return(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
    assert return_action(client, exchange["id"], alice, "accept").status_code == 200
    assert client.post(f"/api/exchanges/{exchange['id']}/review", headers=alice, json=review_body()).status_code == 409
    assert return_action(client, exchange["id"], bob, "accept").status_code == 200
    assert client.post(f"/api/exchanges/{exchange['id']}/review", headers=alice, json=review_body()).status_code == 201


@pytest.mark.parametrize("override", [
    {"stars": True}, {"stars": 1.5}, {"stars": "5"}, {"stars": 0}, {"stars": 6},
    {"structured_answers": None}, {"structured_answers": []}, {"structured_answers": {}},
    {"structured_answers": {field: "maybe" for field in REVIEW_FIELDS}},
    {"structured_answers": {field: "yes" for field in REVIEW_FIELDS}},
    {"comment": 42}, {"comment": "x" * 2001},
])
def test_invalid_review_does_not_create_a_record(client, alice, bob, spot, override):
    exchange = completed_exchange(client, alice, bob, spot)
    response = client.post(f"/api/exchanges/{exchange['id']}/review", headers=bob, json=review_body(**override))
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "validation_error"
    assert db.session.scalar(db.select(Review)) is None
    assert client.get("/api/exchanges", headers=bob).get_json()["exchanges"][0]["can_review"] is True


def test_simultaneous_duplicate_review_records_only_one(app, client, alice, bob, spot):
    exchange = completed_exchange(client, alice, bob, spot)
    barrier = Barrier(2)

    def submit():
        with app.test_client() as independent_client:
            barrier.wait(timeout=5)
            return independent_client.post(f"/api/exchanges/{exchange['id']}/review", headers=bob,
                                           json=review_body()).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit), pool.submit(submit)]
        assert sorted(future.result(timeout=15) for future in futures) == [201, 409]
    assert len(db.session.scalars(db.select(Review)).all()) == 1
