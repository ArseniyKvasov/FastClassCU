"""Content (task_contents / files / quota) operations.

Everything storage-accounted flows through here. Clone/copy never call these
create functions - that's the whole point: deriving a lesson reuses existing
content rows, so it costs zero new bytes and never touches quota.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hashing import content_hash
from app.models import FileAsset, TaskContent, TeacherQuota
from app.services.events import emit_event
from app.storage import storage
from app.tasks_registry import get_schema, validate_payload


class QuotaExceededError(Exception):
    pass


async def _reserve_quota(db: AsyncSession, teacher_id: uuid.UUID, delta: int) -> None:
    """Reserve-then-commit, not check-after-the-fact. Locks the teacher's
    quota row FOR UPDATE so two concurrent writers can't both read an
    under-limit total and jointly overshoot. Must run inside the same
    transaction as the content insert it's accounting for."""
    if delta <= 0:
        return

    row = await db.get(TeacherQuota, teacher_id, with_for_update=True)
    if row is None:
        row = TeacherQuota(teacher_id=teacher_id, storage_bytes=0)
        db.add(row)
        await db.flush()
        row = await db.get(TeacherQuota, teacher_id, with_for_update=True)

    if row.storage_bytes + delta > settings.teacher_storage_limit_bytes:
        raise QuotaExceededError(
            f"Storage limit exceeded: {row.storage_bytes + delta} > "
            f"{settings.teacher_storage_limit_bytes}"
        )
    row.storage_bytes += delta


def _payload_size(payload: dict) -> int:
    import json

    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _validate_mime_type(task_type: str, mime_type: str | None) -> None:
    """Enforces each has_file type's allow-list (e.g. 'file' only takes
    documents, 'image' only takes image/*) so a task can't end up pointing
    at a file its own renderer/answer-checker doesn't expect."""
    schema = get_schema(task_type)
    if not schema.allowed_mime_types:
        return
    if mime_type not in schema.allowed_mime_types:
        raise ValueError(
            f"'{task_type}' tasks only accept {schema.allowed_mime_types}, got '{mime_type}'"
        )


async def get_or_create_content(
    db: AsyncSession,
    *,
    task_type: str,
    payload: dict,
    created_by: uuid.UUID,
    file_id: uuid.UUID | None = None,
) -> TaskContent:
    """Returns an existing TaskContent if an identical one exists (dedup), else
    creates one and charges quota for exactly the new bytes. Identical content
    across users collapses to one row and is charged once (to whoever created
    it first) - later identical writes are free."""
    normalized = validate_payload(task_type, payload)
    digest = content_hash(task_type, normalized, file_id)

    existing = await db.scalar(
        select(TaskContent).where(TaskContent.content_hash == digest)
    )
    if existing is not None:
        return existing

    delta = _payload_size(normalized)
    if file_id is not None:
        f = await db.get(FileAsset, file_id)
        if f is not None:
            _validate_mime_type(task_type, f.mime_type)
            delta += f.size_bytes
    await _reserve_quota(db, created_by, delta)

    content = TaskContent(
        task_type=task_type,
        content_hash=digest,
        payload=normalized,
        file_id=file_id,
        created_by=created_by,
    )
    db.add(content)
    await db.flush()
    return content


async def teacher_storage_bytes(db: AsyncSession, teacher_id: uuid.UUID) -> int:
    row = await db.get(TeacherQuota, teacher_id)
    return row.storage_bytes if row else 0


async def create_file_asset(
    db: AsyncSession,
    *,
    data: bytes,
    mime_type: str | None = None,
    original_filename: str | None = None,
) -> FileAsset:
    """Content-addressed: re-uploading identical bytes reuses the same row
    and the same on-disk blob (LocalStorage.save is itself idempotent by
    hash) - no quota charge happens here, only when a TaskContent first
    references this file (see get_or_create_content)."""
    sha256, storage_key, size = storage.save(data)

    existing = await db.scalar(select(FileAsset).where(FileAsset.sha256 == sha256))
    if existing is not None:
        return existing

    file_asset = FileAsset(
        sha256=sha256,
        storage_key=storage_key,
        size_bytes=size,
        mime_type=mime_type,
        original_filename=original_filename,
    )
    db.add(file_asset)
    await db.flush()

    await emit_event(
        db,
        event_type="file_ready",
        payload={"file_id": str(file_asset.id), "size_bytes": size},
    )
    return file_asset
