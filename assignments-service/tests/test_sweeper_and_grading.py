import uuid
from datetime import datetime, timedelta, timezone

from app.models import Assignment, AssignmentSession, AssignmentTask, SessionStatus, TargetType
from app.services import grading as grading_svc
from app.services import sessions as sessions_svc
from app.services.sweeper import sweep_once


async def test_sweeper_closes_session_past_its_time_limit(db_session):
    db = db_session
    teacher_id = uuid.uuid4()
    student_id = uuid.uuid4()

    assignment = Assignment(
        teacher_id=teacher_id,
        lesson_id=uuid.uuid4(),
        title="HW",
        time_limit_minutes=10,
        target_type=TargetType.link,
    )
    db.add(assignment)
    await db.flush()

    session = AssignmentSession(
        assignment_id=assignment.id,
        student_id=student_id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=20),  # well past the limit
    )
    db.add(session)
    await db.commit()

    closed = await sweep_once(db)
    assert closed == 1

    await db.refresh(session)
    assert session.status == SessionStatus.expired
    assert session.submitted_at is not None


async def test_sweeper_leaves_sessions_within_time_limit_alone(db_session):
    db = db_session
    assignment = Assignment(
        teacher_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        title="HW",
        time_limit_minutes=60,
        target_type=TargetType.link,
    )
    db.add(assignment)
    await db.flush()

    session = AssignmentSession(assignment_id=assignment.id, student_id=uuid.uuid4())
    db.add(session)
    await db.commit()

    closed = await sweep_once(db)
    assert closed == 0

    await db.refresh(session)
    assert session.status == SessionStatus.active


async def test_sweeper_closes_session_past_deadline_regardless_of_time_limit(db_session):
    db = db_session
    assignment = Assignment(
        teacher_id=uuid.uuid4(),
        lesson_id=uuid.uuid4(),
        title="HW",
        deadline=datetime.now(timezone.utc) - timedelta(minutes=5),
        target_type=TargetType.link,
    )
    db.add(assignment)
    await db.flush()

    session = AssignmentSession(assignment_id=assignment.id, student_id=uuid.uuid4())
    db.add(session)
    await db.commit()

    closed = await sweep_once(db)
    assert closed == 1
    await db.refresh(session)
    assert session.status == SessionStatus.expired


async def test_grade_aggregates_weighted_scores_from_answer_events(db_session):
    db = db_session
    assignment = Assignment(
        teacher_id=uuid.uuid4(), lesson_id=uuid.uuid4(), title="HW", target_type=TargetType.link
    )
    db.add(assignment)
    await db.flush()

    task_a, task_b = uuid.uuid4(), uuid.uuid4()
    db.add(AssignmentTask(assignment_id=assignment.id, task_id=task_a, position=0, weight=75))
    db.add(AssignmentTask(assignment_id=assignment.id, task_id=task_b, position=1, weight=25))

    session = AssignmentSession(assignment_id=assignment.id, student_id=uuid.uuid4())
    db.add(session)
    await db.commit()

    await grading_svc.apply_answer_scored(
        db, session_id=session.id, task_id=task_a, correctness=100.0
    )
    await grading_svc.apply_answer_scored(
        db, session_id=session.id, task_id=task_b, correctness=0.0
    )
    await db.commit()

    await db.refresh(session)
    # (100*75 + 0*25) / 100 = 75
    assert float(session.grade) == 75.0


async def test_manual_grade_override_is_never_touched_by_auto_grading(db_session):
    db = db_session
    assignment = Assignment(
        teacher_id=uuid.uuid4(), lesson_id=uuid.uuid4(), title="HW", target_type=TargetType.link
    )
    db.add(assignment)
    await db.flush()

    task_id = uuid.uuid4()
    db.add(AssignmentTask(assignment_id=assignment.id, task_id=task_id, position=0, weight=100))

    session = AssignmentSession(assignment_id=assignment.id, student_id=uuid.uuid4())
    db.add(session)
    await db.commit()

    await sessions_svc.override_grade(db, session=session, grade=42.0)
    await db.commit()

    await grading_svc.apply_answer_scored(
        db, session_id=session.id, task_id=task_id, correctness=100.0
    )
    await db.commit()

    await db.refresh(session)
    assert float(session.grade) == 42.0  # untouched by the auto-aggregation
