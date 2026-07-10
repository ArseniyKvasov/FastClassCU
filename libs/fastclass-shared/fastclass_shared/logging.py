from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from fastclass_shared.context import clear_context, get_actor_context, set_request_id
from fastclass_shared.tracing import configure_tracing, current_traceparent, ensure_trace_context, start_span


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update(get_actor_context())
        for key in (
            "service",
            "method",
            "path",
            "query_string",
            "status_code",
            "latency_ms",
            "client_ip",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class ConsoleLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname} {record.name}: {record.getMessage()}"
        context = get_actor_context()
        if not context:
            return base
        context_str = " ".join(f"{key}={value}" for key, value in context.items())
        return f"{base} [{context_str}]"


def configure_logging(service_name: str) -> None:
    root = logging.getLogger()
    if getattr(root, "_fastclass_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    log_format = os.getenv("FASTCLASS_LOG_FORMAT", "json").strip().lower()
    handler.setFormatter(ConsoleLogFormatter() if log_format == "console" else JsonLogFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.getenv("FASTCLASS_LOG_LEVEL", "INFO").upper())
    root._fastclass_configured = True  # type: ignore[attr-defined]

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger(service_name).info(
        "logging_configured", extra={"service": service_name}
    )
    configure_tracing(service_name)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service_name: str):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logging.getLogger(f"{service_name}.http")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        ensure_trace_context(request.headers.get("traceparent"))
        started = time.perf_counter()
        with start_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.route": request.url.path,
                "fastclass.request_id": request_id,
            },
        ):
            try:
                response = await call_next(request)
            except Exception:
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                self.logger.exception(
                    "request_failed",
                    extra={
                        "service": self.service_name,
                        "method": request.method,
                        "path": request.url.path,
                        "query_string": request.url.query or None,
                        "status_code": 500,
                        "latency_ms": latency_ms,
                        "client_ip": request.client.host if request.client else None,
                    },
                )
                clear_context()
                raise

            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            traceparent = current_traceparent()
            if traceparent:
                response.headers["traceparent"] = traceparent
            self.logger.info(
                "request_completed",
                extra={
                    "service": self.service_name,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query or None,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            clear_context()
            return response


def install_request_middleware(app: FastAPI, *, service_name: str) -> None:
    app.add_middleware(RequestContextMiddleware, service_name=service_name)
