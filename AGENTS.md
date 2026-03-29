# Shadi — Agent Guide

Multi-agent clinical diagnostic reasoning system for emergency medicine. Reads patient data via FHIR R4, runs five specialist agents over a shared 70B base model with hot-swapped LoRA adapters, and produces a ranked differential diagnosis before the physician walks in.

---

## Architecture at a Glance

```
EHR → FHIR MCP Server → Intake Agent → CaseObject
                                             ↓
                          Cardiology / Neurology / Pulmonology / Toxicology (parallel)
                                             ↓
                               Evidence Grounding Agent
                                             ↓
                                    A2A Debate Round
                                             ↓
                               Orchestrator → Safety Veto
                                             ↓
                           DiagnosticReport (FHIR) + Dashboard
```

All agents share a single **Meditron-70B** base model (FP4, ~38 GB) with four LoRA adapters hot-swapped via vLLM. No cloud APIs — PHI stays on the machine.

---

## Repository Layout

```
agents/
  base.py            # BaseAgent ABC — all agents inherit this
  intake/            # SNOMED/LOINC/RxNorm extraction → CaseObject
  specialists/       # Cardiology, neurology, pulmonology, toxicology
  evidence/          # PubMed + guidelines cross-reference
  safety/            # Safety veto (contraindications, allergies, meds)
  orchestrator/      # Fan-out, A2A debate, consensus synthesis
shadi_fhir/          # FHIR R4 normalizer (`fhir.resources` is the HL7 lib — avoid a top-level `fhir` pkg)
a2a/                 # A2A protocol schema + ENDORSE/CHALLENGE/MODIFY logic
models/              # vLLM engine wrapper + LoRA adapter management
api/                 # FastAPI app (routes, schemas, middleware)
dashboard/           # Next.js physician dashboard (bun)
docs/decisions/      # Architecture Decision Records — read before changing arch
tests/
  fixtures/          # De-identified MIMIC-IV sample cases
  unit/
skills/              # Shared agent skills — see Skills section below
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Python runtime | 3.11+ |
| Web framework | FastAPI + Uvicorn |
| Inference | vLLM 0.6+, LoRA via `--enable-lora` |
| Models | Meditron-70B (FP4) base + 4 LoRA adapters |
| FHIR | `fhir.resources` 7.1+ |
| Async task queue | Redis + arq |
| Database | PostgreSQL via asyncpg + SQLAlchemy async |
| NLP | spaCy + scispaCy |
| Dashboard | Next.js + bun |
| Containers | Docker Compose |

---

## Development Commands

```bash
# Python backend (from repo root)
pip install -e ".[dev]"
uvicorn api.main:app --reload

# Dashboard
cd dashboard && bun install && bun dev

# All services
docker compose up

# Tests
pytest tests/
```

---

## Rules

- **All architectural decisions go in `docs/decisions/` first.** See `adr-001-architecture.md` for format. Do not change the agent pipeline, model strategy, A2A protocol, or safety veto behavior without an ADR.
- **PHI never leaves the machine.** No cloud API calls for inference. No logging of patient data.
- **Safety veto is non-negotiable.** Changes to `agents/safety/` require explicit review. The veto must fire before any output reaches the dashboard.
- Run `pytest` before claiming any fix or feature is complete.

---

## Skills

Project-level skills live in `skills/`. They are tracked in git and shared across the team. When a task matches a skill, read the `SKILL.md` and follow it.

Only list skills in this file if they are actually tracked in this repository. Do not point agents at user-home-only skills or editor-specific symlink farms.

Repo-shared Cursor context lives in `.cursor/rules/` and `.cursor/agents/`. Prefer those tracked files over user-home copies such as `~/.cursor/agents/`.

For skill discovery and installation, use the Vercel `find-skills` workflow captured in `skills/find-skills/SKILL.md`. The upstream source is `https://skills.sh/vercel-labs/skills/find-skills`.

| Skill | When to use |
|---|---|
| `api-design-principles` | New FastAPI routes, FHIR endpoint design |
| `codebase-search` | Finding code by meaning when you don't know the exact symbol |
| `dispatching-parallel-agents` | 2+ independent tasks that can run without shared state |
| `find-skills` | Discovering and installing shared skills from the Vercel skills ecosystem |
| `writing-plans` | Multi-step tasks or features with a spec/requirements |
| `git-advanced-workflows` | Complex rebases, bisect, recovering commits |
| `mcp-builder` | Changes to the FHIR MCP server in `shadi_fhir/` |
| `python-performance-optimization` | Slow inference, memory pressure, profiling |
| `receiving-code-review` | When acting on code review feedback |
| `requesting-code-review` | After completing a feature or before merging |
| `subagent-driven-development` | Executing an existing plan with independent sub-tasks |
| `systematic-debugging` | Any bug, test failure, or unexpected behavior — before proposing fixes |
| `using-git-worktrees` | Feature work that needs isolation from current workspace |
| `verification-before-completion` | Before claiming work is done, fixed, or passing |

---

## Agent Communication (A2A)

Agents communicate via structured messages in `a2a/`. Valid message types: `ENDORSE`, `CHALLENGE`, `MODIFY`. The orchestrator tracks consensus and divergence across rounds. Do not add ad-hoc agent-to-agent calls outside the A2A protocol.

---

## Key Invariants

1. Specialist agents reason independently in parallel — no cross-talk before the debate round.
2. Evidence grounding runs after specialist reasoning, before debate.
3. The safety veto runs last, after consensus, and can block any recommendation unconditionally.
4. The LoRA adapter for each specialist must match the specialty's training domain exactly.

---

## Learned User Preferences

- Always use `bunx` instead of `npx` for all CLI tools in this project (e.g. `bunx skills add`, not `npx skills add`).
- Each GitHub issue gets its own branch, git worktree (under `.worktrees/` — gitignored), and a separate PR; never bundle multiple issues into one branch.

---

## Learned Workspace Facts

- Subagent model routing: `planner` → `claude-4.6-sonnet-medium-thinking` (strategic decomposition); `worker` → `gpt-5.4-medium` (Python agents, FHIR, A2A, API, models, infra — never `dashboard/`); `ui-engineer` → `claude-sonnet-4-6` (all work inside `dashboard/` exclusively); `reviewer` → `claude-opus-4-6` (verification and code review).
- Project-level skills for team sharing live in `.agents/skills/` (committed to git). `.cursor/` is gitignored. `.claude/skills/` is not used — the team does not use Claude.
- Dashboard design system (defined in `tailwind.config.ts` on the scaffold branch, inherited by all downstream issues): Vercel/Linear aesthetic; Tailwind `darkMode: 'class'`; light mode uses "Sage Whisper" palette (`--background: #F4F7F4`, `--surface: #FAFCFA`, `--border: #DCE6DB`, `--foreground: #161E15`, `--foreground-muted: #5B7258`) — green-family tokens chosen for harmony with the emerald accent; dark mode base slate-950; emerald-400/500 primary accent (high confidence, CTAs); red-500/600 safety veto/danger; amber-400/500 warnings/divergent agents; monospace for clinical scores and numbers, sans-serif for prose.
- Dashboard routing (established in issue #69, which superseded #42/#43/#44): `/` = role-selection landing (Nurse vs Doctor); `/nurse` = triage intake form (chief complaint → `POST /cases`); `/doctor` = cases list with report cards and live agent progress.
- Next.js hydration rule: never nest the layout shell (`<div>`, `<aside>`, `<header>`) inside a `'use client'` Providers component — only wrap `{children}` with QueryClientProvider/providers to avoid RSC serialization mismatches in Next.js 15 + React 19.
- Nurse form `POST /cases` payload field is `patient_stub_id` (not `patient_id`); using `patient_id` is a silent wrong field name that won't error at compile time.
- `consensus_level` in case/report data is a `float` (0.0–1.0), not a string label like `'high'`; mock handlers and type stubs must use a number.
- Doctor cases list (`/doctor` route) uses `refetchInterval` to poll every 2 s while any case has `status: 'queued'` or `'running'`; polling stops when all cases reach `'complete'` or `'failed'`.
- Dashboard sidebar is role-isolated: `/` (landing) renders with no sidebar or header at all; `/nurse` sidebar shows only nurse-scoped nav + "Sign Out" back to `/`; `/doctor` (and `/cases/*`) sidebar shows "Active Cases" + "Triage Intake" + "Sign Out" — doctors can reach the triage form directly without signing out. Never mix role nav items.
- `DarkModeToggle` defaults to light mode — no OS `prefers-color-scheme` check; dark mode only activates when `localStorage.theme === 'dark'`. First-time visitors always see light mode.
- Sidebar header is two-tier: Row 1 = logo icon + "Shadi" wordmark left-aligned, role badge (`NURSE`/`DOCTOR` emerald pill) right-aligned; Row 2 = username in muted small type below the wordmark. Never put the username on the same line as the logo.
- `globals.css` must set `html, body { height: 100%; overflow: hidden; }` to lock window-level scroll; without this, the browser window scrolls instead of `<main>` (which has `overflow-y: auto`), causing the entire layout to slide up and expose blank viewport below.
- `AppSidebar` reads session from `localStorage` in a `useEffect` — that effect must include `pathname` in its dependency array so the sidebar re-reads session data on every route change, not just on mount; omitting `pathname` causes the username/role badge to stay blank after a post-login redirect.
- All dashboard API calls must use the `/api/` prefix (e.g. `/api/cases`, `/api/reports/${id}`) and `NEXT_PUBLIC_API_URL` must be empty/unset for same-origin requests; without this MSW never intercepts calls (they go to port 8000 instead of 3001).
