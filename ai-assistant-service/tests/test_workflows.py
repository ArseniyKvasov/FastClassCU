import uuid

from app.services.workflows import _normalize_bundle


def test_normalize_bundle_repairs_unsupported_task_type():
    bundle = _normalize_bundle(
        {
            "title": "Draft",
            "description": "desc",
            "sections": [
                {
                    "title": "S1",
                    "tasks": [
                        {"task_type": "unknown_type", "payload": {"foo": "bar"}},
                    ],
                }
            ],
        },
        owner_id=uuid.uuid4(),
        allowed_task_types={"text", "writing_task"},
    )
    assert bundle.sections[0].tasks[0].task_type == "text"
    assert "content" in bundle.sections[0].tasks[0].payload
