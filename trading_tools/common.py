from __future__ import annotations

import importlib.util
import os
import socket
from contextlib import closing
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def package_available(package_name: str) -> bool:
    return importlib.util.find_spec(package_name) is not None


def env_present(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class IBKRSettings:
    host: str
    port: int
    client_id: int
    account: str | None
    readonly: bool


def ibkr_settings() -> IBKRSettings:
    return IBKRSettings(
        host=os.getenv("IBKR_HOST", "127.0.0.1"),
        port=int_env("IBKR_PORT", 7497),
        client_id=int_env("IBKR_CLIENT_ID", 19),
        account=os.getenv("IBKR_ACCOUNT") or None,
        readonly=bool_env("IBKR_READONLY", True),
    )


def socket_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with closing(socket.create_connection((host, port), timeout=timeout)):
            return True
    except OSError:
        return False


def compact_error(exc: Exception) -> dict[str, str]:
    return {"type": exc.__class__.__name__, "message": str(exc)}


def dataframe_tail_json(df: Any, rows: int = 5) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return df.tail(rows).reset_index().to_dict(orient="records")
