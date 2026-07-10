import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


FAKE_KEY = {
    "task_id": None,
    "content_id": None,
    "task_type": "test",
    "answer_key": {
        "questions": [
            {"question": "2+2?", "options": ["3", "4"], "correct_index": 1},
            {"question": "3+3?", "options": ["6", "7"], "correct_index": 0},
        ]
    },
}


def _patch_answer_key(monkeypatch, task_id, content_id=None):
    import app.services.content_client as content_client

    key = dict(FAKE_KEY)
    key["task_id"] = str(task_id)
    key["content_id"] = str(content_id or uuid.uuid4())

    async def fake_get_answer_key(r, *, task_id):
        return key

    monkeypatch.setattr(content_client, "get_answer_key", fake_get_answer_key)
    return key


def test_submit_answer_scores_objective_task(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    student_token = make_token()
    body = {
        "task_id": str(task_id),
        "context_type": "classroom",
        "context_id": str(uuid.uuid4()),
        "payload": {
            "answers": [
                {"question_index": 0, "selected_index": 1},  # correct
                {"question_index": 1, "selected_index": 1},  # wrong
            ]
        },
    }
    r = c.post("/answers", json=body, headers=_auth(student_token))
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["correct_count"] == 1
    assert answer["wrong_count"] == 1
    assert answer["is_checked"] is True
    assert answer["auto_score"] == 50.0


def test_same_task_different_context_creates_separate_rows(api_client, monkeypatch):
    """The core keying guarantee: a live-classroom answer and a homework
    answer for the same task+student are two different rows, not one."""
    c = api_client
    task_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    student_token = make_token()
    classroom_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    payload = {"answers": [{"question_index": 0, "selected_index": 1}]}

    r1 = c.post(
        "/answers",
        json={
            "task_id": str(task_id),
            "context_type": "classroom",
            "context_id": classroom_id,
            "payload": payload,
        },
        headers=_auth(student_token),
    )
    r2 = c.post(
        "/answers",
        json={
            "task_id": str(task_id),
            "context_type": "assignment",
            "context_id": session_id,
            "payload": payload,
        },
        headers=_auth(student_token),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


def test_resubmit_updates_same_row(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    student_token = make_token()
    context_id = str(uuid.uuid4())

    r1 = c.post(
        "/answers",
        json={
            "task_id": str(task_id),
            "context_type": "classroom",
            "context_id": context_id,
            "payload": {"answers": [{"question_index": 0, "selected_index": 0}]},
        },
        headers=_auth(student_token),
    )
    r2 = c.post(
        "/answers",
        json={
            "task_id": str(task_id),
            "context_type": "classroom",
            "context_id": context_id,
            "payload": {"answers": [{"question_index": 0, "selected_index": 1}]},
        },
        headers=_auth(student_token),
    )
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["correct_count"] == 0
    assert r2.json()["correct_count"] == 1


async def test_assignment_context_emits_answer_scored(db_session, monkeypatch):
    from app.models import ContextType
    from app.services import answers as answers_svc
    from app.services import events as events_svc

    task_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    await answers_svc.submit_answer(
        db_session,
        None,
        task_id=task_id,
        user_id=uuid.uuid4(),
        context_type=ContextType.assignment,
        context_id=uuid.uuid4(),
        payload={"answers": [{"question_index": 0, "selected_index": 1}]},
    )
    await db_session.commit()
    events = await events_svc.list_unpublished_events(db_session)
    types = [e.event_type for e in events]

    assert "answer_updated" in types
    assert "answer_scored" in types


async def test_classroom_context_does_not_emit_answer_scored(db_session, monkeypatch):
    from app.models import ContextType
    from app.services import answers as answers_svc
    from app.services import events as events_svc

    task_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    await answers_svc.submit_answer(
        db_session,
        None,
        task_id=task_id,
        user_id=uuid.uuid4(),
        context_type=ContextType.classroom,
        context_id=uuid.uuid4(),
        payload={"answers": [{"question_index": 0, "selected_index": 1}]},
    )
    await db_session.commit()
    events = await events_svc.list_unpublished_events(db_session)
    types = [e.event_type for e in events]

    assert "answer_updated" in types
    assert "answer_scored" not in types
