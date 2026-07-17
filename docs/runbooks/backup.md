# Backup Strategy (Deliverable 9)

## What matters, in order

| Data | Where | Policy | Why |
|---|---|---|---|
| App state (runs, memory, users, checkpoints) + Langfuse relational data | Postgres | **daily hot dump** | the only truly irreplaceable state |
| Secrets | `.env` | copied with every backup | without it the dumps are useless |
| TLS certificates | `caddy_data` volume | weekly snapshot | reissuable, but restoring avoids Let's Encrypt rate limits during a migration |
| Traces | `clickhouse_data` + `minio_data` volumes | weekly, crash-consistent, **expendable** | nice history, never load-bearing |
| Ollama models | `ollama_data` volume | **not backed up** | `ollama pull` recreates them |

`pg_dump` is hot and transactionally consistent — no downtime, ever, for the
daily backup. The weekly volume tars are taken without stopping containers;
for the trace stores that yields crash-consistent archives, which is an
accepted trade for zero downtime given traces are expendable. If you ever
want a perfect full snapshot (e.g. right before a migration):
`docker compose down && FULL=1 ./scripts/backup.sh` (the script works with
the stack down for volumes; Postgres dumps need it up — see the migration
runbook for the exact cold-backup order).

## The script

`scripts/backup.sh` (also `make backup`): dumps both databases in `pg_dump
-Fc` custom format, copies `.env` (mode 600), snapshots the three volumes on
Sundays or when `FULL=1`, prunes anything older than `PRUNE_DAYS` (default
14). Backups land in `~/jarvis-backups/<timestamp>/`.

Schedule it (as the deploy user, `crontab -e`):

```cron
# Daily at 04:30 — Postgres + .env, volumes on Sundays
30 4 * * * cd $HOME/jarvis && ./scripts/backup.sh >> $HOME/jarvis-backups/backup.log 2>&1
```

## Offsite: the two machines back each other up

You run two boxes connected by Tailscale — use that instead of paying for
storage. On the **VPS**, push to the home server (and vice versa on the home
server, swapping names):

```cron
# Daily at 05:00, after the local backup
0 5 * * * rsync -a --delete $HOME/jarvis-backups/ <home-tailscale-ip>:vps-backups/ >> $HOME/jarvis-backups/rsync.log 2>&1
```

(Requires the deploy user's SSH key authorized on the other machine:
`ssh-copy-id <other-machine>` once.) Result: every day, each machine holds
both its own history and the other's. A third copy on your laptop now and
then (`rsync <vps>:jarvis-backups/ ~/offline-jarvis/`) guards against both
boxes dying together.

## Restore (also the migration path)

On a machine with the repo cloned and `.env` in place:

```bash
BACKUP=~/jarvis-backups/<timestamp>

# 1. Fresh Postgres with both databases created by the init script
docker compose up -d postgres && sleep 10

# 2. Restore both databases
docker compose exec -T postgres pg_restore -U jarvis -d jarvis   --clean --if-exists < "$BACKUP/jarvis.dump"
docker compose exec -T postgres pg_restore -U jarvis -d langfuse --clean --if-exists < "$BACKUP/langfuse.dump"

# 3. Volumes, if snapshots exist (certs, traces)
for vol in caddy_data clickhouse_data minio_data; do
  [ -f "$BACKUP/${vol}.tar.gz" ] && docker run --rm \
      -v "jarvis_${vol}:/dest" -v "$BACKUP:/src:ro" \
      alpine sh -c "rm -rf /dest/* && tar xzf /src/${vol}.tar.gz -C /dest"
done

# 4. Everything else
make prod        # or prod-home
```

Startup migrations are a no-op against restored dumps (the schema and
`alembic_version` come with them).

## Trace retention

ClickHouse growth is the only unbounded disk consumer. Single-user volume is
small, but set project-level retention in the Langfuse UI (Project Settings →
Data Retention, e.g. 90 days) once and forget it.

## Test the restore, once

A backup that has never been restored is a hope, not a backup. After first
deploy, run the restore procedure into the dev stack (`make dev` + steps 1–2
against the dev Postgres) and check the dashboard shows your run history.
