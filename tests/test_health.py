"""M1 HTTP contract checks."""


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}
