from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerFile
from app.storage import storage


async def create_answer_file(
    db: AsyncSession,
    *,
    data: bytes,
    mime_type: str | None = None,
    duration_seconds: float | None = None,
) -> AnswerFile:
    """Content-addressed: identical bytes reuse the same row/blob - same
    pattern as Content Service's create_file_asset."""
    sha256, storage_key, size = storage.save(data)

    existing = await db.scalar(select(AnswerFile).where(AnswerFile.sha256 == sha256))
    if existing is not None:
        return existing

    file_row = AnswerFile(
        sha256=sha256,
        storage_key=storage_key,
        size_bytes=size,
        mime_type=mime_type,
        duration_seconds=duration_seconds,
    )
    db.add(file_row)
    await db.flush()
    return file_row
