import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import GenerationArtifact, GenerationJob, JobIntent, JobStatus
from app.schemas import (
    AdaptLessonRequest,
    AudioGenerationRequest,
    CancelGenerationResponse,
    GenerationCreated,
    GenerationJobOut,
    ImageGenerationRequest,
    LessonDraftRequest,
)
from app.services import events as events_svc
from fastclass_shared import RateLimitExceeded, RateLimitRule, RedisRateLimiter

router = APIRouter(prefix="/generations", tags=["generations"])
_generation_limiter = RedisRateLimiter(
    redis_url=settings.rate_limit_redis_url,
    service_name="ai-assistant-service",
)


async def _job_or_404(
    db: AsyncSession, *, job_id: uuid.UUID, user_id: uuid.UUID
) -> GenerationJob:
    job = await db.get(GenerationJob, job_id)
    if job is None or job.requester_id != user_id:
        raise HTTPException(status_code=404, detail={"code": "generation_not_found"})
    return job


async def _serialize_job(db: AsyncSession, job: GenerationJob) -> GenerationJobOut:
    artifacts = (
        await db.scalars(
            select(GenerationArtifact).where(GenerationArtifact.job_id == job.id)
        )
    ).all()
    return GenerationJobOut(
        id=job.id,
        requester_id=job.requester_id,
        intent=job.intent,
        status=job.status,
        input_payload=job.input_payload,
        context_payload=job.context_payload,
        result_payload=job.result_payload,
        error_code=job.error_code,
        error_message=job.error_message,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        cancel_requested=job.cancel_requested,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        artifacts=artifacts,
    )


async def _create_job(
    db: AsyncSession, *, user: CurrentUser, intent: JobIntent, payload: dict
) -> GenerationCreated:
    try:
        await _generation_limiter.hit(
            RateLimitRule(
                name="generation-request",
                limit=settings.generation_request_rate_limit,
                window_seconds=settings.generation_request_window_seconds,
            ),
            str(user.user_id),
            intent.value,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "too_many_requests", "retry_after_seconds": exc.retry_after_seconds},
        )

    job = GenerationJob(
        requester_id=user.user_id,
        intent=intent,
        status=JobStatus.pending,
        input_payload=payload,
        max_attempts=settings.worker_max_attempts,
    )
    db.add(job)
    await db.flush()
    await events_svc.emit_event(
        db,
        event_type="generation_requested",
        payload={
            "job_id": str(job.id),
            "requester_id": str(user.user_id),
            "intent": intent.value,
            "max_attempts": job.max_attempts,
        },
    )
    await db.commit()
    return GenerationCreated(job_id=job.id, status=job.status)


@router.post("/lesson-draft", response_model=GenerationCreated)
async def create_lesson_draft_generation(
    body: LessonDraftRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GenerationCreated:
    return await _create_job(
        db, user=user, intent=JobIntent.create_lesson, payload=body.model_dump(mode="json")
    )


@router.post("/adapt-lesson", response_model=GenerationCreated)
async def create_lesson_adaptation_generation(
    body: AdaptLessonRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GenerationCreated:
    return await _create_job(
        db, user=user, intent=JobIntent.adapt_lesson, payload=body.model_dump(mode="json")
    )


@router.post("/image", response_model=GenerationCreated)
async def create_image_generation(
    body: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GenerationCreated:
    if body.size not in settings.supported_image_sizes:
        raise HTTPException(status_code=400, detail={"code": "unsupported_image_size"})
    return await _create_job(
        db, user=user, intent=JobIntent.generate_image, payload=body.model_dump(mode="json")
    )


@router.post("/audio", response_model=GenerationCreated)
async def create_audio_generation(
    body: AudioGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GenerationCreated:
    return await _create_job(
        db, user=user, intent=JobIntent.generate_audio, payload=body.model_dump(mode="json")
    )


@router.get("/{job_id}", response_model=GenerationJobOut)
async def get_generation(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GenerationJobOut:
    job = await _job_or_404(db, job_id=job_id, user_id=user.user_id)
    return await _serialize_job(db, job)


@router.post("/{job_id}/cancel", response_model=CancelGenerationResponse)
async def cancel_generation(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> CancelGenerationResponse:
    job = await _job_or_404(db, job_id=job_id, user_id=user.user_id)
    if job.status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
        raise HTTPException(status_code=409, detail={"code": "generation_already_finished"})
    job.cancel_requested = True
    await events_svc.emit_event(
        db,
        event_type="generation_cancel_requested",
        payload={
            "job_id": str(job.id),
            "requester_id": str(job.requester_id),
            "intent": job.intent.value,
            "status": job.status.value,
        },
    )
    await db.commit()
    return CancelGenerationResponse(
        job_id=job.id, status=job.status, cancel_requested=job.cancel_requested
    )
