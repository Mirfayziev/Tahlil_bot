"""Health check va Prometheus metrikalari testlari (TZ v2, bo'lim 3: DevOps)."""


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_metrics_endpoint_returns_prometheus_format(client):
    client.get("/healthz")  # kamida bitta so'rov hosil qilamiz
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"http_requests_total" in resp.data or b"python_gc_objects" in resp.data


def test_api_v1_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
