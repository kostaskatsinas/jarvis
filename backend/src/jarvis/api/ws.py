import uuid

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from jarvis.core import runner
from jarvis.core.security import ACCESS, InvalidToken, decode_token
from jarvis.db.models import Run, RunEvent
from jarvis.db.session import get_sessionmaker

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(websocket: WebSocket, run_id: uuid.UUID) -> None:
    """Replay persisted events, then stream live ones until the run finishes.

    Auth: browsers can't set headers on WebSocket, so the access token rides
    a query parameter — short-lived, and Caddy/uvicorn access logs are our
    own. Subscribing before the replay means an event can arrive twice at
    the boundary; clients dedupe trivially and never miss one.
    """
    try:
        decode_token(websocket.query_params.get("token", ""), ACCESS)
    except InvalidToken:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = runner.subscribe(run_id)
    try:
        async with get_sessionmaker()() as session:
            run = await session.get(Run, run_id)
            if run is None:
                await websocket.send_json({"type": "error", "payload": {"error": "run not found"}})
                return
            events = (
                await session.execute(
                    select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id)
                )
            ).scalars()
            for event in events:
                await websocket.send_json({"type": event.type, "payload": event.payload})
            finished = run.status != "running"
        if finished:
            await websocket.send_json(
                {"type": runner.RUN_FINISHED, "payload": {"status": run.status}}
            )
            return
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] == runner.RUN_FINISHED:
                return
    finally:
        runner.unsubscribe(run_id, queue)
        await websocket.close()
