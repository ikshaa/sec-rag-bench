"""
Observability for the API: Prometheus metrics and structured JSON logging.

- Metrics are exposed on /metrics for Prometheus to scrape
- Logs are emitted as JSON lines to stdout, one per structured event

Trace IDs are generated per request so you can grep by trace_id to see
every log line for one specific request.
"""

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager

from prometheus_client import Counter, Histogram, Gauge

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

QUERIES_TOTAL = Counter(
    "secrag_queries_total",
    "Total number of /query requests",
    labelnames=["cache_hit", "provider", "fallback_used"],
)

QUERY_LATENCY_MS = Histogram(
    "secrag_query_latency_ms",
    "Latency of /query requests in milliseconds",
    labelnames=["cache_hit"],
    buckets=[50, 100, 250, 500, 1000, 2000, 5000, 10000, 30000],
)

CACHE_SIZE = Gauge(
    "secrag_cache_size",
    "Current number of entries in the semantic cache",
)

ERRORS_TOTAL = Counter(
    "secrag_errors_total",
    "Total errors, labeled by type",
    labelnames=["error_type"],
)


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record):
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        # Attach any custom fields passed via extra={...}
        for key, value in record.__dict__.items():
            if key not in self.RESERVED:
                entry[key] = value
        return json.dumps(entry)


def _setup_logging() -> logging.Logger:
    """Configure stdout logging with JSON formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    return logging.getLogger("secrag")


log = _setup_logging()


# ---------------------------------------------------------------------------
# Trace context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace_request(path: str):
    """
    Generate a trace_id for a request and log start/finish events.
    Usage:
        with trace_request("/query") as trace_id:
            log.info("something_happened", extra={"trace_id": trace_id})
    """
    trace_id = str(uuid.uuid4())[:8]
    start = time.time()
    log.info("request_started", extra={"trace_id": trace_id, "path": path})
    try:
        yield trace_id
    finally:
        duration_ms = int((time.time() - start) * 1000)
        log.info("request_finished", extra={
            "trace_id": trace_id,
            "path": path,
            "duration_ms": duration_ms,
        })