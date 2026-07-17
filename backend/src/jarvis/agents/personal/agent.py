from jarvis.agents.personal.prompts import SYSTEM_PROMPT, TRIAGE_PROMPT
from jarvis.core.agent import AgentManifest, BaseAgent, Schedule, register_agent

personal_agent = register_agent(
    BaseAgent(
        AgentManifest(
            name="personal",
            description="Email triage/drafting and file organization",
            system_prompt=SYSTEM_PROMPT,
            model_alias="smart",
            tool_scopes=("gmail", "files", "memory"),
            schedules=(Schedule(cron="30 7 * * *", prompt=TRIAGE_PROMPT),),
            max_iterations=16,
        )
    )
)
