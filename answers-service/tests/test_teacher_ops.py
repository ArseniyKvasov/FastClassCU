import uuid

from tests.conftest import make_token

FAKE_KEY = {
    "task_type": "test",
    "answer_key": {
        "questions": [{"question": "2+2?", "options": ["3", "4"], "correct_index": 1}]
    },
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _patch_answer_key(monkeypatch, task_id, content_id=None):
    import app.services.content_client as content_client

    key = dict(FAKE_KEY)
    key["task_id"] = str(task_id)
    key["content_id"] = str(content_id or uuid.uuid4())

    async def fake_get_answer_key(r, *, task_id):
        return key

    monkeypatch.setattr(content_client, "get_answer_key", fake_get_answer_key)


def _patch_teacher(monkeypatch, teacher_id):
    import app.routers.answers as answers_router

    async def fake_get_context_teacher_id(context_type, context_id, token):
        return teacher_id

    monkeypatch.setattr(answers_router, "get_context_teacher_id", fake_get_context_teacher_id)


def _submit(c, token, task_id, context_type, context_id, selected_index=1):
    return c.post(
        "/answers",
        json={
            "task_id": str(task_id),
            "context_type": context_type,
            "context_id": str(context_id),
            "payload": {"answers": [{"question_index": 0, "selected_index": selected_index}]},
        },
        headers=_auth(token),
    )


def test_teacher_can_list_answers_for_context(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    context_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    teacher_id = uuid.uuid4()
    teacher_token = make_token(teacher_id)
    _patch_teacher(monkeypatch, teacher_id)

    student_token = make_token()
    _submit(c, student_token, task_id, "classroom", context_id)

    r = c.get(
        "/answers", params={"context_type": "classroom", "context_id": str(context_id)},
        headers=_auth(teacher_token),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_non_teacher_cannot_list_answers(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    context_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)
    _patch_teacher(monkeypatch, uuid.uuid4())  # some OTHER teacher

    student_token = make_token()
    _submit(c, student_token, task_id, "classroom", context_id)

    r = c.get(
        "/answers", params={"context_type": "classroom", "context_id": str(context_id)},
        headers=_auth(student_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "teacher_only"


def test_teacher_can_set_manual_score(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    context_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    teacher_id = uuid.uuid4()
    teacher_token = make_token(teacher_id)
    _patch_teacher(monkeypatch, teacher_id)

    student_token = make_token()
    answer = _submit(c, student_token, task_id, "classroom", context_id).json()

    r = c.patch(
        f"/answers/{answer['id']}/score", json={"score": 90.0}, headers=_auth(teacher_token)
    )
    assert r.status_code == 200
    assert r.json()["manual_score"] == 90.0


def test_teacher_can_reset_answer(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    context_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    teacher_id = uuid.uuid4()
    teacher_token = make_token(teacher_id)
    _patch_teacher(monkeypatch, teacher_id)

    student_token = make_token()
    answer = _submit(c, student_token, task_id, "classroom", context_id).json()

    r = c.delete(f"/answers/{answer['id']}", headers=_auth(teacher_token))
    assert r.status_code == 204

    r = c.get(
        "/answers/mine",
        params={"task_id": str(task_id), "context_type": "classroom", "context_id": str(context_id)},
        headers=_auth(student_token),
    )
    assert r.json() is None


def test_student_can_read_own_answer(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    context_id = uuid.uuid4()
    _patch_answer_key(monkeypatch, task_id)

    student_token = make_token()
    _submit(c, student_token, task_id, "classroom", context_id)

    r = c.get(
        "/answers/mine",
        params={"task_id": str(task_id), "context_type": "classroom", "context_id": str(context_id)},
        headers=_auth(student_token),
    )
    assert r.status_code == 200
    assert r.json() is not None
