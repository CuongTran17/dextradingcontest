from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.admin import _require_admin, get_certificate_export_service
from src.main import app
from src.services.certificate_export import CertificateExportValidationError


class FakeCertificateExportService:
    def __init__(self):
        self.export_called_with = None
        self.authorize_called_with = None

    def export_batch(self, contest_slug, top_n=10, exported_by=None):
        self.export_called_with = (contest_slug, top_n, exported_by)
        return {
            "batch_id": "91",
            "contest_id": contest_slug,
            "top_n": top_n,
            "snapshot_hash": "a" * 64,
            "merkle_root": "b" * 64,
            "claims": [],
        }

    def authorize_batch(self, contest_slug, batch_id, admin_wallet, tx_signature):
        self.authorize_called_with = (
            contest_slug,
            batch_id,
            admin_wallet,
            tx_signature,
        )
        if admin_wallet != "AdminWallet111111111111111111111111111111111":
            raise CertificateExportValidationError(
                "Only the contest on-chain admin wallet can authorize this batch"
            )
        return {
            "batch_id": str(batch_id),
            "contest_id": contest_slug,
            "status": "authorized",
            "authorized_by_wallet": admin_wallet,
            "authorize_tx_signature": tx_signature,
        }


def test_admin_certificate_export_route_calls_service_with_top_n():
    service = FakeCertificateExportService()
    app.dependency_overrides[_require_admin] = lambda: SimpleNamespace(id=9, role="admin")
    app.dependency_overrides[get_certificate_export_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/crypto/contests/summer-cup/certificates/export",
            json={"top_n": 5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["batch_id"] == "91"
    assert response.json()["top_n"] == 5
    assert response.json()["merkle_root"] == "b" * 64
    assert service.export_called_with == ("summer-cup", 5, 9)


def test_admin_certificate_batch_authorize_confirm_rejects_wrong_wallet():
    service = FakeCertificateExportService()
    app.dependency_overrides[_require_admin] = lambda: SimpleNamespace(id=9, role="admin")
    app.dependency_overrides[get_certificate_export_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/crypto/contests/summer-cup/certificates/batches/91/authorize/confirm",
            json={
                "admin_wallet": "WrongWallet111111111111111111111111111111111",
                "authorize_tx_signature": "s" * 64,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert service.authorize_called_with == (
        "summer-cup",
        91,
        "WrongWallet111111111111111111111111111111111",
        "s" * 64,
    )


def test_admin_certificate_batch_authorize_confirm_accepts_admin_wallet():
    service = FakeCertificateExportService()
    app.dependency_overrides[_require_admin] = lambda: SimpleNamespace(id=9, role="admin")
    app.dependency_overrides[get_certificate_export_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/crypto/contests/summer-cup/certificates/batches/91/authorize/confirm",
            json={
                "admin_wallet": "AdminWallet111111111111111111111111111111111",
                "authorize_tx_signature": "s" * 64,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "authorized"
    assert response.json()["authorized_by_wallet"] == (
        "AdminWallet111111111111111111111111111111111"
    )
