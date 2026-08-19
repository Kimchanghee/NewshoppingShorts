"""Live, secret-safe validation for configured Gemini API keys."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import requests


GEMINI_GENERATE_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


def _probe_one(
    alias: str,
    key_value: str,
    timeout_seconds: float,
    model: str,
) -> dict[str, Any]:
    try:
        response = requests.post(
            GEMINI_GENERATE_URL_TEMPLATE.format(model=model),
            params={"key": key_value},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": "Reply only: OK"}]}
                ],
                "generationConfig": {"maxOutputTokens": 4, "temperature": 0},
            },
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return {
            "alias": alias,
            "state": "unreachable",
            "http_status": 0,
            "reason": type(exc).__name__,
        }

    if response.status_code == 200:
        return {
            "alias": alias,
            "state": "valid",
            "http_status": 200,
            "reason": "",
        }

    google_status = ""
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            google_status = str(error.get("status") or "").strip()
    except (TypeError, ValueError):
        pass

    if response.status_code == 429:
        state = "quota"
    elif response.status_code >= 500:
        state = "unreachable"
    else:
        state = "rejected"

    return {
        "alias": alias,
        "state": state,
        "http_status": int(response.status_code),
        "reason": google_status,
    }


def probe_gemini_keys(
    api_keys: Mapping[str, str],
    *,
    timeout_seconds: float = 8.0,
    model: str = "gemini-3.5-flash",
) -> dict[str, Any]:
    """Validate keys concurrently without returning or logging secret values."""
    normalized = {
        str(alias): str(value).strip()
        for alias, value in dict(api_keys or {}).items()
        if str(value or "").strip()
    }
    if not normalized:
        return {
            "ok": False,
            "reason": "gemini_api_keys_missing",
            "valid": [],
            "rejected": [],
            "quota": [],
            "unreachable": [],
        }

    results: list[dict[str, Any]] = []
    max_workers = min(4, len(normalized))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _probe_one,
                alias,
                value,
                timeout_seconds,
                str(model or "gemini-3.5-flash").strip(),
            ): alias
            for alias, value in normalized.items()
        }
        for future in as_completed(futures):
            alias = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "alias": alias,
                        "state": "unreachable",
                        "http_status": 0,
                        "reason": type(exc).__name__,
                    }
                )

    results.sort(key=lambda item: str(item.get("alias") or ""))
    valid = [item for item in results if item.get("state") == "valid"]
    rejected = [item for item in results if item.get("state") == "rejected"]
    quota = [item for item in results if item.get("state") == "quota"]
    unreachable = [item for item in results if item.get("state") == "unreachable"]
    reason = (
        "gemini_api_key_available"
        if valid
        else "gemini_api_quota_exhausted"
        if quota and not rejected
        else "gemini_api_probe_unreachable"
        if unreachable and not rejected and not quota
        else "gemini_api_keys_rejected"
    )
    return {
        "ok": bool(valid),
        "reason": reason,
        "valid": valid,
        "rejected": rejected,
        "quota": quota,
        "unreachable": unreachable,
    }
