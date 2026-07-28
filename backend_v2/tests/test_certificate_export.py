import json
import hashlib
from decimal import Decimal
from types import SimpleNamespace

from src.database.crypto_models import CryptoCertificateClaim
from src.database.user_models import User  # noqa: F401
from src.services.certificate_export import (
    CertificateExportService,
    certificate_leaf,
    merkle_proof,
    merkle_root,
)


class FakePinataClient:
    def __init__(self):
        self.uploaded_json = []

    def upload_bytes(self, filename, content, content_type):
        assert filename.endswith(".png")
        assert content == b"certificate-png"
        assert content_type == "image/png"
        return f"ipfs://image-{filename}"

    def upload_json(self, filename, payload):
        self.uploaded_json.append(payload)
        assert filename.endswith(".json")
        assert payload["image"].startswith("ipfs://image-")
        return f"ipfs://metadata-{filename}"


class FakeRenderer:
    def __init__(self):
        self.payloads = []

    def render_png(self, payload):
        self.payloads.append(payload)
        return b"certificate-png"


class FakeRepo:
    def __init__(self):
        snapshot = {
            "contest": {
                "id": "summer-cup",
                "title": "Summer Cup",
                "quote_asset": "USDT_TEST",
            },
            "settled_at": "2026-07-28T12:00:00+00:00",
            "rows": [
                {
                    "rank": rank,
                    "participant_id": rank,
                    "user": f"Trader {rank}",
                    "final_equity": 10000 + rank,
                    "final_roi": rank / 10,
                }
                for rank in range(1, 12)
            ],
        }
        self.settlement = SimpleNamespace(
            contest_id=77,
            snapshot_hash="a" * 64,
            snapshot_json=json.dumps(snapshot),
        )
        self.participants = [
            SimpleNamespace(
                id=rank,
                wallet_address=f"So{rank:062d}",
                final_rank=rank,
                final_equity=Decimal(str(10000 + rank)),
                final_roi=Decimal(str(rank / 10)),
            )
            for rank in range(1, 12)
        ]
        self.claims = []
        self.committed = False

    def get_latest_settlement(self, contest_slug):
        assert contest_slug == "summer-cup"
        return self.settlement

    def list_contest_participants(self, contest_slug):
        assert contest_slug == "summer-cup"
        return self.participants

    def add_certificate_claim(self, claim):
        self.claims.append(claim)
        return claim

    def commit(self):
        self.committed = True


def test_merkle_helpers_are_deterministic_and_return_hex_proofs():
    leaves = [
        certificate_leaf("summer-cup", "wallet-a", 1, "ipfs://a", "abc"),
        certificate_leaf("summer-cup", "wallet-b", 2, "ipfs://b", "abc"),
        certificate_leaf("summer-cup", "wallet-c", 3, "ipfs://c", "abc"),
    ]

    assert merkle_root(leaves) == merkle_root(list(leaves))
    assert merkle_root(leaves).hex()
    proof = merkle_proof(leaves, 0)
    assert all(len(item) == 64 for item in proof)
    cursor = leaves[0]
    for sibling in proof:
        first, second = sorted((cursor, bytes.fromhex(sibling)))
        cursor = hashlib.sha256(first + second).digest()
    assert cursor == merkle_root(leaves)


def test_certificate_export_creates_top10_payload_with_metadata_uri():
    repo = FakeRepo()
    pinata = FakePinataClient()
    renderer = FakeRenderer()
    service = CertificateExportService(repo, pinata_client=pinata, renderer=renderer)

    result = service.export_top10("summer-cup", exported_by=9)

    assert len(result["claims"]) == 10
    assert result["claims"][0]["rank"] == 1
    assert renderer.payloads[0]["contest_title"] == "Summer Cup"
    assert renderer.payloads[0]["rank"] == 1
    assert renderer.payloads[0]["snapshot_hash"] == "a" * 64
    assert result["claims"][0]["metadata_uri"].startswith("ipfs://metadata-")
    assert result["claims"][0]["proof"]
    assert result["merkle_root"]
    assert len(repo.claims) == 10
    assert isinstance(repo.claims[0], CryptoCertificateClaim)
    assert repo.claims[0].certificate_metadata_uri.startswith("ipfs://metadata-")
    assert json.loads(repo.claims[0].merkle_proof_json) == result["claims"][0]["proof"]
    assert repo.committed is True
