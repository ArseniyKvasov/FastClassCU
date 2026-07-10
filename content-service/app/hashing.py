import hashlib
import json
import uuid


def content_hash(task_type: str, payload: dict, file_id: uuid.UUID | None) -> str:
    """Stable hash over a task's full content identity. Two contents with the
    same task_type, same normalized payload, and same file collapse to one
    row (dedup) - so identical tasks across users/lessons share storage.

    sort_keys makes the JSON canonical regardless of dict ordering; file_id
    is folded in so two tasks with identical text but different files don't
    collide.
    """
    material = {
        "task_type": task_type,
        "payload": payload,
        "file_id": str(file_id) if file_id else None,
    }
    encoded = json.dumps(material, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
