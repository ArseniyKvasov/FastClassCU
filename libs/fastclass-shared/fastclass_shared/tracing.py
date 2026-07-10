from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from typing import Iterator

from fastclass_shared.context import get_span_id, get_trace_id, set_trace_context

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # pragma: no cover - optional until deps are installed
    trace = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None


def _new_trace_id() -> str:
    return secrets.token_hex(16)


def _new_span_id() -> str:
    return secrets.token_hex(8)


def parse_traceparent(header: str | None) -> tuple[str, str] | None:
    if not header:
        return None
    parts = header.strip().split("-")
    if len(parts) != 4:
        return None
    version, trace_id, span_id, flags = parts
    if version != "00" or len(trace_id) != 32 or len(span_id) != 16 or len(flags) != 2:
        return None
    try:
        int(trace_id, 16)
        int(span_id, 16)
        int(flags, 16)
    except ValueError:
        return None
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return trace_id.lower(), span_id.lower()


def ensure_trace_context(traceparent: str | None = None) -> tuple[str, str]:
    parsed = parse_traceparent(traceparent)
    trace_id = parsed[0] if parsed else _new_trace_id()
    span_id = _new_span_id()
    set_trace_context(trace_id=trace_id, span_id=span_id)
    return trace_id, span_id


def current_traceparent() -> str | None:
    trace_id = get_trace_id()
    span_id = get_span_id()
    if not trace_id or not span_id:
        return None
    return f"00-{trace_id}-{span_id}-01"


def configure_tracing(service_name: str) -> None:
    if trace is None or TracerProvider is None or Resource is None:
        return
    provider = trace.get_tracer_provider()
    if getattr(provider, "_fastclass_configured", False):
        return

    otel_provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint and OTLPSpanExporter is not None and BatchSpanProcessor is not None:
        exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")
        otel_provider.add_span_processor(BatchSpanProcessor(exporter))
    otel_provider._fastclass_configured = True  # type: ignore[attr-defined]
    trace.set_tracer_provider(otel_provider)


@contextmanager
def start_span(name: str, *, attributes: dict[str, object] | None = None) -> Iterator[None]:
    if trace is None:
        yield
        return
    tracer = trace.get_tracer("fastclass")
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        trace_id = get_trace_id()
        request_span_id = get_span_id()
        if trace_id:
            span.set_attribute("fastclass.trace_id", trace_id)
        if request_span_id:
            span.set_attribute("fastclass.span_id", request_span_id)
        yield
