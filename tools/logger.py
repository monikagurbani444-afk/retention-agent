import functools
import json
import os
from datetime import datetime, timezone


def _log_path():
    return os.environ.get("RETENTION_LOG_PATH", "data/tool_calls.jsonl")


def logged(fn):
    """Decorator: records every call to a tool, its inputs and its outcome."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        entry = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": fn.__name__,
            "inputs": {"args": args, "kwargs": kwargs},
            "status": result.get("status"),
            "reason": result.get("reason"),
        }
        try:
            with open(_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass   # logging must never break a tool
        return result
    return wrapper