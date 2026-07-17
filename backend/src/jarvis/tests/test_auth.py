from fastapi.testclient import TestClient

from jarvis.main import app
from jarvis.tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def _login(client: TestClient, password: str = ADMIN_PASSWORD):
    return client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": password})


def test_login_and_protected_routes():
    with TestClient(app) as client:
        # No token -> everything but health is closed.
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/agents").status_code == 401
        assert client.get("/api/runs").status_code == 401

        assert _login(client, password="wrong").status_code == 401

        response = _login(client)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/agents", headers=headers).status_code == 200
        assert client.get("/api/auth/me", headers=headers).json() == {"email": ADMIN_EMAIL}

        assert client.get("/api/agents", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_refresh_cookie_flow():
    with TestClient(app) as client:
        _login(client)
        assert "jarvis_refresh" in client.cookies

        response = client.post("/api/auth/refresh")
        assert response.status_code == 200
        assert "access_token" in response.json()

        client.post("/api/auth/logout")
        client.cookies.clear()
        assert client.post("/api/auth/refresh").status_code == 401


def test_login_rate_limited():
    with TestClient(app) as client:
        for _ in range(5):
            assert _login(client, password="wrong").status_code == 401
        assert _login(client).status_code == 429  # even the right password now waits


def test_websocket_requires_token():
    with TestClient(app) as client:
        token = _login(client).json()["access_token"]
        run_id = "00000000-0000-0000-0000-000000000000"

        try:
            with client.websocket_connect(f"/ws/runs/{run_id}?token=bad") as ws:
                assert ws.receive()["type"] == "websocket.close"
        except Exception:
            pass  # some client versions raise on server-side close instead

        with client.websocket_connect(f"/ws/runs/{run_id}?token={token}") as ws:
            message = ws.receive_json()
            assert message == {"type": "error", "payload": {"error": "run not found"}}
