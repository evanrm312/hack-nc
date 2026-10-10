"""Every /api/* failure uses {"error": {"code", "message", "fields"}}."""


def _assert_error_shape(resp, status, code=None):
    assert resp.status_code == status
    body = resp.get_json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "fields"}
    if code:
        assert body["error"]["code"] == code


def test_api_404_is_json(client):
    _assert_error_shape(client.get("/api/does-not-exist"), 404, "not_found")
    _assert_error_shape(client.get("/api/listings/nope"), 404, "not_found")


def test_api_405_is_json(client):
    _assert_error_shape(client.delete("/api/me"), 405, "method_not_allowed")


def test_malformed_json_is_400(client, alice):
    resp = client.post("/api/listings", data="{not json", content_type="application/json", headers=alice)
    _assert_error_shape(resp, 400, "invalid_json")
    resp = client.post("/api/listings", json=[1, 2], headers=alice)
    _assert_error_shape(resp, 400, "invalid_json")


def test_html_404_outside_api_stays_html(client):
    resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert resp.get_json() is None


def test_healthz_and_pages_render(client):
    assert client.get("/healthz").get_json()["ok"] is True
    for path in ("/", "/sign-in", "/requests", "/listings/new", "/listings/abc", "/results/abc", "/exchanges", "/exchanges/abc"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert b"Campus Current" in resp.data
    sign_in = client.get("/sign-in").data
    assert b"Sandbox sign-in" in sign_in
    assert b"service_role" not in sign_in


def test_exchange_auth_and_error_contract(client, alice):
    assert client.get("/api/exchanges").status_code == 401
    listed = client.get("/api/exchanges", headers=alice).get_json()
    if listed.get("fixture") is True:
        # Main's scaffold remains valid until the exchange PR lands.
        assert listed["exchanges"][0]["id"].startswith("fixture-")
        _assert_error_shape(client.post("/api/exchanges", json={}, headers=alice), 501, "not_implemented")
    else:
        assert listed == {"exchanges": []}
        _assert_error_shape(client.get("/api/exchanges/anything", headers=alice), 404, "not_found")
        _assert_error_shape(client.get("/api/exchanges/anything/messages", headers=alice), 404, "not_found")
        _assert_error_shape(client.post("/api/exchanges", json={}, headers=alice), 400, "validation_error")
