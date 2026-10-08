from __future__ import annotations

import pytest
from celery import Celery
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_task_without_incoming_trace_context_finishes_span_without_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = CeleryInstrumentor()
    app = Celery("tracing-test", broker="memory://", backend="cache+memory://")
    app.conf.task_always_eager = True

    @app.task
    def untraced_task() -> str:
        return "ok"

    instrumentor.instrument(tracer_provider=provider)
    try:
        assert untraced_task.apply().get() == "ok"
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name.endswith("untraced_task")
        assert "Failed to detach context" not in caplog.text
    finally:
        instrumentor.uninstrument()
        provider.shutdown()
        app.close()
