"""Correlation ID middleware uses request-scoped ContextVar (no global overwrite)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.correlation import (  # noqa: E402
    CORRELATION_HEADER,
    CorrelationIdFilter,
    CorrelationIdMiddleware,
    get_correlation_id,
)
from app.core import logging_config  # noqa: F401, E402


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo-corr")
    def echo():
        logging.getLogger("test.corr").info("inside handler")
        return {"id": get_correlation_id()}

    return app


def test_reuses_inbound_correlation_header():
    client = TestClient(_build_app())
    r = client.get("/echo-corr", headers={CORRELATION_HEADER: "presidio-corr-1"})
    assert r.status_code == 200
    assert r.json()["id"] == "presidio-corr-1"
    assert r.headers.get(CORRELATION_HEADER) == "presidio-corr-1"


def test_generates_when_missing():
    client = TestClient(_build_app())
    r = client.get("/echo-corr")
    assert r.status_code == 200
    cid = r.json()["id"]
    assert cid and cid != "-"
    assert r.headers.get(CORRELATION_HEADER) == cid


def test_logging_filter_reads_contextvar():
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "msg", (), None)
    CorrelationIdFilter().filter(record)
    assert hasattr(record, "correlation_id")
