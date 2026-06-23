from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

try:
    from src.database.market_duckdb import market_repo
    from src.services.ai_context import build_analysis_context, build_prompt
    from src.services.ai_response import normalize_kaggle_response
    from src.services.kaggle_client import KaggleClient
    from src.settings import get_settings
except ModuleNotFoundError:
    from backend_v2.src.database.market_duckdb import market_repo
    from backend_v2.src.services.ai_context import build_analysis_context, build_prompt
    from backend_v2.src.services.ai_response import normalize_kaggle_response
    from backend_v2.src.services.kaggle_client import KaggleClient
    from backend_v2.src.settings import get_settings


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AIAnalysisService:
    def __init__(self, repo: Any = market_repo, kaggle_client: Any | None = None, prompt_version: str = "vn30-v1"):
        settings = get_settings()
        self.repo = repo
        self.kaggle_client = kaggle_client or KaggleClient(settings.kaggle_api_url)
        self.prompt_version = prompt_version

    async def generate(self, symbol: str, horizon_days: int = 5) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        context = await build_analysis_context(normalized_symbol, repo=self.repo)
        prompt = build_prompt(context, prompt_version=self.prompt_version)
        context_hash = _stable_hash(context)
        request_payload = {"prompt": prompt}
        request_hash = _stable_hash(request_payload)
        analysis_date = datetime.now(timezone.utc).date()
        current_price = context.get("close_price")

        analysis_id = self.repo.create_ai_analysis_run(
            symbol=normalized_symbol,
            analysis_date=analysis_date,
            horizon_days=horizon_days,
            model_version="Trading-R1/Qwen3.5-2B",
            prompt_version=self.prompt_version,
            context_hash=context_hash,
            request_hash=request_hash,
            market_feature_run_id=context.get("market_feature_run_id"),
            current_price=float(current_price) if current_price is not None else None,
            status="running",
        )

        try:
            kaggle_response = await self.kaggle_client.analyze(prompt)
            normalized = normalize_kaggle_response(kaggle_response)
            response_hash = _stable_hash(kaggle_response)
            self.repo.save_ai_analysis_payload(
                analysis_id=analysis_id,
                request_context=context,
                prompt_text=prompt,
                kaggle_response=kaggle_response,
                raw_output=normalized["raw_output"],
                normalized_output=normalized,
            )
            self.repo.complete_ai_analysis_run(
                analysis_id=analysis_id,
                status="success",
                decision=normalized["decision"],
                confidence=normalized["confidence"],
                reasoning=normalized["reasoning"],
                key_factors=normalized["key_factors"],
                response_hash=response_hash,
            )
            return {
                "status": "ok",
                "analysis_id": analysis_id,
                "symbol": normalized_symbol,
                "decision": normalized["decision"],
                "confidence": normalized["confidence"],
                "reasoning": normalized["reasoning"],
                "raw_output": normalized["raw_output"],
                "key_factors": normalized["key_factors"],
                "model_version": normalized["model_version"],
                "prompt_version": self.prompt_version,
                "context_hash": context_hash,
                "request_hash": request_hash,
                "response_hash": response_hash,
                "analysis": {
                    "data_source": "duckdb-market-features + mysql-reference-cache + Kaggle Trading-R1",
                    "market_feature_run_id": context.get("market_feature_run_id"),
                    "data_date": context.get("data_date"),
                },
            }
        except Exception as exc:
            self.repo.complete_ai_analysis_run(
                analysis_id=analysis_id,
                status="failed",
                error_message=str(exc),
            )
            raise
