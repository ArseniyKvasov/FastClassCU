import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _patch_voice_key(monkeypatch, task_id):
    import app.services.content_client as content_client

    key = {
        "task_id": str(task_id),
        "content_id": str(uuid.uuid4()),
        "task_type": "voice_recording",
        "answer_key": {},
    }

    async def fake_get_answer_key(r, *, task_id):
        return key

    monkeypatch.setattr(content_client, "get_answer_key", fake_get_answer_key)


def _upload_voice(c, token, task_id, context_type, context_id, audio_bytes=b"fake-audio-bytes"):
    return c.post(
        "/answers/voice",
        data={
            "task_id": str(task_id),
            "context_type": context_type,
            "context_id": str(context_id),
            "duration_seconds": "12.5",
        },
        files={"audio": ("recording.mp3", audio_bytes, "audio/mpeg")},
        headers=_auth(token),
    )


def test_voice_upload_creates_answer_with_file(api_client, monkeypatch):
    c = api_client
    task_id = uuid.uuid4()
    _patch_voice_key(monkeypatch, task_id)

    student_token = make_token()
    r = _upload_voice(c, student_token, task_id, "classroom", uuid.uuid4())
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["task_type"] == "voice_recording"
    assert answer["is_checked"] is False
    assert answer["payload"]["duration_seconds"] == 12.5


def test_identical_audio_bytes_dedupe_to_one_file(api_client, monkeypatch):
    """Content-addressable: uploading the same bytes twice (e.g. two
    different tasks) must not create two blobs."""
    c = api_client
    task_a, task_b = uuid.uuid4(), uuid.uuid4()
    _patch_voice_key(monkeypatch, task_a)
    _patch_voice_key(monkeypatch, task_b)

    student_token = make_token()
    same_bytes = b"identical-audio-content"
    context_id = uuid.uuid4()
    r1 = _upload_voice(c, student_token, task_a, "classroom", context_id, same_bytes)
    r2 = _upload_voice(c, student_token, task_b, "classroom", context_id, same_bytes)
    assert r1.status_code == 200 and r2.status_code == 200


def test_quota_deletes_oldest_answer_when_exceeded(api_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "student_answer_limit_bytes", 10)  # tiny, forces eviction

    c = api_client
    task_a, task_b = uuid.uuid4(), uuid.uuid4()
    _patch_voice_key(monkeypatch, task_a)
    _patch_voice_key(monkeypatch, task_b)

    student_token = make_token()
    context_id = uuid.uuid4()

    r1 = _upload_voice(c, student_token, task_a, "classroom", context_id, b"first-answer-bytes")
    assert r1.status_code == 200
    answer_a_id = r1.json()["id"]

    r2 = _upload_voice(c, student_token, task_b, "classroom", context_id, b"second-answer-bytes")
    assert r2.status_code == 200

    # The oldest (task_a's) answer should have been evicted by quota enforcement.
    r_check = c.get(
        "/answers/mine",
        params={"task_id": str(task_a), "context_type": "classroom", "context_id": str(context_id)},
        headers=_auth(student_token),
    )
    assert r_check.json() is None


def test_gc_reclaims_file_after_teacher_reset_but_not_while_referenced(api_client, monkeypatch):
    import app.routers.answers as answers_router

    c = api_client
    task_id = uuid.uuid4()
    _patch_voice_key(monkeypatch, task_id)

    teacher_id = uuid.uuid4()

    async def fake_get_context_teacher_id(context_type, context_id, token):
        return teacher_id

    monkeypatch.setattr(answers_router, "get_context_teacher_id", fake_get_context_teacher_id)

    student_token = make_token()
    context_id = uuid.uuid4()
    answer = _upload_voice(c, student_token, task_id, "classroom", context_id).json()

    # Referenced - GC must not touch it.
    r = c.post("/admin/gc")
    assert r.status_code == 200
    assert r.json()["reclaimed_files"] == 0

    teacher_token = make_token(teacher_id)
    r = c.delete(f"/answers/{answer['id']}", headers=_auth(teacher_token))
    assert r.status_code == 204

    # Now unreferenced - GC reclaims it.
    r = c.post("/admin/gc")
    assert r.json()["reclaimed_files"] == 1
