from jarvis.agents.dev.prompts import SYSTEM_PROMPT
from jarvis.core.agent import AgentManifest, BaseAgent, register_agent

dev_agent = register_agent(
    BaseAgent(
        AgentManifest(
            name="dev",
            description="Repo-aware coding assistant: explore, generate, review",
            system_prompt=SYSTEM_PROMPT,
            model_alias="smart",
            tool_scopes=("dev", "memory", "delegation"),
            max_iterations=20,
        )
    )
)
