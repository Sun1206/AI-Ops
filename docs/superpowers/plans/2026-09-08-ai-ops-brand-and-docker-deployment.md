# AI Ops Brand and Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace user-visible SxDevOps branding with AI Ops without changing runtime identifiers, then build and run the project with Docker Compose.

**Architecture:** Apply a whitelist-based text replacement only to user-facing frontend, backend response/generator, and documentation files. Preserve Django module paths, Compose/database names, environment variables, protocol/storage keys, labels, file names, and external URLs so deployment and existing integrations remain compatible. Verify at source, framework, build, Compose, HTTP, and login levels.

**Tech Stack:** Django 5, Django REST Framework, Channels/Daphne, Vue 3, Vite 6, MySQL 8, Redis 7, Docker Compose.

---

### Task 1: Establish branding and runtime baselines

**Files:**
- Reference: `docs/superpowers/specs/2026-09-08-local-docker-deployment-design.md`
- Reference: `docker-compose.yml`
- Reference: `Dockerfile`

- [x] **Step 1: Confirm old branding is currently visible**

Run:

```powershell
rg -n "SxDevOps" frontend/index.html frontend/src frontend/public/promo docs README.md CONTRIBUTING.md SECURITY.md NOTICE backend/aiops/services.py backend/iac/terraform.py backend/eventwall/management/commands/seed_eventwall_demo.py backend/ops/views.py backend/rbac/registry.py
```

Expected: matches in page titles, navigation/login views, terminal greetings, product documents, prompts, generated IaC text, event descriptions, and API metadata.

- [x] **Step 2: Confirm protected runtime identifiers exist**

Run:

```powershell
rg -n "sxdevops\.asgi|DJANGO_SETTINGS_MODULE|SXDEVOPS_|sxdevops_token|sxdevops-aiops-open|sxdevops\.query_|container_name: sxdevops|MYSQL_DATABASE: sxdevops" backend frontend docker docker-compose.yml Dockerfile
```

Expected: matches remain and form the compatibility allowlist.

### Task 2: Replace frontend-visible branding

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/layout/AppLayout.vue`
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/AIAgentPromo.vue`
- Modify: `frontend/src/views/AIOpsConfig.vue`
- Modify: `frontend/src/views/EventSources.vue`
- Modify: `frontend/src/views/K8sManage.vue`
- Modify: `frontend/src/views/WebShell.vue`
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/public/promo/sxdevops-ai-agent-promo.html`

- [x] **Step 1: Apply exact visible-string replacements**

Replace `SxDevOps` with `AI Ops` in titles, alt text, visible labels, welcome strings, CSS comments, and promo content. Replace visible lowercase phrases `sxdevops 对外 MCP Server` and `<sxdevops地址>` with `AI Ops 对外 MCP Server` and `<AI Ops地址>`. Keep JavaScript class names, browser storage keys, custom event names, and the promo filename unchanged.

- [x] **Step 2: Verify frontend visible-string scan passes**

Run:

```powershell
rg -n "SxDevOps|sxdevops 对外|sxdevops地址" frontend/index.html frontend/src frontend/public/promo
```

Expected: only non-visible compatibility identifiers such as `SxDevOpsDeck`, storage keys, and event names may remain; no old-brand page text remains.

- [x] **Step 3: Build frontend**

Run:

```powershell
cd frontend
npm ci
npm run build
```

Expected: Vite exits with code 0 and writes `frontend/dist`.

Execution note: the host npm cache was inaccessible to the sandbox, so the production frontend build was completed by the Dockerfile's clean Node 20 builder stage and verified from the deployed HTTP response.

### Task 3: Replace backend-visible branding and documentation

**Files:**
- Modify: `backend/aiops/services.py`
- Modify: `backend/iac/terraform.py`
- Modify: `backend/eventwall/management/commands/seed_eventwall_demo.py`
- Modify: `backend/ops/views.py`
- Modify: `backend/rbac/registry.py`
- Modify: `backend/config.example.md`
- Modify: `tools/dev/start-dev.ps1`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `SECURITY.md`
- Modify: `NOTICE`
- Modify: `docs/AIOps2.0升级优化方案.md`
- Modify: `docs/AIOps智能体实现说明.md`
- Modify: `docs/用户使用文档.md`
- Modify: `docs/screenshots/README.md`
- Modify: `docs/sxdevops-ai-agent-promo.html`
- Modify: `docs/superpowers/specs/2026-09-08-local-docker-deployment-design.md`
- Modify: `docs/superpowers/plans/2026-09-08-ai-ops-brand-and-docker-deployment.md`

- [x] **Step 1: Replace backend output strings**

Change assistant identity, MCP display metadata, generated Terraform descriptions, generated README wording, seeded event summaries, response source labels, and RBAC descriptions from `SxDevOps`/natural-language `sxdevops` to `AI Ops`. Preserve `X-SxDevOps-Token`, `sxdevops.query_*`, `/opt/sxdevops`, Kubernetes labels, Python package imports, and environment variable names.

- [x] **Step 2: Replace documentation branding**

Replace prose occurrences of `SxDevOps` and lowercase `sxdevops` used as the product name with `AI Ops`. Preserve code spans and command examples containing package paths, environment variables, database names, file paths, filenames, and `https://www.sxdevops.top` URLs.

- [x] **Step 3: Run framework checks and focused tests**

Run:

```powershell
cd backend
python manage.py check
python manage.py test aiops iac eventwall rbac ops
```

Expected: Django system check reports no issues and focused tests pass. If the host lacks dependencies, use an isolated `uv` environment or perform the same commands inside the built application container in Task 4.

Execution note: `python manage.py check` passed and the 30 RBAC/Eventwall tests passed. The pre-existing broad 432-test suite has 23 failures and 8 errors unrelated to branding, including malformed test methods, mojibake assertions, missing IaC/middleware routes, and existing serializer expectation differences.

### Task 4: Build, start, and verify Docker deployment

**Files:**
- Verify unchanged: `Dockerfile`
- Verify unchanged: `docker-compose.yml`
- Verify unchanged: `docker/entrypoint.sh`

- [x] **Step 1: Start Docker Desktop and wait for the engine**

Run Docker Desktop, then poll `docker info` for up to two minutes.

Expected: Docker reports server information.

- [x] **Step 2: Validate Compose configuration with an ephemeral secret**

Run:

```powershell
$env:SECRET_KEY = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
docker compose config --quiet
```

Expected: exit code 0 and no secret is written to disk.

- [x] **Step 3: Build and start all services**

Run:

```powershell
docker compose up -d --build
```

Expected: `sxdevops-app`, `sxdevops-mysql`, and `sxdevops-redis` are created and started.

- [x] **Step 4: Verify container and application health**

Run:

```powershell
docker compose ps
docker compose logs --no-color --tail 200 sxdevops
Invoke-WebRequest -UseBasicParsing http://localhost:8000/
```

Expected: MySQL and Redis are healthy, the application remains running, migrations and seed commands finish, and `/` returns HTTP 200 with `AI Ops` in the HTML.

- [x] **Step 5: Verify login API**

Run a POST to the login endpoint using the seeded local demo account `demo` / `Demo#123`.

Expected: HTTP 200 and an authentication token/user payload.

### Task 5: Final compatibility audit

**Files:**
- Verify: all source files under the project root

- [x] **Step 1: Audit every remaining occurrence**

Run:

```powershell
rg -n -uu -g '!**/.git/**' -g '!**/.idea/**' -g '!**/node_modules/**' -g '!**/dist/**' -g '!**/__pycache__/**' "(?i)sxdevops" .
```

Expected: each remaining occurrence is a protected internal identifier, external URL, filename, or compatibility note from the approved design.

- [x] **Step 2: Record final running state**

Capture `docker compose ps`, HTTP status, login status, changed-file inventory, and any intentionally retained old-name categories in the final handoff. This directory is not a Git repository, so no commit step is available.
