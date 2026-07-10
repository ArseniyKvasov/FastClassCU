import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, AnswerFile
from app.storage import storage


async def collect_orphaned_files(db: AsyncSession) -> list[uuid.UUID]:
    """Same reaper pattern as Content Service: the only place answer file
    blobs are physically deleted, run after answers referencing them are
    gone (quota eviction, manual reset, ...)."""
    referenced = select(Answer.file_id).where(Answer.file_id.isnot(None))
    orphans = (await db.scalars(select(AnswerFile).where(AnswerFile.id.notin_(referenced)))).all()

    reclaimed: list[uuid.UUID] = []
    for file_row in orphans:
        storage.delete(file_row.storage_key)
        await db.delete(file_row)
        reclaimed.append(file_row.id)

    await db.flush()
    return reclaimed
