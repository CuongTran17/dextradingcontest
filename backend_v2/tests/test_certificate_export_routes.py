from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.admin import get_certificate_export_service
from src.api.auth import require_auth
from src.main import app


class FakeCertificateExportService:
    def __init__(self):
        self.called_with = None

    def export_top10(self, contest_slug, exported_by=None):
        self.called_with = (contest_slug, exported_by)
        return {
            "contest_id": contest_slug,
            "snapshot_hash": "a" * 64,
            "merkle_root": "b" * 64,
            "claims": [],
        }


def test_admin_certificate_export_route_calls_service():
    service = FakeCertificateExportService()
    app.dependency_overrides[require_auth] = lambda: SimpleNamespace(id=9, role="admin")
    app.dependency_overrides[get_certificate_export_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/crypto/contests/summer-cup/certificates/export"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["merkle_root"] == "b" * 64
    assert service.called_with == ("summer-cup", 9)
