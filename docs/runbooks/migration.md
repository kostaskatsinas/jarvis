# Migration Runbook: VPS ↔ Home Server (Deliverable 7)

The whole system is: **repo + `.env` + Postgres + three volumes**. Migration
is a restore on the target followed by a DNS flip. Budget ~30 minutes, most
of it waiting on transfer and DNS.

Downtime is acceptable (single user); this runbook takes the simple
stop-copy-start path rather than anything clever.

## 0. Prerequisites on the target

- Hardening runbook sections 1–6 done (SSH, UFW, fail2ban, Docker, Tailscale).
- Repo cloned: `git clone https://github.com/kostaskatsinas/jarvis.git ~/jarvis`

## 1. Freeze and back up the source

```bash
cd ~/jarvis
docker compose --profile local-llm stop backend   # stop new runs first
FULL=1 ./scripts/backup.sh                        # dumps + all volume snapshots
docker compose --profile local-llm down           # full stop after the backup
```

(Backup before `down` because `pg_dump` needs Postgres up. The backend goes
down first so nothing writes between dump and stop.)

## 2. Transfer to the target (over Tailscale)

```bash
scp -r ~/jarvis-backups/<timestamp> <target-tailscale-ip>:migration
scp ~/jarvis/.env <target-tailscale-ip>:jarvis/.env
```

## 3. Adjust `.env` for the target

| Variable | VPS → Home | Home → VPS |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` (in-stack) | `http://<home-tailscale-ip>:11434` (over tailnet) — or empty for API-only |
| `OLLAMA_BIND_IP` | this machine's Tailscale IP | irrelevant (profile off) |

Everything else — domain, secrets, keys — moves unchanged. That's the point.

## 4. Restore and start on the target

Follow the restore section of `docs/runbooks/backup.md` steps 1–3 with
`BACKUP=~/migration`, then:

```bash
make prod-home    # on the home server;  make prod  on a VPS
docker compose ps # wait for Up/healthy
```

## 5. Verify BEFORE touching DNS

Pin the domain to the target on your laptop only:

```bash
sudo sh -c 'echo "<target-public-or-tailscale-ip> jarvis.<domain> traces.<domain>" >> /etc/hosts'
```

Check: dashboard login works, run history is present, a test chat run
completes, Langfuse shows the trace. Then remove the `/etc/hosts` line.

(TLS note: with the `caddy_data` snapshot restored, existing certificates
come along and there is no reissue at all. Caddy will also happily reissue
via the usual HTTP challenge after DNS points at the target — the snapshot
just makes the cutover seamless.)

## 6. Cut over DNS

At Papaki, edit both A records (`jarvis`, `traces`) to the target's public
IP. TTL is 600s, so the world follows within ~10 minutes.

Home-server caveat: this assumes the home connection has a stable public IP
and ports 80/443 forwarded to the server. If the ISP address rotates, add a
DDNS updater for the Papaki records, or keep the VPS as the permanent public
entry point.

## 7. Decommission the source

Leave the stopped source stack in place for a week as an instant rollback
(step 6 in reverse is the entire rollback plan). After that:

```bash
docker compose --profile local-llm down --volumes   # deletes source data
```

The source machine keeps its copy of `~/jarvis-backups` — that's the offsite
backup leg, don't delete it.
