"""M1 HTTP contract checks."""


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json() == {
        "error": {
            "code": "not_found",
            "message": "API route not found.",
            "fields": {},
        }
    }
