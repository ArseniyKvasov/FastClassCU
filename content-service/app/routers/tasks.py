import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Section, Task, TaskContent
from app.schemas import TaskCreateRequest, TaskOut, TaskUpdateRequest, TaskWithContentOut
from app.services import lessons as lessons_svc

router = APIRouter(tags=["tasks"])


async def _get_task_or_404(db: AsyncSession, task_id: uuid.UUID) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})
    return task


@router.post("/sections/{section_id}/tasks", response_model=TaskWithContentOut)
async def create_task(
    section_id: uuid.UUID, body: TaskCreateRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    section = await db.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail={"code": "section_not_found"})

    task = await lessons_svc.add_task(
        db,
        section_id=section_id,
        task_type=body.task_type,
        payload=body.payload,
        created_by=body.created_by,
        file_id=body.file_id,
    )
    await db.commit()
    content = await db.get(TaskContent, task.current_content_id)
    return {**TaskOut.model_validate(task).model_dump(), "payload": content.payload}


@router.get("/sections/{section_id}/tasks", response_model=list[TaskWithContentOut])
async def list_tasks(section_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    tasks = (
        await db.scalars(
            select(Task).where(Task.section_id == section_id).order_by(Task.position)
        )
    ).all()
    out = []
    for task in tasks:
        content = await db.get(TaskContent, task.current_content_id)
        out.append({**TaskOut.model_validate(task).model_dump(), "payload": content.payload})
    return out


@router.get("/tasks/{task_id}", response_model=TaskWithContentOut)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Pure read: unlike the old get_task_data, never enqueues background
    work as a side effect. If a referenced file isn't ready yet, the client
    sees that in the file's own status, not by this endpoint doing work."""
    task = await _get_task_or_404(db, task_id)
    content = await db.get(TaskContent, task.current_content_id)
    return {**TaskOut.model_validate(task).model_dump(), "payload": content.payload}


@router.patch("/tasks/{task_id}", response_model=TaskWithContentOut)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdateRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    task = await _get_task_or_404(db, task_id)
    task = await lessons_svc.update_task(
        db, task=task, payload=body.payload, edited_by=body.edited_by, file_id=body.file_id
    )
    await db.commit()
    content = await db.get(TaskContent, task.current_content_id)
    return {**TaskOut.model_validate(task).model_dump(), "payload": content.payload}


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    task = await _get_task_or_404(db, task_id)
    await db.delete(task)
    await db.commit()
