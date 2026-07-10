import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import FileAsset, Lesson, Section, Task, TaskContent
from app.schemas import LessonBundle, LessonBundleOut, TaskRegistryItem, TaskRegistryOut
from app.services import lessons as lessons_svc
from app.tasks_registry import REGISTRY
from fastclass_shared.auth import ServiceAuthError, authenticate_service_request

router = APIRouter(prefix="/internal", tags=["internal"])


def require_service_token(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
    required_scopes: set[str] | None = None,
) -> None:
    try:
        authenticate_service_request(
            authorization=authorization,
            x_service_token=x_service_token,
            public_key_path=settings.jwt_public_key_path,
            issuer=settings.jwt_issuer,
            required_scopes=required_scopes,
            allow_legacy_token=settings.allow_legacy_internal_service_token,
            legacy_token=settings.internal_service_token,
        )
    except ServiceAuthError:
        raise HTTPException(status_code=401, detail={"code": "invalid_service_token"})


def require_content_answer_key_read(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"content:answer-key:read"},
    )


def require_content_task_registry_read(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"content:task-registry:read"},
    )


def require_content_lessons_read(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"content:lessons:read"},
    )


def require_content_lesson_draft_write(
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
) -> None:
    require_service_token(
        authorization=authorization,
        x_service_token=x_service_token,
        required_scopes={"content:lesson-draft:write"},
    )


async def _lesson_bundle_or_404(db: AsyncSession, lesson_id: uuid.UUID) -> dict:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail={"code": "lesson_not_found"})

    sections = (
        await db.scalars(
            select(Section).where(Section.lesson_id == lesson.id).order_by(Section.position)
        )
    ).all()

    bundle_sections = []
    for section in sections:
        tasks = (
            await db.scalars(
                select(Task).where(Task.section_id == section.id).order_by(Task.position)
            )
        ).all()
        bundle_tasks = []
        for task in tasks:
            content = await db.get(TaskContent, task.current_content_id)
            file_id = content.file_id
            file_meta = None
            if file_id is not None:
                file_row = await db.get(FileAsset, file_id)
                if file_row is not None:
                    file_meta = {
                        "id": str(file_row.id),
                        "mime_type": file_row.mime_type,
                        "original_filename": file_row.original_filename,
                    }
            bundle_tasks.append(
                {
                    "task_type": task.task_type,
                    "payload": content.payload,
                    "file_id": file_id,
                    "position": task.position,
                    "file": file_meta,
                }
            )
        bundle_sections.append(
            {
                "title": section.title,
                "position": section.position,
                "tasks": bundle_tasks,
            }
        )

    return {
        "id": lesson.id,
        "owner_id": lesson.owner_id,
        "title": lesson.title,
        "description": lesson.description,
        "sections": bundle_sections,
        "created_at": lesson.created_at,
    }


@router.get("/tasks/{task_id}/answer-key")
async def get_answer_key(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_content_answer_key_read),
) -> dict:
    """Service-to-service only (X-Service-Token, never a user JWT) - Answers
    Service is the only intended caller. Returns whatever the task's current
    content payload is; for objective types this includes the correct
    answer(s) (e.g. TestTaskSchema.questions[].correct_index) that must
    never be exposed to a student through a user-facing endpoint."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})

    content = await db.get(TaskContent, task.current_content_id)
    return {
        "task_id": str(task.id),
        "content_id": str(content.id),
        "task_type": task.task_type,
        "answer_key": content.payload,
    }


@router.get("/task-registry", response_model=TaskRegistryOut)
async def get_task_registry(_auth: None = Depends(require_content_task_registry_read)) -> dict:
    return {
        "tasks": [
            TaskRegistryItem(
                task_type=task_type,
                has_file=schema.has_file,
                allowed_mime_types=schema.allowed_mime_types,
            )
            for task_type, schema in sorted(REGISTRY.items())
        ]
    }


@router.get("/lessons/{lesson_id}/bundle", response_model=LessonBundleOut)
async def get_lesson_bundle(
    lesson_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_content_lessons_read),
) -> dict:
    return await _lesson_bundle_or_404(db, lesson_id)


@router.get("/owners/{owner_id}/lessons", response_model=list[LessonBundleOut])
async def list_owner_lessons(
    owner_id: uuid.UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_content_lessons_read),
) -> list[dict]:
    lessons = (
        await db.scalars(
            select(Lesson)
            .where(Lesson.owner_id == owner_id)
            .order_by(Lesson.updated_at.desc())
            .limit(max(1, min(limit, 25)))
        )
    ).all()
    return [await _lesson_bundle_or_404(db, lesson.id) for lesson in lessons]


@router.post("/lessons/draft", response_model=LessonBundleOut)
async def create_lesson_draft(
    body: LessonBundle,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_content_lesson_draft_write),
) -> dict:
    lesson = await lessons_svc.create_lesson(
        db, owner_id=body.owner_id, title=body.title, description=body.description
    )

    existing_sections = (
        await db.scalars(
            select(Section).where(Section.lesson_id == lesson.id).order_by(Section.position)
        )
    ).all()
    for section in existing_sections:
        await db.delete(section)
    await db.flush()

    for section_index, section_data in enumerate(body.sections):
        section = Section(
            lesson_id=lesson.id,
            title=section_data.title,
            position=section_index,
        )
        db.add(section)
        await db.flush()
        for task_index, task_data in enumerate(section_data.tasks):
            task = await lessons_svc.add_task(
                db,
                section_id=section.id,
                task_type=task_data.task_type,
                payload=task_data.payload,
                created_by=body.owner_id,
                file_id=task_data.file_id,
            )
            task.position = task_index
        await db.flush()

    await db.commit()
    return await _lesson_bundle_or_404(db, lesson.id)
