def test_health_check(client):
    """Test health endpoint returns 200 and healthy database connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["service"] == "INDUSAI-X Backend"


def test_system_metrics(client):
    """Test authentic system metrics endpoint returns valid host metrics."""
    response = client.get("/api/system/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "percent" in data["cpu"]
    assert "ram" in data
    assert "total_gb" in data["ram"]
    assert data["ram"]["total_gb"] > 0
    assert "percent" in data["ram"]
    assert "disk" in data
    assert "gpu" in data
    assert data["source"] == "psutil_authentic"

