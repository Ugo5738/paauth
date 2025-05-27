import pytest
from fastapi.testclient import TestClient

from auth_service.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"message": "OK"}


def test_health_method_not_allowed():
    response = client.post("/health")
    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
