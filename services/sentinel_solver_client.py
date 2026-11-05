"""Client for the private Chromium-backed sentinel solver service.

Only challenge material is sent to the solver. Account tokens, cookies, and
user prompts remain in the main process.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from curl_cffi import requests

from services.config import config
from utils.log import logger

SOLVER_TIMEOUT_SECONDS = 20
SOLVER_SOLVE_TIMEOUT_SECONDS = 60
USER_AGENT_CACHE_SECONDS = 600
USER_AGENT_FAILURE_CACHE_SECONDS = 30

_user_agent_lock = threading.Lock()
_user_agent_cache: dict[str, object] = {"url": "", "value": "", "expires_at": 0.0}


class SentinelSolverError(RuntimeError):
    """The solver is unconfigured or could not produce a token."""


def _solver_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.sentinel_solver_key:
        headers["Authorization"] = f"Bearer {config.sentinel_solver_key}"
    return headers


def solver_user_agent() -> str:
    """Return the Chromium UA used by the solver, if it is reachable."""
    base_url = config.sentinel_solver_url
    if not base_url:
        return ""
    with _user_agent_lock:
        now = time.monotonic()
        if _user_agent_cache["url"] == base_url and now < float(_user_agent_cache["expires_at"]):
            return str(_user_agent_cache["value"])
        value = ""
        try:
            response = requests.get(
                f"{base_url}/health",
                headers=_solver_headers(),
                timeout=SOLVER_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                value = str((response.json() or {}).get("user_agent") or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning({"event": "sentinel_solver_health_error", "error": str(exc)})
        ttl = USER_AGENT_CACHE_SECONDS if value else USER_AGENT_FAILURE_CACHE_SECONDS
        _user_agent_cache.update(url=base_url, value=value, expires_at=now + ttl)
        return value


def solve_turnstile(dx: str, p: str, requirements: dict[str, Any] | None = None) -> str:
    """Solve a Turnstile challenge in the private Chromium service."""
    base_url = config.sentinel_solver_url
    if not base_url:
        raise SentinelSolverError(
            "sentinel solver is not configured (CHATGPT2API_SENTINEL_SOLVER_URL / config.json sentinel_solver_url)"
        )
    body: dict[str, object] = {"dx": dx, "p": p}
    if requirements:
        body["requirements"] = requirements
    try:
        response = requests.post(
            f"{base_url}/v1/turnstile",
            headers=_solver_headers(),
            json=body,
            timeout=SOLVER_SOLVE_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning({"event": "sentinel_solver_error", "error": str(exc)})
        raise SentinelSolverError(f"sentinel solver request failed: {exc}") from exc

    if response.status_code != 200:
        logger.warning({
            "event": "sentinel_solver_failed",
            "status": response.status_code,
            "body": str(response.text or "")[:200],
        })
        raise SentinelSolverError(
            f"sentinel solver returned HTTP {response.status_code}: {str(response.text or '')[:200]}"
        )

    token = str((response.json() or {}).get("token") or "")
    if not token:
        raise SentinelSolverError("sentinel solver returned an empty turnstile token")
    return token
