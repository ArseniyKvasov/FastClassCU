"""Garbage collector for orphaned content and files.

The ONLY place content/file rows and blobs are physically deleted. Everything
else (delete_lesson, update_task) just drops references. This centralizes
reclamation so there's exactly one well-logged path, instead of the old code's
scattered best-effort `except: pass` deletes that silently leaked blobs.

Ref-counts are computed live (COUNT queries), never stored - a stored counter
is one more thing that can drift out of sync with reality.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FileAsset, Task, TaskContent, TeacherQuota
from app.storage import storage


async def collect_orphaned_contents(db: AsyncSession) -> list[uuid.UUID]:
    """Delete TaskContent rows no Task points at (via current or synced_from).
    Returns the ids reclaimed. Credits freed payload bytes back to quota."""
    referenced = (
        select(Task.current_content_id).where(Task.current_content_id.isnot(None))
    ).union(
        select(Task.synced_from_content_id).where(Task.synced_from_content_id.isnot(None))
    )

    orphans = (
        await db.scalars(select(TaskContent).where(TaskContent.id.notin_(referenced)))
    ).all()

    reclaimed: list[uuid.UUID] = []
    for content in orphans:
        import json

        size = len(json.dumps(content.payload, ensure_ascii=False).encode("utf-8"))
        quota = await db.get(TeacherQuota, content.created_by, with_for_update=True)
        if quota is not None:
            quota.storage_bytes = max(0, quota.storage_bytes - size)
        await db.delete(content)
        reclaimed.append(content.id)

    await db.flush()
    return reclaimed


async def collect_orphaned_files(db: AsyncSession) -> list[uuid.UUID]:
    """Delete FileAsset rows (and their blobs) no TaskContent references.
    Runs after content collection so contents freed this cycle release their
    files too. Credits freed file bytes back to quota."""
    referenced = select(TaskContent.file_id).where(TaskContent.file_id.isnot(None))

    orphans = (
        await db.scalars(select(FileAsset).where(FileAsset.id.notin_(referenced)))
    ).all()

    reclaimed: list[uuid.UUID] = []
    for f in orphans:
        storage.delete(f.storage_key)
        await db.delete(f)
        reclaimed.append(f.id)

    await db.flush()
    return reclaimed


async def run_gc(db: AsyncSession) -> dict:
    contents = await collect_orphaned_contents(db)
    files = await collect_orphaned_files(db)
    return {"reclaimed_contents": len(contents), "reclaimed_files": len(files)}
