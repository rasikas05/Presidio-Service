import logging

from app.core.correlation import CorrelationIdFilter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
)

# Ensure root logger records always carry correlation_id (ContextVar-backed).
_root = logging.getLogger()
_root.addFilter(CorrelationIdFilter())
for _handler in _root.handlers:
    _handler.addFilter(CorrelationIdFilter())

logger = logging.getLogger(__name__)
