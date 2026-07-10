from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
except ImportError:  # pragma: no cover - optional until deps are installed
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Gauge = Histogram = None
    generate_latest = None


if Counter is not None and Histogram is not None and Gauge is not None:
    HTTP_REQUESTS_TOTAL = Counter(
        "fastclass_http_requests_total",
        "Total HTTP requests",
        ["service", "method", "route", "status_code"],
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "fastclass_http_request_duration_seconds",
        "HTTP request duration",
        ["service", "method", "route"],
    )
    HTTP_REQUESTS_IN_PROGRESS = Gauge(
        "fastclass_http_requests_in_progress",
        "HTTP requests currently in progress",
        ["service", "method"],
    )
    EVENTS_PUBLISHED_TOTAL = Counter(
        "fastclass_events_published_total",
        "Published outbox events",
        ["producer", "event_type"],
    )
    EVENTS_CONSUMED_TOTAL = Counter(
        "fastclass_events_consumed_total",
        "Consumed bus events",
        ["consumer", "producer", "event_type", "status"],
    )
    EVENT_BUS_LOOP_FAILURES_TOTAL = Counter(
        "fastclass_event_bus_loop_failures_total",
        "Event bus loop failures",
        ["role", "name"],
    )
    OUTBOX_BACKLOG = Gauge(
        "fastclass_outbox_backlog",
        "Current outbox backlog seen by relay",
        ["producer"],
    )
    RATE_LIMIT_BLOCK_TOTAL = Counter(
        "fastclass_rate_limit_block_total",
        "Rate limit blocks",
        ["service", "limiter"],
    )
else:
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION_SECONDS = None
    HTTP_REQUESTS_IN_PROGRESS = None
    EVENTS_PUBLISHED_TOTAL = None
    EVENTS_CONSUMED_TOTAL = None
    EVENT_BUS_LOOP_FAILURES_TOTAL = None
    OUTBOX_BACKLOG = None
    RATE_LIMIT_BLOCK_TOTAL = None


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        method = request.method
        if HTTP_REQUESTS_IN_PROGRESS is not None:
            HTTP_REQUESTS_IN_PROGRESS.labels(self.service_name, method).inc()
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route_obj = request.scope.get("route")
            route = getattr(route_obj, "path", None) or request.url.path
            duration = time.perf_counter() - started
            if HTTP_REQUEST_DURATION_SECONDS is not None:
                HTTP_REQUEST_DURATION_SECONDS.labels(self.service_name, method, route).observe(
                    duration
                )
            if HTTP_REQUESTS_TOTAL is not None:
                HTTP_REQUESTS_TOTAL.labels(self.service_name, method, route, str(status_code)).inc()
            if HTTP_REQUESTS_IN_PROGRESS is not None:
                HTTP_REQUESTS_IN_PROGRESS.labels(self.service_name, method).dec()


def install_metrics(app: FastAPI, *, service_name: str) -> None:
    app.add_middleware(MetricsMiddleware, service_name=service_name)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        if generate_latest is None:
            return PlainTextResponse("", media_type=CONTENT_TYPE_LATEST)
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_event_published(*, producer: str, event_type: str) -> None:
    if EVENTS_PUBLISHED_TOTAL is not None:
        EVENTS_PUBLISHED_TOTAL.labels(producer, event_type).inc()


def record_event_consumed(*, consumer: str, producer: str, event_type: str, status: str) -> None:
    if EVENTS_CONSUMED_TOTAL is not None:
        EVENTS_CONSUMED_TOTAL.labels(consumer, producer, event_type, status).inc()


def record_event_bus_failure(*, role: str, name: str) -> None:
    if EVENT_BUS_LOOP_FAILURES_TOTAL is not None:
        EVENT_BUS_LOOP_FAILURES_TOTAL.labels(role, name).inc()


def set_outbox_backlog(*, producer: str, backlog: int) -> None:
    if OUTBOX_BACKLOG is not None:
        OUTBOX_BACKLOG.labels(producer).set(backlog)


def record_rate_limit_block(*, service: str, limiter: str) -> None:
    if RATE_LIMIT_BLOCK_TOTAL is not None:
        RATE_LIMIT_BLOCK_TOTAL.labels(service, limiter).inc()
