# Iteration 12 — Server Deployment & Production Operations
## Detailed Task Plan

**Status:** Planning complete. Ready to start.
**Baseline:** 443 tests passing, ruff clean, main stable.
**Prerequisite:** I11 complete (security hardening). `main` must be stable before any deployment work.

---

## Purpose

I12 takes WBSB from a secured local MVP to a live, remotely accessible server. After I11, the feedback endpoint is fully authenticated and hardened. I12 deploys the application to a real server, establishes the reverse proxy (TLS termination), sets up process supervision, configures the scheduler for unattended operation, and documents the full operational runbook.

After I12, WBSB runs continuously on a server, delivers weekly briefs automatically, and accepts authenticated feedback from authorised operators.

**I12 is the prerequisite for future multi-tenant or dashboard work (I8).** Do not build I8 server-side features until I12's deployment foundation is established.

---

## Critical Architecture Rules

These rules apply to every I12 task.

**Rule 1 — Secrets never in code or config files**
All secrets (API keys, webhook URLs, HMAC secret) are injected at runtime via environment variables or a secrets manager. No secret ever appears in a committed file.

**Rule 2 — Idempotent deploy scripts**
Every provisioning and deploy script must be safe to run multiple times without side effects. Running the deploy script twice must produce the same state as running it once.

**Rule 3 — Supervisor manages the process**
The feedback server and scheduler run under a process supervisor (systemd or supervisord). Manual `nohup` runs are not acceptable for production.

**Rule 4 — TLS everywhere**
All external traffic must be TLS-terminated at the reverse proxy. `WBSB_REQUIRE_HTTPS=true` is always set in production.

**Rule 5 — No silent deployment failures**
Every deploy step must verify its own outcome. A step that completes without confirming success is not done.

---

## Scope Boundaries

| In scope (I12) | Out of scope |
|---|---|
| Server provisioning runbook | Multi-server / Kubernetes / cloud-managed infra |
| Reverse proxy setup (Caddy or nginx + TLS) | CDN or load balancer configuration |
| Process supervision (systemd or supervisord) | Auto-scaling |
| Scheduler unattended operation | Multi-tenant RBAC |
| Production `.env` secret management | Dashboard (I8 scope) |
| Deploy script (idempotent) | CI/CD auto-deploy pipeline (post-I12) |
| Operational runbook | Monitoring dashboards (post-I12) |
| Health check endpoint (`GET /health`) | Full observability stack (Grafana, Prometheus) |
| Log rotation | SIEM integration |
| Smoke test after deploy | |

---

## Branching Strategy

```
main
 └── feature/iteration-12
      ├── feature/i12-0-pre-work
      ├── feature/i12-1-health-endpoint
      ├── feature/i12-2-deploy-script
      ├── feature/i12-3-reverse-proxy
      ├── feature/i12-4-process-supervision
      ├── feature/i12-5-scheduler-production
      ├── feature/i12-6-runbook
      └── feature/i12-7-final-cleanup
```

**Rules (same as all iterations):**
- Every task branch is created from `feature/iteration-12` — never from `main`
- Every task PR targets `feature/iteration-12` — never `main`
- `main` stays stable throughout the entire iteration
- `feature/iteration-12` → `main` via one final PR after I12-8 review passes

---

## Execution Order and Dependencies

```
I12-0  [Claude]  Pre-work: docs, runbook skeleton, health endpoint spec    → no dependencies
I12-1  [Codex]   Health check endpoint (GET /health) in server.py          → I12-0
I12-3  [Codex]   Reverse proxy config (Caddy or nginx + TLS)               → I12-0
I12-4  [Codex]   Process supervision (systemd units)                        → I12-0
I12-5  [Codex]   Scheduler production config + unattended mode              → I12-0
I12-2  [Codex]   Deploy script (idempotent bash)                            → I12-3, I12-4, I12-5
I12-6  [Claude]  Operational runbook (deploy, rollback, rotate secrets)     → I12-1, I12-2
I12-7  [You]     Architecture review                                         → I12-6
I12-8  [Claude]  Final cleanup + merge to main                               → I12-7
```

**Dependency diagram:**
```
I12-0
 ├── I12-1 ──────────────────────────────────────────────────────┐
 ├── I12-3 ──┐                                                   │
 ├── I12-4 ──┼──► I12-2 (deploy script — bundles all components) ┼──► I12-6 → I12-7 → I12-8
 └── I12-5 ──┘                                                   │
                                                                  ┘
```

**Parallelism opportunities:**
- After I12-0: I12-1, I12-3, I12-4, I12-5 can all start simultaneously (4 Codex worktrees)
  - I12-3 does not need I12-1 implemented — only needs the server port/path, which I12-0 specifies
  - I12-4 does not need I12-3 — systemd units only need the run command and port, not the proxy config
  - I12-5 does not need I12-4 — scheduler config is independent of the feedback server's supervision
- I12-2 starts after I12-3, I12-4, I12-5 all merge — the deploy script must bundle all components
- I12-6 starts after I12-1 and I12-2 — runbook needs the health endpoint and deploy script finalised

---

## Task Summary

| Task | Owner | Description | Depends on |
|---|---|---|---|
| I12-0 | Claude | Pre-work: docs, runbook skeleton, health endpoint spec | — |
| I12-1 | Codex | `GET /health` endpoint in `server.py` | I12-0 |
| I12-3 | Codex | Reverse proxy config (Caddy or nginx) + TLS | I12-0 |
| I12-4 | Codex | systemd unit files for feedback server and scheduler | I12-0 |
| I12-5 | Codex | Scheduler production config + unattended weekly runs | I12-0 |
| I12-2 | Codex | Idempotent deploy script (bundles all components) | I12-3, I12-4, I12-5 |
| I12-6 | Claude | Full operational runbook | I12-1, I12-2 |
| I12-7 | You | Architecture review | I12-6 |
| I12-8 | Claude | Final cleanup + merge to main | I12-7 |

---

## Definition of Done

- [ ] `GET /health` returns `{"status": "ok"}` with HTTP 200 (unauthenticated)
- [ ] Deploy script is idempotent and documented
- [ ] TLS certificate provisioned; all external traffic HTTPS
- [ ] Feedback server runs under process supervisor; auto-restarts on crash
- [ ] Scheduler runs unattended on the configured weekly cadence
- [ ] Secrets injected at runtime — no secrets in committed files
- [ ] Operational runbook covers: initial deploy, secret rotation, rollback, log inspection
- [ ] Smoke test after deploy: `wbsb run` + `POST /feedback` succeed end-to-end
- [ ] All 443+ tests pass; ruff clean
- [ ] `main` branch stable
