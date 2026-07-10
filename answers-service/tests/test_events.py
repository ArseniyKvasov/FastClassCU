from app.services import events as events_svc


async def test_mark_published_excludes_from_next_poll(db_session):
    await events_svc.emit_event(db_session, event_type="answer_updated", payload={"x": 1})
    await db_session.commit()

    pending = await events_svc.list_unpublished_events(db_session)
    assert len(pending) >= 1

    await events_svc.mark_published(db_session, [e.id for e in pending])
    await db_session.commit()

    still_pending = await events_svc.list_unpublished_events(db_session)
    assert still_pending == []
