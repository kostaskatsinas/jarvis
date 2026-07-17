"""Cron triggers for agents, framework-level.

Agents declare schedules in their manifest; at startup every declared
schedule is (re)registered with APScheduler. Manifests are the source of
truth, so the in-memory jobstore is correct here — jobs are idempotently
rebuilt on every boot and there is no persisted jobstore to drift.
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jarvis.config import get_settings
from jarvis.core import runner
from jarvis.core.agent import list_agents

log = structlog.get_logger()


async def _fire(agent_name: str, prompt: str) -> None:
    await runner.start_run(agent_name, prompt, trigger="schedule")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=get_settings().timezone)
    for agent in list_agents():
        for i, schedule in enumerate(agent.manifest.schedules):
            scheduler.add_job(
                _fire,
                CronTrigger.from_crontab(schedule.cron, timezone=get_settings().timezone),
                args=[agent.manifest.name, schedule.prompt],
                id=f"{agent.manifest.name}:{i}",
                replace_existing=True,
            )
            log.info("schedule_registered", agent=agent.manifest.name, cron=schedule.cron)
    scheduler.start()
    return scheduler
