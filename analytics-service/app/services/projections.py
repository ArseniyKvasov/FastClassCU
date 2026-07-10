import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalyticsEvent,
    AssignmentDimension,
    ExportJob,
    ExportStatus,
    ExportType,
    FlagStatus,
    LessonQualityDaily,
    LessonReviewFlag,
    PlatformOverviewDaily,
    SessionDimension,
    UserActivityDaily,
)
from fastclass_shared.events import EventEnvelope


def _event_day(occurred_at: datetime) -> date:
    return occurred_at.date()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_or_create_user_day(
    db: AsyncSession, *, activity_date: date, user_id: uuid.UUID, occurred_at: datetime
) -> UserActivityDaily:
    row = await db.scalar(
        select(UserActivityDaily).where(
            UserActivityDaily.activity_date == activity_date,
            UserActivityDaily.user_id == user_id,
        )
    )
    if row is None:
        row = UserActivityDaily(
            activity_date=activity_date,
            user_id=user_id,
            last_event_at=occurred_at,
        )
        db.add(row)
        await db.flush()
    return row


async def _get_or_create_lesson_day(
    db: AsyncSession, *, activity_date: date, lesson_id: uuid.UUID, occurred_at: datetime
) -> LessonQualityDaily:
    row = await db.scalar(
        select(LessonQualityDaily).where(
            LessonQualityDaily.activity_date == activity_date,
            LessonQualityDaily.lesson_id == lesson_id,
        )
    )
    if row is None:
        row = LessonQualityDaily(
            activity_date=activity_date,
            lesson_id=lesson_id,
            last_event_at=occurred_at,
        )
        db.add(row)
        await db.flush()
    return row


async def _get_or_create_platform_day(
    db: AsyncSession, *, activity_date: date, occurred_at: datetime
) -> PlatformOverviewDaily:
    row = await db.scalar(
        select(PlatformOverviewDaily).where(PlatformOverviewDaily.activity_date == activity_date)
    )
    if row is None:
        row = PlatformOverviewDaily(activity_date=activity_date, last_event_at=occurred_at)
        db.add(row)
        await db.flush()
    return row


async def _persist_raw_event(db: AsyncSession, envelope: EventEnvelope, occurred_at: datetime) -> bool:
    db.add(
        AnalyticsEvent(
            event_id=envelope.event_id,
            producer=envelope.producer,
            event_type=envelope.event_type,
            occurred_at=occurred_at,
            trace_id=envelope.trace_id,
            payload=envelope.payload,
        )
    )
    try:
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def _upsert_assignment_dimension(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
    lesson_id: uuid.UUID | None,
    teacher_id: uuid.UUID | None,
    target_type: str | None,
    target_classroom_id: uuid.UUID | None,
) -> AssignmentDimension:
    row = await db.get(AssignmentDimension, assignment_id)
    if row is None:
        row = AssignmentDimension(
            assignment_id=assignment_id,
            lesson_id=lesson_id,
            teacher_id=teacher_id,
            target_type=target_type,
            target_classroom_id=target_classroom_id,
        )
        db.add(row)
    else:
        if lesson_id is not None:
            row.lesson_id = lesson_id
        if teacher_id is not None:
            row.teacher_id = teacher_id
        if target_type is not None:
            row.target_type = target_type
        if target_classroom_id is not None:
            row.target_classroom_id = target_classroom_id
    await db.flush()
    return row


async def _upsert_session_dimension(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    assignment_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    status: str | None,
) -> SessionDimension:
    row = await db.get(SessionDimension, session_id)
    if row is None:
        row = SessionDimension(
            session_id=session_id,
            assignment_id=assignment_id,
            student_id=student_id,
            status=status,
        )
        db.add(row)
    else:
        if assignment_id is not None:
            row.assignment_id = assignment_id
        if student_id is not None:
            row.student_id = student_id
        if status is not None:
            row.status = status
    await db.flush()
    return row


async def apply_event(db: AsyncSession, envelope: EventEnvelope) -> None:
    occurred_at = datetime.fromisoformat(envelope.occurred_at)
    if not await _persist_raw_event(db, envelope, occurred_at):
        return

    activity_date = _event_day(occurred_at)
    payload = envelope.payload
    platform = await _get_or_create_platform_day(
        db, activity_date=activity_date, occurred_at=occurred_at
    )
    platform.last_event_at = occurred_at

    if envelope.producer == "auth-service":
        if envelope.event_type == "guest_created":
            guest_id = uuid.UUID(payload["guest_session_id"])
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=guest_id, occurred_at=occurred_at
            )
            user_day.guests_created += 1
            user_day.last_event_at = occurred_at
            platform.guests_created += 1
        elif envelope.event_type == "user_created":
            user_id = uuid.UUID(payload["user_id"])
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=user_id, occurred_at=occurred_at
            )
            user_day.users_created += 1
            user_day.last_event_at = occurred_at
            platform.users_created += 1
        elif envelope.event_type == "user_upgraded":
            platform.users_upgraded += 1

    if envelope.producer == "content-service":
        if envelope.event_type == "lesson_created":
            owner_id = uuid.UUID(payload["owner_id"])
            lesson_id = uuid.UUID(payload["lesson_id"])
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=owner_id, occurred_at=occurred_at
            )
            user_day.lessons_created += 1
            user_day.last_event_at = occurred_at
            await _get_or_create_lesson_day(
                db, activity_date=activity_date, lesson_id=lesson_id, occurred_at=occurred_at
            )
            platform.lessons_created += 1
        elif envelope.event_type == "lesson_feedback_submitted":
            lesson_id = uuid.UUID(payload["lesson_id"])
            user_id = uuid.UUID(payload["user_id"])
            rating = int(payload["rating"])
            lesson_day = await _get_or_create_lesson_day(
                db, activity_date=activity_date, lesson_id=lesson_id, occurred_at=occurred_at
            )
            lesson_day.feedback_count += 1
            lesson_day.feedback_rating_sum += rating
            lesson_day.last_event_at = occurred_at
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=user_id, occurred_at=occurred_at
            )
            user_day.feedback_submitted += 1
            user_day.last_event_at = occurred_at
            platform.feedback_submitted += 1

    if envelope.producer == "classroom-service" and envelope.event_type == "classroom_created":
        teacher_id = uuid.UUID(payload["teacher_id"])
        user_day = await _get_or_create_user_day(
            db, activity_date=activity_date, user_id=teacher_id, occurred_at=occurred_at
        )
        user_day.classrooms_created += 1
        user_day.last_event_at = occurred_at
        platform.classrooms_created += 1

    if envelope.producer == "assignments-service":
        if envelope.event_type == "assignment_created":
            assignment_id = uuid.UUID(payload["assignment_id"])
            teacher_id = uuid.UUID(payload["teacher_id"])
            lesson_id = uuid.UUID(payload["lesson_id"]) if payload.get("lesson_id") else None
            await _upsert_assignment_dimension(
                db,
                assignment_id=assignment_id,
                lesson_id=lesson_id,
                teacher_id=teacher_id,
                target_type=payload.get("target_type"),
                target_classroom_id=uuid.UUID(payload["target_classroom_id"])
                if payload.get("target_classroom_id")
                else None,
            )
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=teacher_id, occurred_at=occurred_at
            )
            user_day.assignments_created += 1
            user_day.last_event_at = occurred_at
            if lesson_id is not None:
                lesson_day = await _get_or_create_lesson_day(
                    db, activity_date=activity_date, lesson_id=lesson_id, occurred_at=occurred_at
                )
                lesson_day.assignments_created += 1
                lesson_day.last_event_at = occurred_at
            platform.assignments_created += 1
        elif envelope.event_type == "session_started":
            session_id = uuid.UUID(payload["session_id"])
            assignment_id = uuid.UUID(payload["assignment_id"])
            student_id = uuid.UUID(payload["student_id"])
            session = await _upsert_session_dimension(
                db,
                session_id=session_id,
                assignment_id=assignment_id,
                student_id=student_id,
                status="started",
            )
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=student_id, occurred_at=occurred_at
            )
            user_day.sessions_started += 1
            user_day.last_event_at = occurred_at
            assignment = await db.get(AssignmentDimension, session.assignment_id)
            if assignment and assignment.lesson_id:
                lesson_day = await _get_or_create_lesson_day(
                    db,
                    activity_date=activity_date,
                    lesson_id=assignment.lesson_id,
                    occurred_at=occurred_at,
                )
                lesson_day.sessions_started += 1
                lesson_day.last_event_at = occurred_at
            platform.sessions_started += 1
        elif envelope.event_type == "session_submitted":
            session_id = uuid.UUID(payload["session_id"])
            assignment_id = uuid.UUID(payload["assignment_id"])
            session = await _upsert_session_dimension(
                db,
                session_id=session_id,
                assignment_id=assignment_id,
                student_id=None,
                status="submitted",
            )
            if session.student_id is not None:
                user_day = await _get_or_create_user_day(
                    db,
                    activity_date=activity_date,
                    user_id=session.student_id,
                    occurred_at=occurred_at,
                )
                user_day.sessions_submitted += 1
                user_day.last_event_at = occurred_at
            assignment = await db.get(AssignmentDimension, session.assignment_id)
            if assignment and assignment.lesson_id:
                lesson_day = await _get_or_create_lesson_day(
                    db,
                    activity_date=activity_date,
                    lesson_id=assignment.lesson_id,
                    occurred_at=occurred_at,
                )
                lesson_day.sessions_submitted += 1
                lesson_day.last_event_at = occurred_at
            platform.sessions_submitted += 1
        elif envelope.event_type == "session_expired":
            platform.sessions_expired += 1

    if envelope.producer == "answers-service":
        if envelope.event_type == "answer_updated":
            user_id = uuid.UUID(payload["user_id"])
            user_day = await _get_or_create_user_day(
                db, activity_date=activity_date, user_id=user_id, occurred_at=occurred_at
            )
            user_day.answers_submitted += 1
            user_day.last_event_at = occurred_at
            platform.answers_submitted += 1
        elif envelope.event_type == "answer_scored":
            session_id = uuid.UUID(payload["session_id"])
            correctness = float(payload["correctness"])
            session = await db.get(SessionDimension, session_id)
            if session and session.assignment_id:
                assignment = await db.get(AssignmentDimension, session.assignment_id)
                if assignment and assignment.lesson_id:
                    lesson_day = await _get_or_create_lesson_day(
                        db,
                        activity_date=activity_date,
                        lesson_id=assignment.lesson_id,
                        occurred_at=occurred_at,
                    )
                    lesson_day.answers_scored += 1
                    lesson_day.score_sum += correctness
                    lesson_day.score_count += 1
                    lesson_day.last_event_at = occurred_at
            platform.answers_scored += 1

    if envelope.producer == "ai-assistant-service":
        requester_id_raw = payload.get("requester_id")
        requester_id = uuid.UUID(requester_id_raw) if requester_id_raw else None
        artifact_type = str(payload.get("artifact_type") or "")

        user_day = None
        if requester_id is not None:
            user_day = await _get_or_create_user_day(
                db,
                activity_date=activity_date,
                user_id=requester_id,
                occurred_at=occurred_at,
            )
            user_day.last_event_at = occurred_at

        if envelope.event_type == "generation_requested":
            platform.ai_jobs_requested += 1
            if user_day is not None:
                user_day.ai_jobs_requested += 1
        elif envelope.event_type == "generation_succeeded":
            platform.ai_jobs_succeeded += 1
            if user_day is not None:
                user_day.ai_jobs_succeeded += 1

            if artifact_type == "lesson_draft":
                platform.ai_lessons_generated += 1
                if user_day is not None:
                    user_day.ai_lessons_generated += 1
            elif artifact_type == "image":
                platform.ai_images_generated += 1
                if user_day is not None:
                    user_day.ai_images_generated += 1
            elif artifact_type == "audio":
                platform.ai_audio_generated += 1
                if user_day is not None:
                    user_day.ai_audio_generated += 1
        elif envelope.event_type == "generation_failed":
            platform.ai_jobs_failed += 1
            if user_day is not None:
                user_day.ai_jobs_failed += 1

    await db.commit()


async def get_user_activity_stats(
    db: AsyncSession, *, user_id: uuid.UUID, date_from: date, date_to: date
) -> list[UserActivityDaily]:
    result = await db.scalars(
        select(UserActivityDaily)
        .where(
            UserActivityDaily.user_id == user_id,
            UserActivityDaily.activity_date >= date_from,
            UserActivityDaily.activity_date <= date_to,
        )
        .order_by(UserActivityDaily.activity_date)
    )
    return list(result.all())


async def get_lesson_quality_report(
    db: AsyncSession, *, lesson_id: uuid.UUID, date_from: date, date_to: date
) -> list[LessonQualityDaily]:
    result = await db.scalars(
        select(LessonQualityDaily)
        .where(
            LessonQualityDaily.lesson_id == lesson_id,
            LessonQualityDaily.activity_date >= date_from,
            LessonQualityDaily.activity_date <= date_to,
        )
        .order_by(LessonQualityDaily.activity_date)
    )
    return list(result.all())


async def get_platform_overview(
    db: AsyncSession, *, date_from: date, date_to: date
) -> list[PlatformOverviewDaily]:
    result = await db.scalars(
        select(PlatformOverviewDaily)
        .where(
            PlatformOverviewDaily.activity_date >= date_from,
            PlatformOverviewDaily.activity_date <= date_to,
        )
        .order_by(PlatformOverviewDaily.activity_date)
    )
    return list(result.all())


async def create_lesson_flag(
    db: AsyncSession,
    *,
    lesson_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    reason: str,
    severity: str,
) -> LessonReviewFlag:
    flag = LessonReviewFlag(
        lesson_id=lesson_id,
        created_by_user_id=created_by_user_id,
        reason=reason,
        severity=severity,
    )
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag


async def update_lesson_flag(
    db: AsyncSession,
    *,
    flag_id: uuid.UUID,
    resolved_by_user_id: uuid.UUID,
    status: str,
    resolution_note: str | None,
) -> LessonReviewFlag | None:
    flag = await db.get(LessonReviewFlag, flag_id)
    if flag is None:
        return None
    flag.status = status
    flag.resolution_note = resolution_note
    if status == FlagStatus.resolved:
        flag.resolved_by_user_id = resolved_by_user_id
        flag.resolved_at = _now()
    else:
        flag.resolved_by_user_id = None
        flag.resolved_at = None
    await db.commit()
    await db.refresh(flag)
    return flag


async def count_open_flags(db: AsyncSession, *, lesson_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count()).select_from(LessonReviewFlag).where(
            LessonReviewFlag.lesson_id == lesson_id,
            LessonReviewFlag.status == FlagStatus.open,
        )
    )
    return int(count or 0)


async def create_export_job(
    db: AsyncSession,
    *,
    requested_by_user_id: uuid.UUID,
    export_type: ExportType,
    filters: dict,
) -> ExportJob:
    job = ExportJob(
        requested_by_user_id=requested_by_user_id,
        export_type=export_type,
        status=ExportStatus.pending,
        filters=filters,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
