def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_public_key(client):
    r = client.get("/auth/public-key")
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "RS256"
    assert "BEGIN PUBLIC KEY" in body["public_key"]


def test_list_providers(client):
    r = client.get("/auth/providers")
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()}
    assert keys == {"testprovider"}
