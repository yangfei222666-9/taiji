#!/usr/bin/env python3
"""
Structured Logging for AIOS

Replaces print() with structured JSON logging.

Features:
- JSON format
- Contextual fields (agent_id, task_id, trace_id)
- Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Searchable and parseable
- Automatic context propagation

Usage:
    from structured_logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Task started", agent_id="agent-001", task_id="task-123")
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import contextvars

# Context variables for automatic propagation
agent_id_var = contextvars.ContextVar('agent_id', default=None)
task_id_var = contextvars.ContextVar('task_id', default=None)
trace_id_var = contextvars.ContextVar('trace_id', default=None)

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add context from contextvars
        agent_id = agent_id_var.get()
        if agent_id:
            log_data["agent_id"] = agent_id
        
        task_id = task_id_var.get()
        if task_id:
            log_data["task_id"] = task_id
        
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id
        
        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)

class StructuredLogger(logging.LoggerAdapter):
    """Logger adapter that adds structured fields"""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add extra fields"""
        # Extract extra fields
        extra_fields = {}
        for key in list(kwargs.keys()):
            if key not in ['exc_info', 'stack_info', 'stacklevel', 'extra']:
                extra_fields[key] = kwargs.pop(key)
        
        # Add to extra
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['extra_fields'] = extra_fields
        
        return msg, kwargs

def get_logger(name: str, level: int = logging.INFO) -> StructuredLogger:
    """
    Get a structured logger
    
    Args:
        name: Logger name (usually __name__)
        level: Log level (default: INFO)
        
    Returns:
        StructuredLogger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    
    return StructuredLogger(logger, {})

def set_context(agent_id: Optional[str] = None, 
                task_id: Optional[str] = None, 
                trace_id: Optional[str] = None):
    """
    Set logging context
    
    Args:
        agent_id: Agent ID
        task_id: Task ID
        trace_id: Trace ID for distributed tracing
    """
    if agent_id:
        agent_id_var.set(agent_id)
    if task_id:
        task_id_var.set(task_id)
    if trace_id:
        trace_id_var.set(trace_id)

def clear_context():
    """Clear logging context"""
    agent_id_var.set(None)
    task_id_var.set(None)
    trace_id_var.set(None)


# ── TaijiOS 扩展：env/job/run_id + JSONL 落盘 ────────────────────────

import os
import socket
import uuid
from pathlib import Path


def _taiji_env() -> str:
    return os.environ.get("TAIJI_ENV", "prod")


def _log_dir() -> Path:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from config_center import agent_system_data_dir
        return agent_system_data_dir() / "logs"
    except Exception:
        env = _taiji_env()
        return Path(__file__).resolve().parents[2] / "aios" / "agent_system" / "data" / env / "logs"


class TaijiLogger:
    """
    TaijiOS 结构化日志记录器。
    输出 JSON 格式，含 env/job/trace_id/run_id，落盘到 JSONL 文件。

    用法：
        from structured_logger import new_logger
        log = new_logger("hourly_s1", run_id="20260319_162800")
        log.info("任务开始")
        log.error("失败", reason_code="smoke_failed", exit_code=1)
    """

    def __init__(self, job: str, trace_id: str = "", run_id: str = "", echo_stderr: bool = True):
        self.job = job
        self.trace_id = trace_id or uuid.uuid4().hex[:12]
        self.run_id = run_id
        self.echo_stderr = echo_stderr
        self._fh = None

    def _open(self):
        if self._fh is None:
            d = _log_dir()
            d.mkdir(parents=True, exist_ok=True)
            try:
                self._fh = open(d / "structured.jsonl", "a", encoding="utf-8")
            except Exception:
                pass

    def _write(self, level: str, message: str, **kw):
        record = {
            "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": level,
            "env": _taiji_env(),
            "job": self.job,
            "trace_id": self.trace_id,
            "host": socket.gethostname(),
            "message": message,
        }
        if self.run_id:
            record["run_id"] = self.run_id
        record.update(kw)

        line = json.dumps(record, ensure_ascii=False)
        self._open()
        if self._fh:
            try:
                self._fh.write(line + "\n")
                self._fh.flush()
            except Exception:
                pass
        if self.echo_stderr:
            print(f"[{record['ts']}][{level}][{self.job}] {message}", file=sys.stderr, flush=True)

    def debug(self, msg: str, **kw):    self._write("DEBUG", msg, **kw)
    def info(self, msg: str, **kw):     self._write("INFO", msg, **kw)
    def warn(self, msg: str, **kw):     self._write("WARN", msg, **kw)
    def error(self, msg: str, **kw):    self._write("ERROR", msg, **kw)
    def critical(self, msg: str, **kw): self._write("CRITICAL", msg, **kw)

    def close(self):
        if self._fh:
            try: self._fh.close()
            except Exception: pass
            self._fh = None


def new_logger(job: str, trace_id: str = "", run_id: str = "", echo_stderr: bool = True) -> TaijiLogger:
    """每次调用创建新 logger（新 trace_id），用于独立执行链路。"""
    return TaijiLogger(job=job, trace_id=trace_id, run_id=run_id, echo_stderr=echo_stderr)

# Example usage and demo
if __name__ == "__main__":
    print("=" * 80)
    print("  Structured Logging - Demo")
    print("=" * 80)
    print()
    
    # Get logger
    logger = get_logger(__name__)
    
    # Basic logging
    print("Basic logging:")
    logger.info("Application started")
    logger.warning("This is a warning")
    logger.error("This is an error")
    print()
    
    # Logging with extra fields
    print("Logging with extra fields:")
    logger.info("Task started", task_type="analysis", priority="high")
    logger.info("Processing data", records_processed=1000, duration_ms=250)
    print()
    
    # Logging with context
    print("Logging with context:")
    set_context(agent_id="agent-001", task_id="task-123", trace_id="trace-abc")
    logger.info("Task executing")
    logger.info("Step 1 completed", step="data_loading")
    logger.info("Step 2 completed", step="data_processing")
    clear_context()
    print()
    
    # Logging with exception
    print("Logging with exception:")
    try:
        raise ValueError("Something went wrong")
    except Exception as e:
        logger.error("Task failed", error_type="ValueError", exc_info=True)
    print()
    
    print("=" * 80)
    print("  Demo completed!")
    print("=" * 80)
