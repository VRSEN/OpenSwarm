from __future__ import annotations

import atexit
import hashlib
import hmac
import importlib.util
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
STATE_VERSION = 1
_MODULE_DIR = Path(__file__).resolve().parent
_STATE_FILE_NAME = "telemetry.json"
_SESSION_ID = uuid.uuid4().hex

ALLOWED_PROPERTIES = {
    "agent_id",
    "agent_name",
    "agent_run_id",
    "auth_method",
    "caller_agent_name",
    "cost_usd",
    "error_category",
    "error_type",
    "event_version",
    "has_provider_key",
    "http_status",
    "install_source",
    "is_streaming",
    "latency_ms",
    "message_role",
    "message_type",
    "model",
    "parent_agent_id",
    "parent_run_id",
    "provider",
    "run_trace_id",
    "session_id",
    "status",
    "stop_reason",
    "thread_id",
    "tokens_input",
    "tokens_output",
    "tool_name",
    "user_id",
    "workspace_id",
}

ALLOWED_EVENTS = {
    "agent_run_completed",
    "agent_run_started",
    "app_started",
    "error",
    "handoff",
    "install_created",
    "llm_generation_completed",
    "message_sent",
    "onboarding_completed",
    "provider_configured",
    "swarm_run_completed",
    "swarm_run_started",
    "telemetry_smoke_test",
    "tool_invoked",
}

BASE_PROPERTIES = {"event_version", "session_id", "user_id", "workspace_id"}
BOOLEAN_PROPERTIES = {"has_provider_key", "is_streaming"}
INTEGER_PROPERTIES = {"http_status", "latency_ms", "tokens_input", "tokens_output"}
FLOAT_PROPERTIES = {"cost_usd"}
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}$")
SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
EMAIL_RE = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|bearer|sk-[A-Za-z0-9_-]{8,}|"
    r"sk-proj-[A-Za-z0-9_-]{8,}|phc_[A-Za-z0-9_-]{8,}|phx_[A-Za-z0-9_-]{8,}|"
    r"AIza[A-Za-z0-9_-]{8,}|xox[baprs]-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_-]{8,})"
)
PATH_RE = re.compile(r"(?i)(^/|^\./|^\.\./|^~/|^[A-Za-z]:[\\/]|[\\]|/(Users|home|private|var|tmp)/|//)")

CONTENT_LIKE_KEYS = {
    "arguments",
    "content",
    "exception_message",
    "file_path",
    "input",
    "input_text",
    "message",
    "output",
    "output_text",
    "path",
    "prompt",
    "stack",
    "tool_args",
    "tool_result",
    "traceback",
}

_client: Any | None = None
_client_config: dict[str, str | None] | None = None
_posthog_factory: Callable[[str, str], Any] | None = None
_state_cache: dict[str, Any] | None = None
_state_created = False


def _config_dir() -> Path:
    custom = os.getenv("OPENSWARM_CONFIG_DIR")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".openswarm"


def _state_path() -> Path:
    return _config_dir() / _STATE_FILE_NAME


def _load_state() -> dict[str, Any]:
    global _state_cache, _state_created
    if _state_cache is not None:
        return _state_cache

    path = _state_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("install_id") and data.get("install_secret"):
                _state_cache = data
                return _state_cache
        except Exception:
            logger.debug("Could not read telemetry state", exc_info=True)

    _state_created = True
    _state_cache = {
        "version": STATE_VERSION,
        "install_id": uuid.uuid4().hex,
        "install_secret": uuid.uuid4().hex + uuid.uuid4().hex,
        "install_created_captured": False,
    }
    _save_state()
    return _state_cache


def _save_state() -> None:
    if _state_cache is None:
        return
    try:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_state_cache, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        logger.debug("Could not write telemetry state", exc_info=True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _install_secret() -> bytes:
    state = _load_state()
    return str(state["install_secret"]).encode("utf-8")


def hashed_identifier(namespace: str, value: Any) -> str:
    return hmac.new(_install_secret(), f"{namespace}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def user_id() -> str:
    state = _load_state()
    return _sha256(f"openswarm:user:{state['install_id']}")


def workspace_id(path: str | Path | None = None) -> str:
    candidate = Path(path or os.getcwd()).expanduser()
    try:
        normalized = str(candidate.resolve())
    except Exception:
        normalized = str(candidate.absolute())
    return hashed_identifier("workspace", normalized)


def thread_id(value: Any) -> str:
    return hashed_identifier("thread", value)


def agent_id(agent_name: str | None) -> str | None:
    if not agent_name:
        return None
    return hashed_identifier("agent", agent_name)


def _load_generated_config() -> dict[str, str]:
    config_path = _MODULE_DIR / "openswarm_telemetry_config.py"
    if not config_path.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location("_openswarm_telemetry_config", config_path)
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return {
            "POSTHOG_API_KEY": str(getattr(module, "POSTHOG_API_KEY", "") or ""),
            "POSTHOG_HOST": str(getattr(module, "POSTHOG_HOST", "") or ""),
        }
    except Exception:
        logger.debug("Could not load generated telemetry config", exc_info=True)
        return {}


def _running_in_tests_or_ci() -> bool:
    if os.getenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", "").strip().lower() in TRUE_VALUES:
        return False
    if os.getenv("CI", "").strip().lower() in TRUE_VALUES:
        return True
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_VERSION"):
        return True
    return False


def _is_opted_out() -> bool:
    telemetry_env = os.getenv("OPENSWARM_TELEMETRY")
    if telemetry_env is not None and telemetry_env.strip().lower() in FALSE_VALUES:
        return True
    if os.getenv("DO_NOT_TRACK") == "1":
        return True
    return _running_in_tests_or_ci()


def _resolve_client_config() -> dict[str, str | None]:
    global _client_config
    if _client_config is not None:
        return _client_config

    generated = _load_generated_config()
    env_key = os.getenv("POSTHOG_API_KEY")
    env_host = os.getenv("POSTHOG_HOST")

    api_key = env_key or generated.get("POSTHOG_API_KEY") or None
    host = env_host or generated.get("POSTHOG_HOST") or DEFAULT_POSTHOG_HOST
    source = "env" if env_key else ("npm_config" if generated.get("POSTHOG_API_KEY") else None)

    _client_config = {
        "api_key": api_key,
        "host": host,
        "source": source,
    }
    return _client_config


def is_enabled() -> bool:
    if _is_opted_out():
        return False
    return bool(_resolve_client_config().get("api_key"))


def config_source() -> str | None:
    return _resolve_client_config().get("source")


def has_posthog_key() -> bool:
    return bool(_resolve_client_config().get("api_key"))


def _create_posthog_client(api_key: str, host: str) -> Any:
    if _posthog_factory is not None:
        return _posthog_factory(api_key, host)

    os.environ.setdefault("POSTHOG_ENABLE_EXCEPTION_AUTOCAPTURE", "false")
    os.environ.setdefault("POSTHOG_CAPTURE_EXCEPTION_CODE_VARIABLES", "false")

    from posthog import Posthog  # type: ignore

    try:
        return Posthog(
            api_key,
            host=host,
            disable_geoip=True,
            enable_exception_autocapture=False,
            capture_exception_code_variables=False,
        )
    except TypeError:
        pass
    try:
        return Posthog(api_key, host=host, disable_geoip=True)
    except TypeError:
        return Posthog(api_key, host=host)


def _get_client() -> Any | None:
    global _client
    if not is_enabled():
        return None
    if _client is not None:
        return _client

    config = _resolve_client_config()
    api_key = config.get("api_key")
    host = config.get("host") or DEFAULT_POSTHOG_HOST
    if not api_key:
        return None

    try:
        _client = _create_posthog_client(str(api_key), str(host))
        atexit.register(shutdown)
    except Exception:
        logger.debug("Could not initialize PostHog telemetry client", exc_info=True)
        _client = None
    return _client


def provider_from_model(model: Any) -> str | None:
    if model is None:
        return None
    name = str(model)
    if "/" not in name:
        safe_model = sanitize_model_id(name)
        if safe_model and safe_model.startswith(("gpt-", "o")):
            return "openai"
        return None
    parts = name.split("/")
    provider: str | None
    if parts[0] == "litellm" and len(parts) > 1:
        provider = parts[1]
    else:
        provider = parts[0]
    return sanitize_provider(provider)


def configured_provider() -> str | None:
    model = os.getenv("DEFAULT_MODEL", "")
    if model:
        provider = provider_from_model(model)
        if provider:
            return provider
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GOOGLE_API_KEY"):
        return "google"
    return None


def has_provider_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _looks_private(value: str) -> bool:
    return bool(EMAIL_RE.search(value) or SECRET_RE.search(value) or PATH_RE.search(value))


def sanitize_model_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    model = value.strip()
    if not model or len(model) > 128:
        return None
    if not MODEL_ID_RE.fullmatch(model):
        return None
    if _looks_private(model):
        return None
    return model


def sanitize_provider(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    provider = value.strip()
    if not provider or not SAFE_SLUG_RE.fullmatch(provider):
        return None
    if _looks_private(provider):
        return None
    return provider


def _safe_property(key: str, value: Any) -> str | int | float | bool | None:
    if key in BASE_PROPERTIES:
        return None
    if key == "model":
        return sanitize_model_id(value)
    if key == "provider":
        return sanitize_provider(value)
    if key in BOOLEAN_PROPERTIES:
        return value if isinstance(value, bool) else None
    if key in INTEGER_PROPERTIES:
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if key in FLOAT_PROPERTIES:
        return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
    if value is None:
        return None
    if isinstance(value, str):
        return value[:256]
    if isinstance(value, bool | int | float):
        return value
    return None


def sanitize_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {
        "event_version": 1,
        "user_id": user_id(),
        "workspace_id": workspace_id(),
        "session_id": _SESSION_ID,
    }
    if not properties:
        return safe
    for key, value in properties.items():
        if key not in ALLOWED_PROPERTIES:
            continue
        if key in CONTENT_LIKE_KEYS:
            continue
        scalar = _safe_property(key, value)
        if scalar is not None:
            safe[key] = scalar
    return safe


def capture(event: str, properties: dict[str, Any] | None = None) -> bool:
    if event not in ALLOWED_EVENTS:
        logger.debug("Telemetry event %s is not allowlisted", event)
        return False
    client = _get_client()
    if client is None:
        return False
    props = sanitize_properties(properties)
    try:
        client.capture(event=event, distinct_id=props["user_id"], properties=props)
        return True
    except TypeError:
        try:
            client.capture(distinct_id=props["user_id"], event=event, properties=props)
            return True
        except Exception:
            logger.debug("PostHog capture failed for event %s", event, exc_info=True)
            return False
    except Exception:
        logger.debug("PostHog capture failed for event %s", event, exc_info=True)
        return False


def capture_error(error: BaseException, *, category: str, properties: dict[str, Any] | None = None) -> bool:
    props = dict(properties or {})
    props.update(
        {
            "error_type": error.__class__.__name__,
            "error_category": category,
            "status": props.get("status") or "error",
        }
    )
    return capture("error", props)


def capture_app_started(*, install_source: str | None = None) -> None:
    if not is_enabled():
        return
    state = _load_state()
    if not state.get("install_created_captured"):
        if capture(
            "install_created",
            {
                "install_source": install_source or config_source() or "source",
                "has_provider_key": has_provider_key(),
                "provider": configured_provider(),
            },
        ):
            state["install_created_captured"] = True
            _save_state()
    capture(
        "app_started",
        {
            "install_source": install_source or config_source() or "source",
            "has_provider_key": has_provider_key(),
            "provider": configured_provider(),
        },
    )


def capture_onboarding_completed(*, provider: str | None, auth_method: str = "api_key") -> None:
    capture(
        "onboarding_completed",
        {
            "auth_method": auth_method,
            "provider": provider,
            "has_provider_key": has_provider_key(),
            "install_source": config_source() or "source",
        },
    )


def capture_provider_configured(*, provider: str | None, auth_method: str = "api_key") -> None:
    capture(
        "provider_configured",
        {
            "auth_method": auth_method,
            "provider": provider,
            "has_provider_key": has_provider_key(),
            "install_source": config_source() or "source",
        },
    )


def shutdown() -> None:
    if _client is None:
        return
    for method_name in ("shutdown", "flush"):
        method = getattr(_client, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                logger.debug("PostHog telemetry shutdown failed", exc_info=True)
            break


def set_posthog_factory_for_tests(factory: Callable[[str, str], Any] | None) -> None:
    global _posthog_factory, _client
    _posthog_factory = factory
    _client = None


def _reset_for_tests() -> None:
    global _client, _client_config, _posthog_factory, _state_cache, _state_created
    _client = None
    _client_config = None
    _posthog_factory = None
    _state_cache = None
    _state_created = False
