from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor_user_id: ContextVar[str | None] = ContextVar("actor_user_id", default=None)
_actor_service: ContextVar[str | None] = ContextVar("actor_service", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("span_id", default=None)


def clear_context() -> None:
    _request_id.set(None)
    _actor_user_id.set(None)
    _actor_service.set(None)
    _trace_id.set(None)
    _span_id.set(None)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def set_trace_context(*, trace_id: str | None, span_id: str | None) -> None:
    _trace_id.set(trace_id)
    _span_id.set(span_id)


def get_trace_id() -> str | None:
    return _trace_id.get()


def get_span_id() -> str | None:
    return _span_id.get()


def bind_actor(*, user_id: str | None = None, service: str | None = None) -> None:
    if user_id is not None:
        _actor_user_id.set(user_id)
    if service is not None:
        _actor_service.set(service)


def get_actor_context() -> dict[str, str]:
    context: dict[str, str] = {}
    request_id = _request_id.get()
    actor_user_id = _actor_user_id.get()
    actor_service = _actor_service.get()
    trace_id = _trace_id.get()
    span_id = _span_id.get()
    if request_id:
        context["request_id"] = request_id
    if actor_user_id:
        context["actor_user_id"] = actor_user_id
    if actor_service:
        context["actor_service"] = actor_service
    if trace_id:
        context["trace_id"] = trace_id
    if span_id:
        context["span_id"] = span_id
    return context
