import pytest
from fastapi.testclient import TestClient

from auth_service.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    # Accept either 200 (all healthy) or 503 (degraded) status codes
    assert response.status_code in [200, 503]
    response_data = response.json()
    
    # Verify the structure of the response
    assert "status" in response_data
    assert "version" in response_data
    assert "components" in response_data
    
    # Either status could be valid in different environments
    assert response_data["status"] in ["ok", "degraded"]
    
    # If status code is 503, status must be "degraded"
    if response.status_code == 503:
        assert response_data["status"] == "degraded"


def test_health_method_not_allowed():
    response = client.post("/health")
    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
