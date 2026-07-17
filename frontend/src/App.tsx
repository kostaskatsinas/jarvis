import { useEffect, useState } from "react";

interface Health {
  status: string;
  version: string;
  env: string;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 640, margin: "4rem auto", padding: "0 1rem" }}>
      <h1>Jarvis</h1>
      {health && (
        <p>
          Backend: <strong>{health.status}</strong> · v{health.version} · {health.env}
        </p>
      )}
      {error && <p style={{ color: "crimson" }}>Backend unreachable: {error}</p>}
      {!health && !error && <p>Checking backend…</p>}
    </main>
  );
}
