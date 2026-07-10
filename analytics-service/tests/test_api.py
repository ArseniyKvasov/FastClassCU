import asyncio
import uuid
from datetime import date, datetime, timezone

from app.db import SessionLocal, engine
from app.models import ExportStatus, ExportType, PlatformOverviewDaily, UserActivityDaily


def test_platform_overview_endpoint_returns_ai_totals(api_client, admin_auth_header):
    async def _seed():
        async with SessionLocal() as db:
            db.add(
                PlatformOverviewDaily(
                    activity_date=date(2026, 7, 9),
                    users_created=2,
                    ai_jobs_requested=3,
                    ai_jobs_succeeded=2,
                    ai_jobs_failed=1,
                    ai_images_generated=2,
                    last_event_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

    asyncio.run(_seed())
    asyncio.run(engine.dispose())

    response = api_client.get(
        "/analytics/platform/overview?date_from=2026-07-01&date_to=2026-07-31",
        headers=admin_auth_header,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["totals"]["users_created"] == 2
    assert data["totals"]["ai_jobs_requested"] == 3
    assert data["totals"]["ai_jobs_succeeded"] == 2
    assert data["totals"]["ai_jobs_failed"] == 1
    assert data["totals"]["ai_images_generated"] == 2


def test_user_activity_endpoint_returns_ai_totals(api_client, admin_auth_header):
    user_id = uuid.uuid4()
    async def _seed():
        async with SessionLocal() as db:
            db.add(
                UserActivityDaily(
                    activity_date=date(2026, 7, 9),
                    user_id=user_id,
                    lessons_created=1,
                    ai_jobs_requested=2,
                    ai_jobs_succeeded=1,
                    ai_lessons_generated=1,
                    last_event_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

    asyncio.run(_seed())
    asyncio.run(engine.dispose())

    response = api_client.get(
        f"/analytics/users/{user_id}/activity?date_from=2026-07-01&date_to=2026-07-31",
        headers=admin_auth_header,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["totals"]["lessons_created"] == 1
    assert data["totals"]["ai_jobs_requested"] == 2
    assert data["totals"]["ai_jobs_succeeded"] == 1
    assert data["totals"]["ai_lessons_generated"] == 1


def test_create_export_job_validates_required_filters(api_client, admin_auth_header):
    response = api_client.post(
        "/analytics/exports",
        headers=admin_auth_header,
        json={"export_type": ExportType.user_activity.value},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "user_id_required"


def test_get_export_job_returns_serialized_status(api_client, admin_auth_header):
    job_id = uuid.uuid4()
    async def _seed():
        async with SessionLocal() as db:
            from app.models import ExportJob

            db.add(
                ExportJob(
                    id=job_id,
                    requested_by_user_id=uuid.uuid4(),
                    export_type=ExportType.platform_overview,
                    status=ExportStatus.completed,
                    filters={"date_from": "2026-07-01", "date_to": "2026-07-31"},
                    row_count=3,
                    created_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

    asyncio.run(_seed())
    asyncio.run(engine.dispose())

    response = api_client.get(f"/analytics/exports/{job_id}", headers=admin_auth_header)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job_id)
    assert data["status"] == ExportStatus.completed.value
