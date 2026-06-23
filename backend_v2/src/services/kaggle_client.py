from __future__ import annotations

from typing import Any

import httpx


class KaggleClient:
    def __init__(self, base_url: str, http_client: Any | None = None, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds

    async def analyze(self, prompt: str) -> dict[str, Any]:
        if not self.base_url:
            raise ValueError("KAGGLE_API_URL not configured")
        url = f"{self.base_url}/api/analyze"
        headers = {"Content-Type": "application/json"}
        if self.http_client is not None:
            response = await self.http_client.post(url, json={"prompt": prompt}, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json={"prompt": prompt}, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Kaggle API error {response.status_code}: {response.text}")
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw_output": str(payload)}
