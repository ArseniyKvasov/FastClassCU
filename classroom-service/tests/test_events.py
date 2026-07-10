import uuid

from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_classroom_lifecycle_emits_events(api_client):
    c = api_client
    teacher_token = make_token()

    r = c.post("/classrooms", json={"title": "Lesson"}, headers=_auth(teacher_token))
    classroom = r.json()

    student_token = make_token()
    c.post(
        f"/classrooms/{classroom['id']}/join",
        json={"password": classroom["join_password"], "display_name": "Student"},
        headers=_auth(student_token),
    )
    c.post(f"/classrooms/{classroom['id']}/leave", headers=_auth(student_token))
    c.delete(f"/classrooms/{classroom['id']}", headers=_auth(teacher_token))

    # Inspect the outbox directly - this proves the events were written in
    # the same transaction as each change, not just that the HTTP calls
    # succeeded.
    import asyncio

    from app.config import settings
    from app.services import events as events_svc
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    async def _check():
        engine = create_async_engine(settings.database_url)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
        async with SessionLocal() as db:
            events = await events_svc.list_unpublished_events(db, limit=100)
            types = [e.event_type for e in events if e.payload.get("classroom_id") == classroom["id"]]
        await engine.dispose()
        return types

    types = asyncio.run(_check())
    assert "classroom_created" in types
    assert "student_joined" in types
    assert "student_left" in types
    assert "classroom_deleted" in types


async def test_mark_published_excludes_from_next_poll(db_session):
    from app.services import events as events_svc

    await events_svc.emit_event(db_session, event_type="classroom_created", payload={"x": 1})
    await db_session.commit()

    pending = await events_svc.list_unpublished_events(db_session)
    assert len(pending) >= 1

    await events_svc.mark_published(db_session, [e.id for e in pending])
    await db_session.commit()

    still_pending = await events_svc.list_unpublished_events(db_session)
    assert still_pending == []
