import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtifactType, GenerationArtifact, GenerationJob, JobIntent, JobStatus
from app.schemas import (
    AdaptLessonRequest,
    AudioGenerationRequest,
    ImageGenerationRequest,
    LessonBundle,
    LessonDraftRequest,
)
from app.services import content_client, context
from app.services import events as events_svc
from app.services.providers import ProviderRouter


def _normalize_bundle(
    bundle_data: dict[str, Any], *, owner_id: uuid.UUID, allowed_task_types: set[str]
) -> LessonBundle:
    sections = []
    for section_index, section in enumerate(bundle_data.get("sections") or []):
        tasks = []
        for task_index, task in enumerate(section.get("tasks") or []):
            task_type = str(task.get("task_type") or "text")
            if task_type not in allowed_task_types:
                task_type = "text"
                task["payload"] = {
                    "content": str(task.get("payload") or task)
                }
            payload = dict(task.get("payload") or {})
            if task_type == "text" and "content" not in payload:
                payload = {"content": str(payload or "")}
            if task_type == "writing_task":
                payload.setdefault("prompt", "Напиши ответ по теме урока.")
                payload.setdefault("default_text", "")
            tasks.append(
                {
                    "task_type": task_type,
                    "payload": payload,
                    "position": task_index,
                    "file_id": task.get("file_id"),
                }
            )
        if tasks:
            sections.append(
                {
                    "title": str(section.get("title") or f"Section {section_index + 1}"),
                    "position": section_index,
                    "tasks": tasks,
                }
            )

    if not sections:
        sections = [
            {
                "title": "Основная часть",
                "position": 0,
                "tasks": [
                    {
                        "task_type": "text",
                        "payload": {"content": "Черновик урока был сгенерирован без секций и был автоматически восстановлен."},
                        "position": 0,
                    }
                ],
            }
        ]

    return LessonBundle(
        owner_id=owner_id,
        title=str(bundle_data.get("title") or "AI Draft"),
        description=bundle_data.get("description"),
        sections=sections,
    )


async def hydrate_job(db: AsyncSession, *, job_id: uuid.UUID) -> GenerationJob | None:
    return await db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))


async def _emit_generation_succeeded(
    db: AsyncSession,
    *,
    job: GenerationJob,
    provider: str,
    artifact_type: str,
    extra_payload: dict[str, str | None] | None = None,
) -> None:
    payload = {
        "job_id": str(job.id),
        "requester_id": str(job.requester_id),
        "intent": job.intent.value,
        "provider": provider,
        "artifact_type": artifact_type,
    }
    if extra_payload:
        payload.update({key: value for key, value in extra_payload.items() if value is not None})
    await events_svc.emit_event(db, event_type="generation_succeeded", payload=payload)


async def process_job(db: AsyncSession, *, job: GenerationJob) -> None:
    router = ProviderRouter(db, job=job)
    input_payload = dict(job.input_payload)

    if job.intent == JobIntent.create_lesson:
        request = LessonDraftRequest.model_validate(input_payload)
        context_pack = await context.build_context_pack(
            db, user_id=job.requester_id, request_payload=request.model_dump(mode="json")
        )
        job.context_payload = context_pack
        prefer_pdf = any(item.mime_type == "application/pdf" for item in request.source_attachments)
        selection = await router.generate_lesson_bundle(
            context_pack=context_pack, prefer_pdf=prefer_pdf, mode="create"
        )
        task_registry = await content_client.get_task_registry()
        bundle = _normalize_bundle(
            selection.output,
            owner_id=job.requester_id,
            allowed_task_types={item.task_type for item in task_registry.tasks},
        )
        lesson = await content_client.create_lesson_draft(bundle)
        artifact = GenerationArtifact(
            job_id=job.id,
            artifact_type=ArtifactType.lesson_draft,
            lesson_id=lesson.id,
            payload=lesson.model_dump(mode="json"),
        )
        db.add(artifact)
        job.result_payload = {
            "provider": selection.provider,
            "lesson_id": str(lesson.id),
            "title": lesson.title,
        }
        job.status = JobStatus.succeeded
        await _emit_generation_succeeded(
            db,
            job=job,
            provider=selection.provider,
            artifact_type=ArtifactType.lesson_draft.value,
            extra_payload={"lesson_id": str(lesson.id)},
        )
        return

    if job.intent == JobIntent.adapt_lesson:
        request = AdaptLessonRequest.model_validate(input_payload)
        source_lesson = await content_client.get_lesson_bundle(request.lesson_id)
        context_pack = await context.build_context_pack(
            db,
            user_id=job.requester_id,
            source_lesson=source_lesson,
            request_payload=request.model_dump(mode="json"),
        )
        job.context_payload = context_pack
        prefer_pdf = any(item.mime_type == "application/pdf" for item in request.source_attachments)
        selection = await router.generate_lesson_bundle(
            context_pack=context_pack, prefer_pdf=prefer_pdf, mode="adapt"
        )
        task_registry = await content_client.get_task_registry()
        bundle = _normalize_bundle(
            {
                **selection.output,
                "title": request.title or selection.output.get("title") or source_lesson.title,
                "description": request.description
                or selection.output.get("description")
                or source_lesson.description,
            },
            owner_id=job.requester_id,
            allowed_task_types={item.task_type for item in task_registry.tasks},
        )
        lesson = await content_client.create_lesson_draft(bundle)
        db.add(
            GenerationArtifact(
                job_id=job.id,
                artifact_type=ArtifactType.lesson_draft,
                lesson_id=lesson.id,
                payload=lesson.model_dump(mode="json"),
            )
        )
        job.result_payload = {
            "provider": selection.provider,
            "lesson_id": str(lesson.id),
            "source_lesson_id": str(source_lesson.id),
        }
        job.status = JobStatus.succeeded
        await _emit_generation_succeeded(
            db,
            job=job,
            provider=selection.provider,
            artifact_type=ArtifactType.lesson_draft.value,
            extra_payload={
                "lesson_id": str(lesson.id),
                "source_lesson_id": str(source_lesson.id),
            },
        )
        return

    if job.intent == JobIntent.generate_image:
        request = ImageGenerationRequest.model_validate(input_payload)
        selection = await router.generate_image(
            prompt=request.prompt, size=request.size, filename=request.filename
        )
        asset = await content_client.upload_generated_file(selection.output)
        db.add(
            GenerationArtifact(
                job_id=job.id,
                artifact_type=ArtifactType.image,
                content_service_file_id=uuid.UUID(asset["id"]),
                mime_type=asset["mime_type"],
                payload=asset,
            )
        )
        job.result_payload = {
            "provider": selection.provider,
            "file_id": asset["id"],
            "mime_type": asset["mime_type"],
        }
        job.status = JobStatus.succeeded
        await _emit_generation_succeeded(
            db,
            job=job,
            provider=selection.provider,
            artifact_type=ArtifactType.image.value,
            extra_payload={"file_id": str(asset["id"]), "mime_type": asset["mime_type"]},
        )
        return

    if job.intent == JobIntent.generate_audio:
        request = AudioGenerationRequest.model_validate(input_payload)
        selection = await router.generate_audio(
            script=request.script,
            voice_mapping=request.voice_mapping,
            sample_context=request.sample_context,
            filename=request.filename,
        )
        asset = await content_client.upload_generated_file(selection.output)
        db.add(
            GenerationArtifact(
                job_id=job.id,
                artifact_type=ArtifactType.audio,
                content_service_file_id=uuid.UUID(asset["id"]),
                mime_type=asset["mime_type"],
                payload=asset,
            )
        )
        job.result_payload = {
            "provider": selection.provider,
            "file_id": asset["id"],
            "mime_type": asset["mime_type"],
        }
        job.status = JobStatus.succeeded
        await _emit_generation_succeeded(
            db,
            job=job,
            provider=selection.provider,
            artifact_type=ArtifactType.audio.value,
            extra_payload={"file_id": str(asset["id"]), "mime_type": asset["mime_type"]},
        )
        return

    raise ValueError(f"unsupported_intent:{job.intent}")
