from fastapi.testclient import TestClient

import jarvis.tests.test_agent_run  # noqa: F401  (registers test-agent)
from jarvis.main import app


def test_health_and_agent_listing():
    # TestClient runs the lifespan: tool/agent loading, checkpointer, scheduler.
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        agents = client.get("/api/agents").json()
        names = {a["name"] for a in agents}
        assert "test-agent" in names  # registered by the framework test module

        assert client.get("/api/runs").status_code == 200
        assert (
            client.post("/api/agents/nope/runs", json={"message": "hi"}).status_code == 404
        )
