from __future__ import annotations

from typing import Any

import httpx


class PinataClientError(ValueError):
    pass


class HttpxPinataTransport:
    def post(self, url: str, **kwargs) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            response = client.post(url, **kwargs)
            response.raise_for_status()
            return response.json()


class PinataClient:
    base_url = "https://api.pinata.cloud"

    def __init__(self, jwt: str, http_client=None, gateway_url: str | None = None):
        if not jwt:
            raise PinataClientError("Pinata JWT is required")
        self.jwt = jwt
        self.http_client = http_client or HttpxPinataTransport()
        self.gateway_url = gateway_url.rstrip("/") if gateway_url else None

    def upload_bytes(self, filename: str, content: bytes, content_type: str) -> str:
        response = self.http_client.post(
            f"{self.base_url}/pinning/pinFileToIPFS",
            headers=self._headers(),
            files={
                "file": (filename, content, content_type),
            },
        )
        return self._asset_uri(response)

    def upload_json(self, filename: str, payload: dict) -> str:
        response = self.http_client.post(
            f"{self.base_url}/pinning/pinJSONToIPFS",
            headers=self._headers(),
            json={
                "pinataMetadata": {"name": filename},
                "pinataContent": payload,
            },
        )
        return self._asset_uri(response)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jwt}"}

    def _asset_uri(self, response: dict[str, Any]) -> str:
        ipfs_hash = response.get("IpfsHash")
        if not ipfs_hash:
            raise PinataClientError("Pinata response did not include IpfsHash")
        if self.gateway_url:
            return f"{self.gateway_url}/{ipfs_hash}"
        return f"ipfs://{ipfs_hash}"
