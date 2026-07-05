"""Structured JSON logging for PolarisGate services.
Enterprise-grade: JSON-formatted logs with service name, correlation IDs, and log levels.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging.
    
    Produces JSON-formatted log entries parsable by log aggregators
    (Loki, ELK, CloudWatch, etc.).
    """
    
    def __init__(self, service_name: str = "polarisgate"):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }
        
        # Include extra fields passed to logger
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, default=str)


def setup_logging(
    service_name: str = "polarisgate",
    log_level: str = "INFO",
    json_format: bool = True,
) -> None:
    """Configure structured logging for a service.
    
    Args:
        service_name: Name of the service for log identification
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, use JSON format; otherwise use standard format
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if json_format:
        handler.setFormatter(JSONFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    
    root_logger.addHandler(handler)
    
    # Set third-party loggers to WARNING to reduce noise
    for logger_name in ["uvicorn", "uvicorn.access", "httpx", "asyncio"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


class LoggerAdapter(logging.LoggerAdapter):
    """Adapter that adds extra fields to all log messages."""
    
    def __init__(self, logger: logging.Logger, extra: Optional[dict] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.setdefault("extra_fields", self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
