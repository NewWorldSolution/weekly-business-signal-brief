# Iteration 12 — Server Deployment & Production Operations
## Detailed Task Plan

**Status:** Planning complete. Ready to start.
**Baseline:** 443 tests passing, ruff clean, main stable.
**Prerequisite:** I11 complete (security hardening). `main` must be stable before any deployment work.

---

## Purpose

I12 takes WBSB from a secured local MVP to a live, remotely accessible server. After I11, the feedback endpoint is fully authenticated and hardened. I12 deploys the application to a real server using Docker Compose, establishes the reverse proxy (Caddy for automatic TLS), sets up the scheduler for unattended operation, and documents the full operational runbook.

After I12, WBSB runs continuously on a server, delivers weekly briefs automatically, and accepts authenticated feedback from authorised operators.

**I12 is the prerequisite for future multi-tenant or dashboard work (I8).** Do not build I8 server-side features until I12's deployment foundation is established.

---

## Critical Architecture Rules

These rules apply to every I12 task.

**Rule 1 — Secrets never in code or config files**
All secrets (API keys, webhook URLs, HMAC secret) are injected at runtime via `.env` on the server. No secret ever appears in a committed file.

**Rule 2 — Docker is the deployment unit**
All services run as Docker containers managed by `docker-compose.prod.yml`. Manual process management outside Docker is not acceptable for production.

**Rule 3 — Caddy handles TLS**
All external traffic is TLS-terminated by Caddy. The feedback server container is never exposed directly. `WBSB_REQUIRE_HTTPS=true` is always set in production.

**Rule 4 — Makefile wraps all operations**
Every common operator action (deploy, restart, logs, backup, smoke test) is a single `make <target>` command. Operators must not need to remember raw Docker commands.

**Rule 5 — No silent deployment failures**
Every deploy step must verify its own outcome. `make smoke-test` must pass after every deploy.

---

## Deployment Target Decision

**This decision must be made and documented in I12-0 before any task work begins.**

I12 supports two deployment paths. Choose one before starting I12-0.

| | Path A — VPS (Hetzner/DigitalOcean) | Path B — Azure Container Apps |
|---|---|---|
| **Cost** | €4–$6/month | $0–5/month (free tier likely sufficient) |
| **Learning value** | High — Linux, Docker, SSH, cron, firewall | High — Azure CLI, container registry, managed infra |
| **Complexity** | You manage the OS and Docker | Azure manages the OS; you manage the app |
| **TLS** | Caddy handles automatically | Azure handles automatically |
| **Scheduler** | Host cron | Azure Container Apps Jobs (scheduled) |
| **Recommended if** | You want to understand how servers work | You want to leverage existing M365 subscription |

Both paths produce the same end result. Path B is documented as an alternative in `docs/deployment/azure.md`. **All task details below are Path A (VPS) only.** If Path B is chosen, the I12-0 pre-work must produce Azure-specific specs to replace the VPS-specific task details for I12-1 (no server setup), I12-3 (no Caddyfile — Azure handles TLS), I12-6 (Container Apps Jobs instead of host cron), and I12-7 (no `/opt/wbsb/.env` — Azure Key Vault or app settings). The branch structure and DoD remain the same for either path.

---

## Scope Boundaries

| In scope (I12) | Out of scope |
|---|---|
| VPS provisioning runbook (`docs/deployment/server-setup.md`) | Multi-server / Kubernetes / cloud-managed infra |
| `docker-compose.prod.yml` with restart policies and named volumes | CDN or load balancer configuration |
| Reverse proxy config (Caddy + automatic TLS) | Auto-scaling |
| `Makefile` with deploy, logs, backup, smoke-test targets | Multi-tenant RBAC |
| `GET /health` endpoint in `server.py` | Dashboard (I8 scope) |
| Scheduler production config + docs | CI/CD auto-deploy pipeline (post-I12) |
| Secrets management + env-management docs | Monitoring dashboards (post-I12) |
| Operations runbook | SIEM integration |
| `scripts/smoke_test.sh` | Custom domain purchase / DNS configuration (operator pre-condition) |

---

## Branching Strategy

```
main
 └── feature/iteration-12
      ├── feature/i12-0-pre-work          ← docs structure + deployment decision
      ├── feature/i12-2-prod-compose      ← docker-compose.prod.yml
      ├── feature/i12-3-caddy-tls         ← Caddyfile + tls.md
      ├── feature/i12-4-makefile          ← Makefile + smoke_test.sh
      ├── feature/i12-5-health-endpoint   ← GET /health
      ├── feature/i12-6-scheduler         ← scheduler config + scheduler.md
      └── feature/i12-7-runbooks          ← env-management.md + operations.md
```

**Rules (same as all iterations):**
- Every task branch is created from `feature/iteration-12` — never from `main`
- Every task PR targets `feature/iteration-12` — never `main`
- `main` stays stable throughout the entire iteration
- I12-1 (VPS provisioning) and I12-8 (architecture review) are done by You — no branches needed
- `feature/iteration-12` → `main` via one final PR after I12-8 review passes

---

## Execution Order and Dependencies

```
I12-0  [Claude]  Pre-work: docs structure, deployment decision, specs         → no dependencies
I12-1  [You]     VPS provisioning + initial server setup (runbook only)       → I12-0
I12-5  [Codex]   GET /health endpoint in server.py                            → I12-0
I12-3  [Codex]   Caddyfile + TLS docs (docs/deployment/tls.md)               → I12-0
I12-2  [Codex]   docker-compose.prod.yml (restart, volumes, health checks)    → I12-3, I12-5
I12-4  [Claude]  Makefile + scripts/smoke_test.sh                             → I12-2
I12-6  [Claude]  Scheduler production config + docs/deployment/scheduler.md   → I12-2
I12-7  [Claude]  docs/deployment/env-management.md + operations.md            → I12-2, I12-4, I12-6
I12-8  [You]     Architecture review                                           → I12-7
I12-9  [Claude]  Final cleanup + merge to main                                 → I12-8
```

**Dependency diagram:**
```
I12-0
 ├── I12-1 (runbook — parallel with coding tasks)
 ├── I12-5 ──────────────────────┐
 └── I12-3 ──────────────────────┼──► I12-2 ──► I12-4 ──┐
                                 │           └── I12-6 ──┼──► I12-7 → I12-8 → I12-9
                                 └───────────────────────┘
```

**Parallelism opportunities:**
- After I12-0: I12-1, I12-3, and I12-5 can all start simultaneously
  - I12-3 (Caddyfile) does not depend on any code — only needs the server port and domain placeholder
  - I12-5 (health endpoint) is a single-file code change, fully independent of proxy config
  - I12-1 (VPS provisioning) is a human task — no conflict with coding worktrees
- I12-2 starts after I12-3 and I12-5 merge — the compose file references the Caddy config structure and the `/health` route for the health check definition
- I12-4 and I12-6 can start in parallel after I12-2 merges
- I12-7 starts after I12-4 and I12-6 both merge — the operations runbook needs the full Makefile and scheduler docs to be final

---

## Task Summary

| Task | Owner | Description | Depends on |
|---|---|---|---|
| I12-0 | Claude | Pre-work: docs structure, deployment decision, specs | — |
| I12-1 | You | VPS provisioning + initial server setup (runbook only, no code) | I12-0 |
| I12-2 | Codex | `docker-compose.prod.yml` — restart policies, named volumes, health checks | I12-3, I12-5 |
| I12-3 | Codex | `Caddyfile` + TLS docs (`docs/deployment/tls.md`) | I12-0 |
| I12-4 | Claude | `Makefile` with all standard targets + `scripts/smoke_test.sh` | I12-2 |
| I12-5 | Codex | `GET /health` endpoint in `src/wbsb/feedback/server.py` | I12-0 |
| I12-6 | Claude | Scheduler production config + `docs/deployment/scheduler.md` | I12-2 |
| I12-7 | Claude | `docs/deployment/env-management.md` + `docs/deployment/operations.md` | I12-2, I12-4, I12-6 |
| I12-8 | You | Architecture review | I12-7 |
| I12-9 | Claude | Final cleanup + merge to main | I12-8 |

---

## Task Details

### I12-0 — Pre-work (Claude)

**Deliverables:**
- Create `docs/deployment/` directory with placeholder files for all docs tasks
- Document the chosen deployment path (Path A or Path B) in `docs/deployment/README.md`
- Write the health endpoint spec (response shape, auth requirements, which files are allowed)
- Write the Caddyfile spec (domain placeholder, upstream port)
- Confirm `docker-compose.prod.yml` requirements (services, volumes, health check format)
- Open draft PRs for all task branches

**Allowed files:** `docs/iterations/i12/`, `docs/deployment/`

---

### I12-1 — VPS Provisioning (You)

**Deliverable:** `docs/deployment/server-setup.md` — a complete, step-by-step runbook for provisioning a fresh VPS and preparing it to run `docker compose up -d`.

**Steps covered:**
- Provision Ubuntu 24.04 LTS (Hetzner CX22 recommended: 2 vCPU, 4 GB RAM, ~€4/month)
- Install Docker and Docker Compose
- Create non-root deploy user (`wbsb`, UID 1000) with sudo
- SSH key authentication only — password auth disabled
- UFW firewall: ports 22, 80, 443 allowed; all others denied
- System timezone set to match business location
- Clone the repo: `git clone <repo> /opt/wbsb`
- Create `/opt/wbsb/data/` for weekly input files

No code changes. This is a human-executed runbook task.

---

### I12-2 — Production Docker Compose (Codex)

**Allowed files:** `docker-compose.prod.yml`

**Requirements:**
- `restart: unless-stopped` on all services
- Named Docker volumes for `runs/`, `feedback/`, `logs/`
- Bind mount `/opt/wbsb/data` → `/data` inside the pipeline container (production input path)
- No development bind mounts (`./src:/app/src` etc.)
- Health check defined for the feedback server container (uses `GET /health`)
- Resource limits: `mem_limit: 512m` on pipeline container; `mem_limit: 128m` on feedback server
- Environment sourced from `.env` file on server (not committed to repo)
- Caddy runs as a separate container; feedback server not exposed directly

---

### I12-3 — Caddy Reverse Proxy + TLS (Codex)

**Allowed files:** `Caddyfile`, `docs/deployment/tls.md`

**Requirements:**
- `Caddyfile` committed to repo with placeholder domain (`feedback.yourdomain.com`)
- Reverse proxy to the feedback server container on its internal port
- TLS handled automatically by Caddy (Let's Encrypt)
- `docs/deployment/tls.md` covers: DNS A record pre-condition, how Caddy obtains the certificate, how to verify TLS is active, what to do if the certificate fails

**Pre-condition note:** A DNS A record pointing to the server IP must exist before Caddy can obtain a Let's Encrypt certificate. Domain purchase and DNS configuration are operator responsibilities and are not deliverables of this task. Document this as a pre-condition in `tls.md`.

---

### I12-4 — Makefile + Smoke Test (Claude)

**Allowed files:** `Makefile`, `scripts/smoke_test.sh`

**Required Makefile targets:**
```makefile
deploy:            ## git pull + docker compose -f docker-compose.prod.yml up --build -d
logs:              ## Tail logs from all containers
status:            ## Show container health and uptime; reads last entry from runs/index.json
restart:           ## Restart all containers
restart-feedback:  ## Restart only the feedback server container (use after rotating WBSB_FEEDBACK_SECRET)
backup:            ## Archive runs/, feedback/, data/ to dated tarball in /opt/wbsb/backups/
smoke-test:        ## Run scripts/smoke_test.sh — sends HMAC-signed POST /feedback, asserts HTTP 200
```

**`scripts/smoke_test.sh`:** Reads `WBSB_FEEDBACK_SECRET` from the environment. Sends a valid HMAC-signed `POST /feedback` and asserts HTTP 200. Never hardcodes the secret. Must exit non-zero on failure.

**Backup implementation:** Uses `docker run --rm` with volume mounts to create a dated archive without stopping containers.

---

### I12-5 — Health Check Endpoint (Codex)

**Allowed files:** `src/wbsb/feedback/server.py`, and corresponding test file.

**Response:** `{"status": "ok", "timestamp": "<ISO8601>"}` — HTTP 200 always, no auth required.

Used by: Docker health check in `docker-compose.prod.yml`, Caddy upstream health probing, external uptime monitors.

---

### I12-6 — Scheduler Production Config (Claude)

**Allowed files:** `docs/deployment/scheduler.md`

**Contents of `scheduler.md`:**
- Production schedule options (host cron is recommended for VPS):
  ```cron
  0 6 * * 1 docker compose -f /opt/wbsb/docker-compose.prod.yml run --rm pipeline wbsb run --auto --watch-dir /data
  ```
- Input file transfer procedure (SCP to `/opt/wbsb/data/` before 6am Monday)
- How to verify the scheduler fired (check `runs/index.json`, container logs)
- How to manually trigger a run
- No-file behaviour: `wbsb run --auto` exits gracefully if no new file is present

---

### I12-7 — Secrets Management + Operations Runbook (Claude)

**Allowed files:** `docs/deployment/env-management.md`, `docs/deployment/operations.md`

**`env-management.md`:**
- `.env` file location: `/opt/wbsb/.env`, owned by deploy user, permissions `0o600`
- Never committed to the repo
- Initial setup procedure
- How to rotate any single secret: edit `.env`, then `make restart-feedback` (or `make restart`)
- What to do if a secret is compromised

**`operations.md`:** Intended audience: business owner or non-technical assistant.
- How to tell if the Monday report ran successfully
- How to re-trigger a run manually
- What to do if the report was not delivered
- How to check container logs (`make logs`)
- How to rotate an API key or webhook URL
- How to restore from backup

---

## Definition of Done

**Deployment:**
- [ ] `docker compose -f docker-compose.prod.yml up -d` starts all services on a fresh VPS from the documented setup runbook
- [ ] All containers show `healthy` status after startup

**TLS and network** *(evaluated after DNS A record is pointed to the server IP):*
- [ ] `https://feedback.yourdomain.com/health` returns `{"status": "ok", "timestamp": "<ISO8601>"}` with HTTP 200 and a valid Let's Encrypt certificate
- [ ] `http://` request redirects to `https://` (Caddy default behaviour)
- [ ] `POST /feedback` with `X-Forwarded-Proto: http` returns HTTP 400 (I11 requirement active in production)
- [ ] If DNS not yet configured, TLS acceptance deferred; all other criteria still pass using server IP directly

**Scheduler:**
- [ ] Scheduler fires at configured time; run artifact written to named volume without manual intervention
- [ ] Delivery dispatched to Teams or Slack within 5 minutes of pipeline completion
- [ ] `make status` shows timestamp of last successful run

**Security (I11 controls active in production):**
- [ ] `POST /feedback` without valid HMAC returns HTTP 401
- [ ] `POST /feedback` with valid HMAC and fresh nonce returns HTTP 200 over HTTPS
- [ ] `docker inspect` confirms containers run as UID 1000 (non-root)
- [ ] No secrets appear in `docker history --no-trunc wbsb` output

**Operations:**
- [ ] `make deploy` completes without manual steps; containers restart cleanly
- [ ] `make backup` produces a dated archive of `runs/` and `feedback/` volumes
- [ ] `make smoke-test` passes end-to-end after a clean deploy
- [ ] `docs/deployment/` contains: `server-setup.md`, `tls.md`, `env-management.md`, `scheduler.md`, `operations.md`

**Regression:**
- [ ] All 443+ tests pass; ruff clean
- [ ] `wbsb eval` golden cases all pass
