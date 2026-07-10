from __future__ import annotations

from fastclass_shared.context import get_request_id
from fastclass_shared.tracing import current_traceparent


def propagate_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(headers or {})
    request_id = get_request_id()
    if request_id and "X-Request-ID" not in merged:
        merged["X-Request-ID"] = request_id
    traceparent = current_traceparent()
    if traceparent and "traceparent" not in merged:
        merged["traceparent"] = traceparent
    return merged
