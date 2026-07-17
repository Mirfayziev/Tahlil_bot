"""Hisobotlar (Excel/PDF eksport) smoke-testlari."""
from tests.conftest import login


def test_reports_page_requires_login(client):
    resp = client.get("/reports/", follow_redirects=True)
    assert b"Kirish" in resp.data or "tizimga kiring".encode() in resp.data


def test_export_excel(client, super_admin, service_request):
    login(client, "test_admin", "AdminPass123")
    resp = client.get("/reports/export/excel")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.data) > 0


def test_export_pdf(client, super_admin, service_request):
    login(client, "test_admin", "AdminPass123")
    resp = client.get("/reports/export/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:4] == b"%PDF"
