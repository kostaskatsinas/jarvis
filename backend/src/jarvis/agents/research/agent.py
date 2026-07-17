from jarvis.agents.research.prompts import JOB_SCAN_PROMPT, SYSTEM_PROMPT
from jarvis.core.agent import (
    AgentManifest,
    BaseAgent,
    Schedule,
    expose_agent_as_tool,
    register_agent,
)

research_agent = register_agent(
    BaseAgent(
        AgentManifest(
            name="research",
            description="Web research, summarization, and job-search workflows",
            system_prompt=SYSTEM_PROMPT,
            model_alias="smart",
            tool_scopes=("web", "memory"),
            schedules=(Schedule(cron="0 8 * * *", prompt=JOB_SCAN_PROMPT),),
            max_iterations=12,
        )
    )
)

# Other agents (scope "delegation") can hand research questions off as
# ask_research(request); each delegation is its own tracked run.
expose_agent_as_tool("research", scopes=("delegation",))
