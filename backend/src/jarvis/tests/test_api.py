from fastapi.testclient import TestClient

import jarvis.tests.test_agent_run  # noqa: F401  (registers test-agent)
from jarvis.main import app
from jarvis.tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_health_and_agent_listing():
    # TestClient runs the lifespan: tool/agent loading, checkpointer, scheduler.
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        token = client.post(
            "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        agents = client.get("/api/agents", headers=headers).json()
        names = {a["name"] for a in agents}
        assert "test-agent" in names  # registered by the framework test module

        assert client.get("/api/runs", headers=headers).status_code == 200
        assert (
            client.post(
                "/api/agents/nope/runs", json={"message": "hi"}, headers=headers
            ).status_code
            == 404
        )
