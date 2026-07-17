from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jarvis.core import runner
from jarvis.core.agent import list_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


class StartRunRequest(BaseModel):
    message: str
    trigger: str = "chat"


@router.get("")
async def get_agents() -> list[dict]:
    return [
        {
            "name": a.manifest.name,
            "description": a.manifest.description,
            "model_alias": a.manifest.model_alias,
            "tools": [t.name for t in a.tools()],
            "schedules": [{"cron": s.cron, "prompt": s.prompt} for s in a.manifest.schedules],
        }
        for a in list_agents()
    ]


@router.post("/{name}/runs", status_code=202)
async def start_run(name: str, body: StartRunRequest) -> dict:
    try:
        run_id = await runner.start_run(name, body.message, trigger=body.trigger)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown agent: {name}")
    return {"run_id": str(run_id)}
