# Shadi — Agent Guide

Multi-agent clinical diagnostic reasoning system for emergency medicine. Reads patient data via FHIR R4, runs **four** specialist agents over a shared **Meditron** model on Ollama (`MEDITRON_MODEL`, default `meditron:70b`; domain-specific prompts per ADR-004), plus separate agents for intake, optional imaging, evidence, orchestrator synthesis, and safety veto — producing a ranked differential diagnosis before the physician walks in. Optional vLLM+LoRA exists as a Compose profile only (ADR-003).

**Wiring note:** `POST /cases` builds `CaseObject` from a FHIR bundle via the normalizer, not via `IntakeAgent`. `Orchestrator.run()` runs intake → imaging → specialists → evidence → debate → synthesis → safety veto. Both `IntakeAgent` and `ImageAnalysisAgent` are wired in `orchestrator.py`. Root [`config.py`](config.py) sets **`MOCK_LLM`** (default `true`).

---

## Architecture at a Glance

**Inference split (ADR-002, ADR-004):** Ollama serves **all** agent chat and embeddings, including **`MEDITRON_MODEL`** for the four specialists and evidence claim evaluation. Intake (Qwen), imaging (MedGemma), safety (Phi), and orchestrator synthesis (DeepSeek-R1) are also on Ollama. Optional **vLLM + LoRA** is a Compose **`vllm-lora`** profile for experiments — default agents do not call it. No cloud APIs — PHI stays on the machine.

```
EHR → FHIR MCP Server → Intake Agent → CaseObject
                          │    │
                          │    └──→ Imaging Agent (MedGemma, only if attachments)
                          ↓
          Four specialists: Cardiology / Neurology / Pulmonology / Toxicology (parallel, Ollama Meditron)
                          ↓
                    Evidence Grounding Agent
                          ↓
                       A2A Debate Round
                          ↓
               Orchestrator (synthesis) → Safety Veto
                          ↓
              DiagnosticReport (FHIR) + Dashboard
```

Specialists share **Meditron** via Ollama (`MEDITRON_MODEL`, default `meditron:70b`); differentiation is by prompt and domain metadata, not separate weight loads. The imaging agent is multimodal (MedGemma on Ollama), not a fifth specialist adapter. Optional per-domain LoRA on vLLM is profile-only (ADR-003).

---

## Repository Layout

```
agents/
  base.py            # BaseAgent ABC — all agents inherit this
  intake/            # IntakeAgent (Qwen) — wired as Stage 0 in Orchestrator.run()
  specialists/       # Four LoRA domains + image_agent.py (MedGemma — not LoRA)
  evidence/          # PubMed + guidelines cross-reference
  safety/            # Safety veto (contraindications, allergies, meds)
  orchestrator/      # Fan-out, A2A debate, consensus synthesis
shadi_fhir/          # FHIR R4 normalizer (`fhir.resources` is the HL7 lib — avoid a top-level `fhir` pkg)
a2a/                 # A2A protocol schema + ENDORSE/CHALLENGE/MODIFY logic
api/                 # FastAPI app (routes, schemas, middleware; POST /fhir/notify)
tasks/               # arq worker + diagnostic pipeline job
tools/mock_ehr/      # Local mock EHR (OAuth + Subscription + rest-hook demos)
dashboard/           # Next.js physician dashboard (bun)
docs/decisions/      # Architecture Decision Records — read before changing arch
tests/
  fixtures/          # Bundles and JSON fixtures for tests
  unit/
skills/              # Primary copy of shared skills (see Skills section)
.agents/skills/      # Extended mirror (e.g. browser-automation); same SKILL.md layout
config.py            # MOCK_LLM, OLLAMA_BASE_URL, VLLM_BASE_URL for agents
docker-compose.yml   # vLLM LoRA modules, Ollama, api, worker, postgres, redis
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Python runtime | 3.11+ |
| Web framework | FastAPI + Uvicorn |
| Inference | Ollama (default agents); optional vLLM 0.6+ + LoRA (`vllm-lora` profile) |
| Models | Shared `MEDITRON_MODEL` on Ollama for four specialists; other Ollama tags per ADR-002 / ADR-004 |
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

**Layout:** The **canonical** checked-in skills used with Vercel `find-skills` live under **`skills/`** (each skill is a folder with `SKILL.md`). **`skills-lock.json`** pins hashes for a subset of upstream sources (see that file for which). **`.agents/skills/`** mirrors the same layout and adds a few extra skills (for example `browser-automation`) that are not duplicated under `skills/`. Prefer reading `SKILL.md` from `skills/<name>/` when both exist.

Only list skills in the table below if they are tracked in this repository. Do not point agents at user-home-only skills or editor-specific symlink farms.

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
4. Each specialist’s **prompts and domain metadata** must match the clinical specialty; weights are shared (`MEDITRON_MODEL`) unless a future ADR reintroduces per-domain adapters.

---

## Learned User Preferences

- Always use `bunx` instead of `npx` for all CLI tools in this project (e.g. `bunx skills add`, not `npx skills add`).
- Each GitHub issue gets its own branch and a separate PR; never bundle multiple issues into one branch. Worktrees are not used for normal feature work — only create one if the user explicitly requests isolation.

---

## Learned Workspace Facts

- Subagent model routing: `planner` → `claude-4.6-sonnet-medium-thinking` (strategic decomposition); `worker` → `gpt-5.4-medium` (Python agents, FHIR, A2A, API, models, infra — never `dashboard/`); `ui-engineer` → `claude-sonnet-4-6` (all work inside `dashboard/` exclusively); `reviewer` → `claude-opus-4-6` (verification and code review).
- Project-level skills for team sharing live in `.agents/skills/` (committed to git). `.cursor/` is gitignored. `.claude/skills/` is not used — the team does not use Claude.
- Dashboard design system (defined in `tailwind.config.ts` on the scaffold branch, inherited by all downstream issues): Vercel/Linear aesthetic; Tailwind `darkMode: 'class'`; light mode uses "Sage Whisper" palette (`--background: #F4F7F4`, `--surface: #FAFCFA`, `--border: #DCE6DB`, `--foreground: #161E15`, `--foreground-muted: #5B7258`) — green-family tokens chosen for harmony with the emerald accent; dark mode base slate-950; emerald-400/500 primary accent (high confidence, CTAs); red-500/600 safety veto/danger; amber-400/500 warnings/divergent agents; monospace for clinical scores and numbers, sans-serif for prose.
- Dashboard routing (established in issue #69, which superseded #42/#43/#44): `/` = role-selection landing (Nurse vs Doctor); `/nurse` = triage intake form (chief complaint → `POST /cases/intake`); `/doctor` = cases list with report cards and live agent progress; `/doctor/notifications` = activity feed; `/cases/:id/triage` = formatted triage document. Header search is role-differentiated: doctor header searches cases (navigates to `/cases/:id/triage`); nurse header searches patients via `/api/patients/search` and autofills the form via URL params (`patient_id`, `patient_name`, `dob`).
- Next.js hydration rule: never nest the layout shell (`<div>`, `<aside>`, `<header>`) inside a `'use client'` Providers component — only wrap `{children}` with QueryClientProvider/providers to avoid RSC serialization mismatches in Next.js 15 + React 19.
- Nurse form `POST /cases/intake` payload fields: `chief_complaint`, `patient_name`, `patient_stub_id` (not `patient_id`); using `patient_id` is a silent wrong field name that won't error at compile time.
- `consensus_level` in case/report data is a `float` (0.0–1.0), not a string label like `'high'`; mock handlers and type stubs must use a number.
- Doctor cases list (`/doctor` route) uses `refetchInterval` to poll every 2 s while any case has `status: 'queued'` or `'running'`; polling stops when all cases reach `'complete'` or `'failed'`.
- Dashboard sidebar is role-isolated: `/` (landing) renders with no sidebar or header at all; `/nurse` sidebar shows only nurse-scoped nav + "Sign Out" back to `/`; `/doctor` (and `/cases/*`) sidebar shows "Active Cases", "Activity" (→ `/doctor/notifications`), a "Patients" section with per-patient triage links (→ `/cases/:id/triage`), and "Sign Out". No "Triage Intake" link in doctor sidebar. Never mix role nav items.
- `DarkModeToggle` defaults to light mode — no OS `prefers-color-scheme` check; dark mode only activates when `localStorage.theme === 'dark'`. First-time visitors always see light mode.
- Sidebar header is two-tier: Row 1 = logo icon + "Shadi" wordmark left-aligned, role badge (`NURSE`/`DOCTOR` emerald pill) right-aligned; Row 2 = username in muted small type below the wordmark. Never put the username on the same line as the logo.
- `globals.css` must set `html, body { height: 100%; overflow: hidden; }` to lock window-level scroll; without this, the browser window scrolls instead of `<main>` (which has `overflow-y: auto`), causing the entire layout to slide up and expose blank viewport below.
- `AppSidebar` reads session from `localStorage` in a `useEffect` — that effect must include `pathname` in its dependency array so the sidebar re-reads session data on every route change, not just on mount; omitting `pathname` causes the username/role badge to stay blank after a post-login redirect.
- All dashboard API calls use the `/api/` prefix; the axios client uses same-origin by default. `dashboard/next.config.ts` rewrites `/api/:path* → ${API_URL}/:path*` (server-only env var, default `http://localhost:8000`). `NEXT_PUBLIC_MOCK_API=true` in `.env.local` activates MSW mock mode (in-memory, does not survive page reloads); set it to `false` for real FastAPI. `NEXT_PUBLIC_API_URL` must **never** be set at runtime — it exists only in `vitest.config.ts` for MSW test interception.
- MSW race condition guard: `AppSidebar` and `AppHeader` render outside `<Providers>` and fire fetches before MSW's service worker finishes registering. Any `useEffect` fetch in these components must delay ~300 ms and guard `setState` with `Array.isArray()`; without the delay early requests bypass MSW, return HTML/error strings, and crash `.map()`.
- Dashboard test framework: Vitest (`bun run test`); config in `dashboard/vitest.config.ts` sets `NEXT_PUBLIC_API_URL=http://localhost` (test-only, gives axios a base for MSW Node interception); test files live in `dashboard/src/__tests__/`.
- Backend routes in `api/routes/cases.py`: `GET /cases` (list with patient_name + chief_complaint), `GET /cases/:id` (detail), `POST /cases/intake` (NurseIntakePayload — no FHIR required; accepts chief_complaint, patient_name, patient_stub_id), `POST /cases/:id/feedback` (vote: `"up" | "down" | null` — toggleable, null clears the vote). `api/routes/patients.py`: `GET /patients/search?name=<query>` (up to 10 results; `SHADI_STUB_PATIENT_SEARCH=1` for stub mode).
