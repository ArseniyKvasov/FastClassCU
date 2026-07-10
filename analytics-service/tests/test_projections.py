import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import PlatformOverviewDaily, UserActivityDaily
from app.services import projections
from fastclass_shared.events import EventEnvelope


def _event(
    *,
    producer: str,
    event_type: str,
    payload: dict,
    event_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id or str(uuid.uuid4()),
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        producer=producer,
        payload=payload,
    )


async def test_apply_event_aggregates_core_and_ai_metrics(db_session):
    teacher_id = uuid.uuid4()
    student_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    session_id = uuid.uuid4()
    ai_user_id = uuid.uuid4()

    events = [
        _event(
            producer="content-service",
            event_type="lesson_created",
            payload={"lesson_id": str(lesson_id), "owner_id": str(teacher_id)},
        ),
        _event(
            producer="assignments-service",
            event_type="assignment_created",
            payload={
                "assignment_id": str(assignment_id),
                "teacher_id": str(teacher_id),
                "lesson_id": str(lesson_id),
                "target_type": "classroom",
                "target_classroom_id": None,
            },
        ),
        _event(
            producer="assignments-service",
            event_type="session_started",
            payload={
                "session_id": str(session_id),
                "assignment_id": str(assignment_id),
                "student_id": str(student_id),
            },
        ),
        _event(
            producer="answers-service",
            event_type="answer_scored",
            payload={"session_id": str(session_id), "correctness": 87.5},
        ),
        _event(
            producer="ai-assistant-service",
            event_type="generation_requested",
            payload={
                "job_id": str(uuid.uuid4()),
                "requester_id": str(ai_user_id),
                "intent": "generate_image",
            },
        ),
        _event(
            producer="ai-assistant-service",
            event_type="generation_succeeded",
            payload={
                "job_id": str(uuid.uuid4()),
                "requester_id": str(ai_user_id),
                "intent": "generate_image",
                "provider": "pollinations",
                "artifact_type": "image",
            },
        ),
        _event(
            producer="ai-assistant-service",
            event_type="generation_failed",
            payload={
                "job_id": str(uuid.uuid4()),
                "requester_id": str(ai_user_id),
                "intent": "generate_audio",
                "error_code": "generation_failed",
            },
        ),
    ]

    for envelope in events:
        await projections.apply_event(db_session, envelope)

    teacher_row = await db_session.scalar(
        select(UserActivityDaily).where(UserActivityDaily.user_id == teacher_id)
    )
    student_row = await db_session.scalar(
        select(UserActivityDaily).where(UserActivityDaily.user_id == student_id)
    )
    ai_row = await db_session.scalar(
        select(UserActivityDaily).where(UserActivityDaily.user_id == ai_user_id)
    )
    platform_row = await db_session.scalar(select(PlatformOverviewDaily))

    assert teacher_row is not None
    assert teacher_row.lessons_created == 1
    assert teacher_row.assignments_created == 1

    assert student_row is not None
    assert student_row.sessions_started == 1

    assert ai_row is not None
    assert ai_row.ai_jobs_requested == 1
    assert ai_row.ai_jobs_succeeded == 1
    assert ai_row.ai_jobs_failed == 1
    assert ai_row.ai_images_generated == 1
    assert ai_row.ai_lessons_generated == 0

    assert platform_row is not None
    assert platform_row.lessons_created == 1
    assert platform_row.assignments_created == 1
    assert platform_row.sessions_started == 1
    assert platform_row.answers_scored == 1
    assert platform_row.ai_jobs_requested == 1
    assert platform_row.ai_jobs_succeeded == 1
    assert platform_row.ai_jobs_failed == 1
    assert platform_row.ai_images_generated == 1


async def test_apply_event_is_idempotent_by_event_id(db_session):
    user_id = uuid.uuid4()
    event_id = str(uuid.uuid4())
    envelope = _event(
        producer="ai-assistant-service",
        event_type="generation_requested",
        payload={
            "job_id": str(uuid.uuid4()),
            "requester_id": str(user_id),
            "intent": "create_lesson",
        },
        event_id=event_id,
    )

    await projections.apply_event(db_session, envelope)
    await projections.apply_event(db_session, envelope)

    row = await db_session.scalar(select(UserActivityDaily).where(UserActivityDaily.user_id == user_id))
    assert row is not None
    assert row.ai_jobs_requested == 1
