export interface AgentInfo {
  name: string;
  description: string;
  model_alias: string;
  tools: string[];
  schedules: { cron: string; prompt: string }[];
}

export interface RunSummary {
  id: string;
  agent_name: string;
  trigger: string;
  status: string;
  input_text: string;
  output_text: string | null;
  error: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  finished_at: string | null;
}

export interface RunEvent {
  type: string;
  payload: { messages?: Message[]; status?: string; error?: string };
}

export interface Message {
  role: string;
  content?: string;
  name?: string;
  tool_calls?: { function: { name: string; arguments: string } }[];
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export const api = {
  agents: () => fetch("/api/agents").then((r) => json<AgentInfo[]>(r)),
  runs: (agent?: string) =>
    fetch(`/api/runs${agent ? `?agent=${encodeURIComponent(agent)}` : ""}`).then((r) =>
      json<RunSummary[]>(r),
    ),
  run: (id: string) => fetch(`/api/runs/${id}`).then((r) => json<RunSummary & { events: RunEvent[] }>(r)),
  startRun: (agent: string, message: string) =>
    fetch(`/api/agents/${encodeURIComponent(agent)}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, trigger: "chat" }),
    }).then((r) => json<{ run_id: string }>(r)),
};

export function runSocket(runId: string): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${window.location.host}/ws/runs/${runId}`);
}
