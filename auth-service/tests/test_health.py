def test_ready_reports_db_and_keys_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["jwt_keys"] == "ok"
