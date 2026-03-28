---
name: find-skills
description: Shared workflow for discovering and installing agent skills from the Vercel Skills ecosystem.
source: https://skills.sh/vercel-labs/skills/find-skills
---

# Find Skills

Use this skill when the user asks for a skill, wants to extend agent capabilities, or would benefit from an existing workflow instead of custom instructions.

## Preferred Source

- Start with the Vercel Skills ecosystem at `https://skills.sh/`.
- Prefer established publishers such as `vercel-labs`, `anthropics`, or `microsoft`.
- For this repo, treat this tracked file as the shared source of truth rather than user-home installs.

## Install Commands

Install the upstream Vercel skill:

```bash
npx skills add https://github.com/vercel-labs/skills --skill find-skills
```

Install a discovered skill collection:

```bash
npx skills add <owner/repo-or-url> --skill <skill-name>
```

If the CLI is available locally, you can also search directly:

```bash
npx skills find <query>
```

## Workflow

1. Identify the domain and concrete task.
2. Check `https://skills.sh/` for an existing skill before proposing custom work.
3. Prefer skills with meaningful install volume and a reputable source.
4. Give the user the skill name, what it does, the install command, and the skills.sh link.
5. If nothing relevant exists, say so briefly and continue with direct help.

## What to Present

When recommending a skill, include:

- Skill name
- Publisher
- Why it matches the task
- Install command
- Direct `skills.sh` URL

## Common Queries

- React / Next.js: `react`, `nextjs`, `frontend`
- Testing: `jest`, `playwright`, `e2e`
- Reviews: `code review`, `pr review`
- Docs: `readme`, `changelog`, `api docs`
- DevOps: `docker`, `deploy`, `ci-cd`

## Notes

- `npx` is required for the standard install flow.
- Review third-party skills before installing them.
- Keep repo-shared skills in `skills/` so every agent sees the same instructions.
