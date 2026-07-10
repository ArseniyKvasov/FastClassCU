import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_assignment_and_session_lifecycle_emits_events(api_client):
    c = api_client
    teacher_token = make_token()
    body = {
        "title": "HW",
        "lesson_id": str(uuid.uuid4()),
        "target_type": "link",
        "tasks": [{"task_id": str(uuid.uuid4()), "weight": 100}],
    }
    assignment = c.post("/assignments", json=body, headers=_auth(teacher_token)).json()

    student_token = make_token()
    session = c.post(
        f"/assignments/{assignment['id']}/sessions", headers=_auth(student_token)
    ).json()
    c.post(f"/sessions/{session['id']}/submit", headers=_auth(student_token))
    c.patch(
        f"/sessions/{session['id']}/grade", json={"grade": 88}, headers=_auth(teacher_token)
    )
    c.delete(f"/assignments/{assignment['id']}", headers=_auth(teacher_token))

    import asyncio

    from app.config import settings
    from app.services import events as events_svc
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    async def _check():
        engine = create_async_engine(settings.database_url)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
        async with SessionLocal() as db:
            events = await events_svc.list_unpublished_events(db, limit=100)
            types = [
                e.event_type
                for e in events
                if e.payload.get("assignment_id") == assignment["id"]
                or e.payload.get("session_id") == session["id"]
            ]
        await engine.dispose()
        return types

    types = asyncio.run(_check())
    assert "assignment_created" in types
    assert "session_started" in types
    assert "session_submitted" in types
    assert "session_grade_overridden" in types
    assert "assignment_deleted" in types


async def test_mark_published_excludes_from_next_poll(db_session):
    from app.services import events as events_svc

    await events_svc.emit_event(db_session, event_type="assignment_created", payload={"x": 1})
    await db_session.commit()

    pending = await events_svc.list_unpublished_events(db_session)
    assert len(pending) >= 1

    await events_svc.mark_published(db_session, [e.id for e in pending])
    await db_session.commit()

    still_pending = await events_svc.list_unpublished_events(db_session)
    assert still_pending == []
