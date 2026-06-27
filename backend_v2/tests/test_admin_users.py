from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import router


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_admin_router_exposes_users_and_crypto_contests_only():
    client = make_client()
    paths = set(client.app.openapi()["paths"])

    assert "/api/admin/users" in paths
    assert "/api/admin/users/{user_id}/role" in paths
    assert "/api/admin/users/{user_id}/lock" in paths
    assert "/api/admin/users/{user_id}/unlock" in paths
    assert "/api/admin/crypto/contests" in paths
    assert "/api/admin/crypto/contests/{contest_id}" in paths
    assert "/api/admin/crypto/contests/{contest_id}/status" in paths
    assert not any("/promotions" in path for path in paths)
    assert not any("/flash-sales" in path for path in paths)
    assert not any("/sales-stats" in path for path in paths)
    assert not any("/user-portfolios" in path for path in paths)
