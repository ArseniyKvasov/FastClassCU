import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import Assignment, AssignmentSession, SessionStatus
from app.services.sessions import maybe_expire

logger = logging.getLogger("assignments_service.sweeper")


async def sweep_once(db: AsyncSession) -> int:
    """The authoritative half of expiry (the other half is the eager check
    in GET /sessions/{id} - see sessions.maybe_expire's docstring). This is
    what guarantees a session nobody ever looks at again still gets closed,
    fixing the old system's lazy-only expiry.

    Pragmatic v1: scans a bounded batch of ALL active sessions and checks
    each in Python rather than pushing the deadline/time_limit comparison
    into SQL - simple and correct at this scale. If the active-sessions
    table gets large, the candidate query should first narrow to rows where
    the assignment's deadline or the session's own started_at makes expiry
    plausible, so the sweep doesn't scan sessions nowhere near expiring.
    """
    rows = (
        await db.execute(
            select(AssignmentSession, Assignment)
            .join(Assignment, AssignmentSession.assignment_id == Assignment.id)
            .where(AssignmentSession.status == SessionStatus.active)
            .limit(settings.sweeper_batch_size)
        )
    ).all()

    closed = 0
    for session, assignment in rows:
        if await maybe_expire(db, assignment=assignment, session=session):
            closed += 1

    if closed:
        await db.commit()
    return closed


async def run_sweeper_forever(session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with session_factory() as db:
                closed = await sweep_once(db)
                if closed:
                    logger.info("sweeper closed %d expired session(s)", closed)
        except Exception:  # noqa: BLE001
            logger.exception("sweeper pass failed")
        await asyncio.sleep(settings.sweeper_interval_seconds)
