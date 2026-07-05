"""OpenTelemetry setup with configurable OTLP exporter."""
import os
import logging
from typing import Optional
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    BatchSpanProcessor,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

logger = logging.getLogger(__name__)


def setup_otel(app: FastAPI, service_name: str = None) -> None:
    """Configure OpenTelemetry with console exporter and optional OTLP exporter.
    
    If OTEL_EXPORTER_OTLP_ENDPOINT is set, traces will be sent to that endpoint
    via the OTLP HTTP protocol. Console exporter is always enabled for debugging.
    
    Also instruments the FastAPI app for automatic span creation.
    """
    provider = TracerProvider()

    # Always log to console for debugging
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    # Optionally export to OTLP endpoint (e.g., Jaeger, Tempo, Grafana)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        logger.info(f"OTLP exporter enabled: {otlp_endpoint}")
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{otlp_endpoint}/v1/traces",
            headers={
                "Content-Type": "application/json",
            },
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        logger.info("OTLP exporter disabled (set OTEL_EXPORTER_OTLP_ENDPOINT to enable)")

    trace.set_tracer_provider(provider)
    
    # Instrument FastAPI for automatic span creation
    if app:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logger.info(f"FastAPI instrumented for service: {service_name or 'unknown'}")
