"""
tests/test_frontend.py
======================
Module 6: Frontend & Deployment Test Suite.

Covers:
- Root web page serving (GET /)
- Static assets serving (/static/style.css, /static/app.js, /static/favicon.svg)
- API Content Negotiation on root route
- Health probe endpoint (GET /health)
- API Discovery endpoint (GET /api)
- Runner prerequisite verification
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from run import check_prerequisites


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


class TestFrontendEndpoints:
    def test_root_serves_html_web_app(self, client):
        """Visiting / without JSON accept header should return the HTML UI."""
        resp = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "TruthLens AI" in resp.text
        assert "nav-tabs" in resp.text
        assert "form-detect" in resp.text

    def test_root_content_negotiation_json(self, client):
        """Requesting / with Accept: application/json should return API welcome info."""
        resp = client.get("/", headers={"Accept": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "docs_url" in data
        assert data["docs_url"] == "/docs"

    def test_api_discovery_endpoint(self, client):
        """GET /api returns API documentation and endpoint pointers."""
        resp = client.get("/api")
        assert resp.status_code == 200
        data = resp.json()
        assert data["docs_url"] == "/docs"
        assert "/auth" in data["auth_endpoints"]

    def test_health_check_endpoint(self, client):
        """GET /health returns healthy status and lists all 6 modules."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "TruthLens AI" in data["service"]
        assert len(data["modules"]) == 6
        assert any("Frontend" in m for m in data["modules"])


class TestStaticAssets:
    def test_static_style_css(self, client):
        """GET /static/style.css returns stylesheet."""
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")
        assert "--primary" in resp.text

    def test_static_app_js(self, client):
        """GET /static/app.js returns application JavaScript."""
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers.get("content-type", "")
        assert "TruthLens AI" in resp.text
        assert "apiRequest" in resp.text

    def test_static_favicon_svg(self, client):
        """GET /static/favicon.svg returns SVG icon."""
        resp = client.get("/static/favicon.svg")
        assert resp.status_code == 200
        assert "image/svg+xml" in resp.headers.get("content-type", "")
        assert "<svg" in resp.text


class TestDeploymentPrerequisites:
    def test_check_prerequisites_runs(self, capsys):
        """System launcher prerequisite check executes without error."""
        check_prerequisites()
        captured = capsys.readouterr()
        assert "TRUTHLENS AI" in captured.out
        assert "SQLite Tables: OK" in captured.out
