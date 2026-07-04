"""Smoke test for Task 0.1's exit gate: the FastAPI app boots and /health
responds. Deeper contract tests land in Tier 3 (3A) once real routes exist.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_v1_prefix() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
