import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from jarvis.api.auth import require_user
from jarvis.db.models import Run, RunEvent
from jarvis.db.session import get_sessionmaker

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(require_user)])


def _run_dict(run: Run) -> dict:
    return {
        "id": str(run.id),
        "agent_name": run.agent_name,
        "trigger": run.trigger,
        "status": run.status,
        "input_text": run.input_text,
        "output_text": run.output_text,
        "error": run.error,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.get("")
async def list_runs(agent: str | None = None, limit: int = 50) -> list[dict]:
    stmt = select(Run).order_by(Run.created_at.desc()).limit(min(limit, 200))
    if agent:
        stmt = stmt.where(Run.agent_name == agent)
    async with get_sessionmaker()() as session:
        return [_run_dict(r) for r in (await session.execute(stmt)).scalars()]


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID) -> dict:
    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        events = (
            await session.execute(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id)
            )
        ).scalars()
        out = _run_dict(run)
        out["events"] = [
            {"id": e.id, "type": e.type, "payload": e.payload, "created_at": e.created_at.isoformat()}
            for e in events
        ]
        return out
