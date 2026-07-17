# Deploy & Hardening Runbook (Deliverable 6)

Exact commands for taking a fresh Ubuntu 24.04 VPS (Hostinger KVM 2) to a
hardened, HTTPS-served Jarvis. Home-server deltas at the end. Run as root
unless stated; adjust names to taste.

## 1. Users and SSH

```bash
adduser jarvis-op
usermod -aG sudo jarvis-op

# From YOUR local machine: install your key for the new user
ssh-copy-id -i ~/.ssh/id_ed25519.pub jarvis-op@<VPS_IP>
```

Lock sshd down (`/etc/ssh/sshd_config.d/90-hardening.conf`):

```bash
cat >/etc/ssh/sshd_config.d/90-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
MaxAuthTries 3
AllowUsers jarvis-op
EOF
systemctl restart ssh
```

Verify you can log in as `jarvis-op` with your key **before closing your
root session**.

## 2. Base packages, automatic security updates

```bash
apt update && apt -y upgrade
apt -y install ufw fail2ban unattended-upgrades curl git
dpkg-reconfigure -plow unattended-upgrades   # accept "Yes"
```

## 3. Firewall (UFW)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp     # HTTP/3
ufw enable
ufw status verbose
```

**Docker caveat, understood and handled:** ports *published* by Docker
bypass UFW entirely (Docker writes its own iptables rules). Our compose file
is designed around that: the only services publishing to all interfaces are
Caddy's 80/443 (meant to be public), Postgres/Redis/ClickHouse/MinIO/Langfuse
publish nothing, and Ollama binds to `OLLAMA_BIND_IP` (Tailscale IP or
127.0.0.1) so it physically can't listen publicly. Keep it that way: never
add a `ports:` entry with a bare `"port:port"` unless it's meant to be
world-reachable.

## 4. fail2ban (sshd jail)

```bash
cat >/etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
EOF
systemctl enable --now fail2ban
fail2ban-client status sshd
```

(Login brute-force against the app itself is throttled in the backend —
5 attempts/min/IP on `/api/auth/login` — and Langfuse has its own lockouts.)

## 5. Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker jarvis-op
```

Never mount `/var/run/docker.sock` into a container (nothing in this stack
does), and leave the daemon listening on the local socket only (default).

## 6. Tailscale (VPS ↔ home tunnel)

On **both** the VPS and the home server:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up        # authenticate in the browser once per machine
tailscale ip -4     # note each machine's 100.x.y.z address
```

In the tailnet admin console, disable key expiry for both machines
(Machines → ⋯ → Disable key expiry), or the tunnel dies silently in 180 days.

## 7. DNS at Papaki

In the Papaki DNS manager for your domain, add A records pointing at the
VPS public IP:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `jarvis` | `<VPS_IP>` | 600 |
| A | `traces` | `<VPS_IP>` | 600 |

Low TTL (600s) is deliberate — it makes the eventual VPS↔home migration a
ten-minute cutover instead of a day of stale caches.

## 8. Deploy

As `jarvis-op`:

```bash
git clone https://github.com/kostaskatsinas/jarvis.git ~/jarvis
cd ~/jarvis
cp .env.example .env
make secrets          # prints generated values; paste into .env
nano .env             # fill in DOMAIN, ACME_EMAIL, JARVIS_ADMIN_*, API keys,
                      # LANGFUSE_ADMIN_*, OLLAMA_BASE_URL=http://<home-tailscale-ip>:11434
make prod
docker compose ps     # everything Up/healthy after ~1 min
```

First-boot checks:

```bash
curl -s https://jarvis.<domain>/api/health          # {"status":"ok",...}
# Dashboard: https://jarvis.<domain>  -> log in with JARVIS_ADMIN_EMAIL/PASSWORD
# Traces:    https://traces.<domain>  -> log in with LANGFUSE_ADMIN_EMAIL/PASSWORD
```

TLS is automatic: Caddy obtains and renews Let's Encrypt certificates for
both subdomains on first request; certificates persist in the `caddy_data`
volume.

## 9. What auth is in force

- Dashboard/API: JWT (30-min access token) + httponly refresh cookie
  (14 days, `Secure`, `SameSite=Strict`, scoped to `/api/auth`). The single
  user is bootstrapped from `JARVIS_ADMIN_EMAIL/_PASSWORD` on first start.
- WebSocket streams authenticate with the access token.
- API docs (`/api/docs`) are disabled outside dev.
- Langfuse UI: its own login; signup disabled after the bootstrapped admin.
- Everything else (Postgres, Redis, ClickHouse, MinIO, backend) is reachable
  only on the compose-internal network.
- Password change (single-user pragmatism): set the new value in `.env`,
  then `docker compose exec postgres psql -U jarvis -c "DELETE FROM users;"
  && docker compose restart backend` — the user re-bootstraps.
- Rotating `JARVIS_SECRET_KEY` invalidates all tokens immediately (log out
  everywhere).

## 10. Home-server deltas

Same runbook, sections 1–6, plus:

```bash
# .env differences:
#   OLLAMA_BIND_IP=<this machine's tailscale IP>   # NOT 0.0.0.0
#   OLLAMA_BASE_URL=http://ollama:11434            # backend reaches it in-network
make prod-home        # includes the Ollama container

# Pull models sized for ~8 GB RAM (3-8B quantized):
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull llama3.2:3b
```

If the home server sits behind a router, no port forwarding is needed —
Tailscale handles reachability, and that's the point.
