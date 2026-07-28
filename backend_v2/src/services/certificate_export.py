from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.database.crypto_models import CryptoCertificateClaim


class CertificateExportError(ValueError):
    pass


class CertificateExportNotFoundError(CertificateExportError):
    pass


def certificate_leaf(
    contest_id: str,
    wallet: str,
    rank: int,
    metadata_uri: str,
    snapshot_hash: str,
) -> bytes:
    payload = json.dumps(
        {
            "contest_id": contest_id,
            "wallet": wallet,
            "rank": rank,
            "metadata_uri": metadata_uri,
            "snapshot_hash": snapshot_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).digest()


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return b"\x00" * 32
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            _hash_pair(level[index], level[index + 1])
            for index in range(0, len(level), 2)
        ]
    return level[0]


def merkle_proof(leaves: list[bytes], index: int) -> list[str]:
    if index < 0 or index >= len(leaves):
        raise IndexError("Merkle proof index out of range")
    proof = []
    cursor = index
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = cursor + 1 if cursor % 2 == 0 else cursor - 1
        proof.append(level[sibling].hex())
        cursor //= 2
        level = [
            _hash_pair(level[item], level[item + 1])
            for item in range(0, len(level), 2)
        ]
    return proof


def _hash_pair(left: bytes, right: bytes) -> bytes:
    first, second = sorted((left, right))
    return hashlib.sha256(first + second).digest()


class CertificateExportService:
    def __init__(self, repo, pinata_client, renderer):
        self.repo = repo
        self.pinata_client = pinata_client
        self.renderer = renderer

    def export_top10(
        self,
        contest_slug: str,
        exported_by: int | None = None,
    ) -> dict[str, Any]:
        del exported_by
        settlement = self.repo.get_latest_settlement(contest_slug)
        if settlement is None:
            raise CertificateExportNotFoundError("Contest settlement not found")

        snapshot = json.loads(settlement.snapshot_json)
        participants = {
            participant.id: participant
            for participant in self.repo.list_contest_participants(contest_slug)
            if getattr(participant, "wallet_address", None)
        }
        rows = sorted(snapshot.get("rows", []), key=lambda row: row["rank"])
        prepared = []
        for row in rows:
            if len(prepared) >= 10:
                break
            participant = participants.get(row["participant_id"])
            if participant is None:
                continue
            prepared.append((row, participant))

        claim_payloads = []
        leaves = []
        for row, participant in prepared:
            image_uri = self._render_and_upload_image(snapshot, row, participant)
            metadata = self._metadata(snapshot, row, participant, image_uri)
            metadata_uri = self.pinata_client.upload_json(
                f"{contest_slug}-rank-{row['rank']}.json",
                metadata,
            )
            leaf = certificate_leaf(
                contest_slug,
                participant.wallet_address,
                row["rank"],
                metadata_uri,
                settlement.snapshot_hash,
            )
            leaves.append(leaf)
            claim_payloads.append(
                {
                    "row": row,
                    "participant": participant,
                    "image_uri": image_uri,
                    "metadata_uri": metadata_uri,
                    "leaf": leaf,
                }
            )

        root = merkle_root(leaves)
        response_claims = []
        for index, item in enumerate(claim_payloads):
            row = item["row"]
            participant = item["participant"]
            proof = merkle_proof(leaves, index)
            claim = CryptoCertificateClaim(
                contest_id=settlement.contest_id,
                participant_id=participant.id,
                wallet_address=participant.wallet_address,
                rank=row["rank"],
                recipient_name=row["user"],
                final_equity=Decimal(str(row["final_equity"])),
                roi=Decimal(str(row["final_roi"])),
                snapshot_hash=settlement.snapshot_hash,
                certificate_image_uri=item["image_uri"],
                certificate_metadata_uri=item["metadata_uri"],
                merkle_leaf=item["leaf"].hex(),
                merkle_proof_json=json.dumps(proof),
                created_at=datetime.now(timezone.utc),
            )
            self.repo.add_certificate_claim(claim)
            response_claims.append(
                {
                    "participant_id": participant.id,
                    "wallet_address": participant.wallet_address,
                    "rank": row["rank"],
                    "recipient_name": row["user"],
                    "image_uri": item["image_uri"],
                    "metadata_uri": item["metadata_uri"],
                    "merkle_leaf": item["leaf"].hex(),
                    "proof": proof,
                }
            )

        self.repo.commit()
        return {
            "contest_id": contest_slug,
            "snapshot_hash": settlement.snapshot_hash,
            "merkle_root": root.hex(),
            "claims": response_claims,
        }

    def _render_and_upload_image(self, snapshot, row, participant) -> str:
        payload = {
            "contest_title": snapshot["contest"]["title"],
            "rank": row["rank"],
            "recipient_name": row["user"],
            "wallet_address": participant.wallet_address,
            "final_equity": f"{row['final_equity']} {snapshot['contest']['quote_asset']}",
            "roi": f"{row['final_roi']}%",
            "settlement_date": snapshot.get("settled_at", "")[:10],
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }
        content = self.renderer.render_png(payload)
        return self.pinata_client.upload_bytes(
            f"{snapshot['contest']['id']}-rank-{row['rank']}.png",
            content,
            "image/png",
        )

    def _metadata(self, snapshot, row, participant, image_uri: str) -> dict[str, Any]:
        contest_title = snapshot["contest"]["title"]
        return {
            "name": f"{contest_title} - Top {row['rank']} Certificate",
            "symbol": "CDTC",
            "description": (
                f"Certificate awarded for ranking Top {row['rank']} in {contest_title}."
            ),
            "image": image_uri,
            "attributes": [
                {"trait_type": "Contest", "value": contest_title},
                {"trait_type": "Rank", "value": f"Top {row['rank']}"},
                {"trait_type": "Recipient", "value": row["user"]},
                {
                    "trait_type": "Final Equity",
                    "value": f"{row['final_equity']} {snapshot['contest']['quote_asset']}",
                },
                {"trait_type": "ROI", "value": f"{row['final_roi']}%"},
                {"trait_type": "Wallet", "value": participant.wallet_address},
            ],
        }
