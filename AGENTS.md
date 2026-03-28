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
- Dashboard design system (defined in `tailwind.config.ts` on the scaffold branch, inherited by all downstream issues): Vercel/Linear aesthetic; Tailwind `darkMode: 'class'`; slate-950/white base; emerald-400/500 primary accent (high confidence, CTAs); red-500/600 safety veto/danger; amber-400/500 warnings/divergent agents; monospace for clinical scores and numbers, sans-serif for prose.
- Dashboard issue dependency order: #41 (scaffold) must merge before #42 (case intake) and #43 (report view); #43 must merge before #44 (live updates).
