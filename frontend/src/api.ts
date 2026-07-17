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

// Access token lives in memory only; the refresh token is an httponly
// cookie, so a page reload silently re-authenticates via /api/auth/refresh.
let accessToken: string | null = null;

export function getToken(): string | null {
  return accessToken;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function authed(input: string, init: RequestInit = {}): Promise<Response> {
  const withAuth = (): RequestInit => ({
    ...init,
    headers: { ...(init.headers ?? {}), Authorization: `Bearer ${accessToken}` },
  });
  let response = await fetch(input, withAuth());
  if (response.status === 401 && (await tryRefresh())) {
    response = await fetch(input, withAuth());
  }
  return response;
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const detail = await response.json().then((d) => d.detail).catch(() => response.statusText);
    throw new Error(detail);
  }
  accessToken = (await response.json()).access_token;
}

export async function tryRefresh(): Promise<boolean> {
  const response = await fetch("/api/auth/refresh", { method: "POST" });
  if (!response.ok) return false;
  accessToken = (await response.json()).access_token;
  return true;
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
  accessToken = null;
}

export const api = {
  agents: () => authed("/api/agents").then((r) => json<AgentInfo[]>(r)),
  runs: (agent?: string) =>
    authed(`/api/runs${agent ? `?agent=${encodeURIComponent(agent)}` : ""}`).then((r) =>
      json<RunSummary[]>(r),
    ),
  run: (id: string) =>
    authed(`/api/runs/${id}`).then((r) => json<RunSummary & { events: RunEvent[] }>(r)),
  startRun: (agent: string, message: string) =>
    authed(`/api/agents/${encodeURIComponent(agent)}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, trigger: "chat" }),
    }).then((r) => json<{ run_id: string }>(r)),
};

export function runSocket(runId: string): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(
    `${proto}://${window.location.host}/ws/runs/${runId}?token=${accessToken ?? ""}`,
  );
}
