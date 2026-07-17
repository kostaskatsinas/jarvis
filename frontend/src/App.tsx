import { useCallback, useEffect, useRef, useState } from "react";
import { api, runSocket, AgentInfo, Message, RunEvent, RunSummary } from "./api";

interface ChatItem {
  kind: "user" | "assistant" | "tool" | "status";
  text: string;
  detail?: string;
}

function messageToItems(msg: Message): ChatItem[] {
  const items: ChatItem[] = [];
  for (const call of msg.tool_calls ?? []) {
    items.push({ kind: "tool", text: `→ ${call.function.name}`, detail: call.function.arguments });
  }
  if (msg.role === "assistant" && msg.content) items.push({ kind: "assistant", text: msg.content });
  if (msg.role === "tool") items.push({ kind: "tool", text: `← ${msg.name}`, detail: msg.content });
  return items;
}

export default function App() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [chat, setChat] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const agent = agents.find((a) => a.name === selected);

  const refreshRuns = useCallback((name: string | null) => {
    api.runs(name ?? undefined).then(setRuns).catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    api.agents().then((list) => {
      setAgents(list);
      if (list.length > 0) setSelected((s) => s ?? list[0].name);
    });
  }, []);

  useEffect(() => {
    refreshRuns(selected);
  }, [selected, refreshRuns]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  function attachSocket(runId: string) {
    socketRef.current?.close();
    const socket = runSocket(runId);
    socketRef.current = socket;
    socket.onmessage = (raw) => {
      const event: RunEvent = JSON.parse(raw.data);
      if (event.type === "run_finished") {
        setChat((c) => [...c, { kind: "status", text: `run ${event.payload.status}` }]);
        setBusy(false);
        refreshRuns(selected);
        socket.close();
        return;
      }
      if (event.type === "error") {
        setChat((c) => [...c, { kind: "status", text: `error: ${event.payload.error}` }]);
        return;
      }
      const items = (event.payload.messages ?? []).flatMap(messageToItems);
      if (items.length > 0) setChat((c) => [...c, ...items]);
    };
    socket.onerror = () => setBusy(false);
  }

  async function send() {
    if (!selected || !input.trim() || busy) return;
    const message = input.trim();
    setInput("");
    setBusy(true);
    setChat((c) => [...c, { kind: "user", text: message }]);
    try {
      const { run_id } = await api.startRun(selected, message);
      attachSocket(run_id);
    } catch (e) {
      setChat((c) => [...c, { kind: "status", text: `failed to start run: ${e}` }]);
      setBusy(false);
    }
  }

  async function openRun(id: string) {
    const run = await api.run(id);
    const items: ChatItem[] = [{ kind: "user", text: run.input_text }];
    for (const event of run.events) items.push(...(event.payload.messages ?? []).flatMap(messageToItems));
    if (run.error) items.push({ kind: "status", text: `error: ${run.error}` });
    items.push({ kind: "status", text: `run ${run.status}` });
    setChat(items);
  }

  return (
    <div style={styles.layout}>
      <aside style={styles.sidebar}>
        <h1 style={{ fontSize: "1.2rem", margin: "0 0 1rem" }}>Jarvis</h1>
        {agents.map((a) => (
          <button
            key={a.name}
            onClick={() => {
              setSelected(a.name);
              setChat([]);
            }}
            style={{ ...styles.agentBtn, ...(a.name === selected ? styles.agentBtnActive : {}) }}
          >
            <strong>{a.name}</strong>
            <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>{a.description}</span>
          </button>
        ))}
        <h2 style={styles.h2}>Runs</h2>
        <div style={{ overflowY: "auto", flex: 1 }}>
          {runs.map((r) => (
            <button key={r.id} onClick={() => openRun(r.id)} style={styles.runBtn}>
              <span>
                {r.status === "running" ? "⏳" : r.status === "succeeded" ? "✓" : "✗"}{" "}
                {r.trigger} · {new Date(r.created_at).toLocaleString()}
              </span>
              <span style={styles.runInput}>{r.input_text.slice(0, 60)}</span>
            </button>
          ))}
        </div>
      </aside>

      <main style={styles.main}>
        {agent && (
          <div style={styles.agentHeader}>
            <strong>{agent.name}</strong> · model: {agent.model_alias} · tools:{" "}
            {agent.tools.join(", ")}
            {agent.schedules.length > 0 && <> · cron: {agent.schedules.map((s) => s.cron).join("; ")}</>}
          </div>
        )}
        <div style={styles.chat}>
          {chat.map((item, i) => (
            <div key={i} style={{ ...styles.msg, ...styles[item.kind] }}>
              <div style={{ whiteSpace: "pre-wrap" }}>{item.text}</div>
              {item.detail && (
                <details>
                  <summary style={{ cursor: "pointer", fontSize: "0.75rem" }}>detail</summary>
                  <pre style={styles.pre}>{item.detail}</pre>
                </details>
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <div style={styles.inputRow}>
          <textarea
            style={styles.textarea}
            rows={2}
            value={input}
            placeholder={selected ? `Message ${selected}…` : "No agents registered"}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <button style={styles.sendBtn} onClick={send} disabled={busy || !selected}>
            {busy ? "…" : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  layout: { display: "flex", height: "100vh", fontFamily: "system-ui", color: "#1a1a1a" },
  sidebar: {
    width: 280,
    borderRight: "1px solid #ddd",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    background: "#fafafa",
  },
  h2: { fontSize: "0.8rem", textTransform: "uppercase", opacity: 0.6, margin: "1.5rem 0 0.5rem" },
  agentBtn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 2,
    width: "100%",
    textAlign: "left",
    padding: "0.5rem",
    marginBottom: 4,
    border: "1px solid #ddd",
    borderRadius: 6,
    background: "white",
    cursor: "pointer",
  },
  agentBtnActive: { borderColor: "#4a6cf7", background: "#eef1fe" },
  runBtn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    width: "100%",
    textAlign: "left",
    padding: "0.4rem 0.5rem",
    marginBottom: 2,
    border: "none",
    borderRadius: 4,
    background: "transparent",
    cursor: "pointer",
    fontSize: "0.75rem",
  },
  runInput: { opacity: 0.6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" },
  main: { flex: 1, display: "flex", flexDirection: "column" },
  agentHeader: { padding: "0.6rem 1rem", borderBottom: "1px solid #ddd", fontSize: "0.8rem", background: "#fafafa" },
  chat: { flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: 8 },
  msg: { maxWidth: "48rem", padding: "0.5rem 0.8rem", borderRadius: 8, fontSize: "0.9rem" },
  user: { alignSelf: "flex-end", background: "#4a6cf7", color: "white" },
  assistant: { alignSelf: "flex-start", background: "#f0f0f0" },
  tool: { alignSelf: "flex-start", background: "#fff8e6", border: "1px solid #f0e0b0", fontSize: "0.8rem" },
  status: { alignSelf: "center", opacity: 0.6, fontSize: "0.75rem" },
  pre: { fontSize: "0.7rem", whiteSpace: "pre-wrap", wordBreak: "break-all", margin: "0.3rem 0 0" },
  inputRow: { display: "flex", gap: 8, padding: "0.8rem 1rem", borderTop: "1px solid #ddd" },
  textarea: { flex: 1, padding: "0.5rem", borderRadius: 6, border: "1px solid #ccc", fontFamily: "inherit", resize: "none" },
  sendBtn: {
    padding: "0 1.2rem",
    borderRadius: 6,
    border: "none",
    background: "#4a6cf7",
    color: "white",
    cursor: "pointer",
  },
};
