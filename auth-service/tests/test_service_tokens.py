from app.security import verify_token


def test_issue_service_token(client):
    response = client.post(
        "/auth/service-token",
        data={
            "grant_type": "client_credentials",
            "client_id": "answers-service",
            "client_secret": "answers-secret",
            "scope": "content:answer-key:read",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    claims = verify_token(body["access_token"])
    assert claims["sub"] == "answers-service"
    assert claims["token_use"] == "service"
    assert claims["scope"] == "content:answer-key:read"
    assert claims["access_level"] == "service"


def test_service_token_rejects_scope_escalation(client):
    response = client.post(
        "/auth/service-token",
        data={
            "grant_type": "client_credentials",
            "client_id": "answers-service",
            "client_secret": "answers-secret",
            "scope": "content:answer-key:read forbidden:scope",
        },
    )
    assert response.status_code == 403
