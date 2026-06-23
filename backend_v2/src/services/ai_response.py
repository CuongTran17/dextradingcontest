from __future__ import annotations

import json
import re
from typing import Any


def extract_kaggle_output_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""

    for key in (
        "raw_response",
        "raw_output",
        "raw_text",
        "output",
        "response",
        "content",
        "message",
        "text",
        "answer",
        "thinking",
        "reasoning",
        "conclusion",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("data", "result", "analysis", "payload"):
        nested_text = extract_kaggle_output_text(payload.get(key))
        if nested_text:
            return nested_text

    return json.dumps(payload, ensure_ascii=False)


def _normalize_decision(value: Any, raw_output: str) -> str:
    candidate = str(value or "").upper().strip()
    if candidate in {"BUY", "SELL", "HOLD"}:
        return candidate
    match = re.search(r"(?:FINAL\s+DECISION|DECISION)\s*:\s*(BUY|SELL|HOLD)", raw_output, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "HOLD"


def _normalize_confidence(value: Any, raw_output: str) -> float:
    candidate = value
    if candidate is None:
        match = re.search(r"CONFIDENCE\s*:\s*([0-9]+(?:\.[0-9]+)?)", raw_output, re.IGNORECASE)
        candidate = match.group(1) if match else 50
    try:
        score = float(candidate)
    except (TypeError, ValueError):
        score = 50.0
    if score > 1:
        score = score / 100.0
    return max(0.0, min(score, 1.0))


def _normalize_key_factors(payload: dict[str, Any], raw_output: str) -> list[str]:
    factors = payload.get("key_factors")
    if factors is None:
        factors = payload.get("factors")
    if isinstance(factors, list):
        return [str(item).strip() for item in factors if str(item).strip()]
    if isinstance(factors, str) and factors.strip():
        stripped = factors.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

    match = re.search(r"KEY_FACTORS\s*:\s*(.+)", raw_output, re.IGNORECASE | re.DOTALL)
    if not match:
        return [stripped] if isinstance(factors, str) and stripped else []
    tail = re.split(
        r"\n\s*(?:FINAL DECISION|CONFIDENCE|CONCLUSION)",
        match.group(1),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    chunks: list[str] = []
    for line in tail.splitlines() or [tail]:
        chunks.extend(line.split(","))
    return [chunk.strip().strip("-* ") for chunk in chunks if chunk.strip().strip("-* ")]


def normalize_kaggle_response(payload: dict[str, Any]) -> dict[str, Any]:
    raw_output = extract_kaggle_output_text(payload)
    decision = _normalize_decision(payload.get("decision"), raw_output)
    confidence = _normalize_confidence(payload.get("confidence"), raw_output)
    reasoning = str(payload.get("conclusion") or payload.get("reasoning") or raw_output or "").strip()
    key_factors = _normalize_key_factors(payload, raw_output)
    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": reasoning,
        "raw_output": raw_output,
        "key_factors": key_factors,
        "model_version": str(payload.get("model_version") or payload.get("model_source") or "Trading-R1/Qwen3.5-2B"),
    }
