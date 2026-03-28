#!/usr/bin/env bash
# Create stacked PRs for API issues #31–#34 (merge #31 first, then retarget/rebase as needed).
# Prerequisites: branches pushed to origin; run `gh auth login` or export GH_TOKEN.
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-noahvar15/shadi}"
GH_BIN="${GH_BIN:-gh}"

if ! command -v "$GH_BIN" &>/dev/null; then
  echo "Install GitHub CLI: brew install gh" >&2
  exit 1
fi

if [[ -z "${GH_TOKEN:-}" ]] && ! "$GH_BIN" auth status &>/dev/null 2>&1; then
  echo "Authenticate first:" >&2
  echo "  gh auth login" >&2
  echo "or:" >&2
  echo "  export GH_TOKEN=<personal access token with repo scope>" >&2
  echo >&2
  echo "Or open these compare links (logged into GitHub in your browser) to open each PR form:" >&2
  owner="${REPO%%/*}"
  repo="${REPO#*/}"
  base_url="https://github.com/${owner}/${repo}/compare"
  echo "  #31  ${base_url}/main...issue/31-api-lifespan-settings?expand=1" >&2
  echo "  #32  ${base_url}/issue/31-api-lifespan-settings...issue/32-post-cases-intake?expand=1" >&2
  echo "  #33  ${base_url}/issue/32-post-cases-intake...issue/33-reports-pipeline-stub?expand=1" >&2
  echo "  #34  ${base_url}/issue/33-reports-pipeline-stub...issue/34-arq-worker-and-tests?expand=1" >&2
  exit 1
fi

create_pr() {
  local base="$1" head="$2" title="$3" body="$4"
  echo "Creating PR: $head -> $base"
  "$GH_BIN" pr create --repo "$REPO" --base "$base" --head "$head" --title "$title" --body "$body"
}

create_pr main issue/31-api-lifespan-settings \
  "feat(api): Settings, DB pool, Redis/arq lifespan (#31)" \
"## Summary
- \`api/config.py\`: \`Settings\` (DATABASE_URL, REDIS_URL, VLLM/OLLAMA URLs, INTAKE_QUEUE).
- \`api/db.py\`: asyncpg pool + \`cases\` table schema.
- \`api/main.py\`: lifespan opens/closes pool and arq Redis pool on \`app.state\`.

## Track
Backend platform / Emmanuel — see [docs/cross-track-dependencies.md](https://github.com/${REPO}/blob/main/docs/cross-track-dependencies.md).

## Tests
\`tests/unit/test_api_issue_31.py\` + \`./scripts/verify_api_branch_tests.sh\`"

create_pr issue/31-api-lifespan-settings issue/32-post-cases-intake \
  "feat(api): POST /cases intake, stub flag, arq enqueue (#32)" \
"## Summary
- \`POST /cases\` → \`{ case_id, status: \"queued\" }\`.
- Persists case row; enqueues \`tasks.pipeline.run_diagnostic_pipeline\`.
- \`SHADI_STUB_CASE_INTAKE\` for DEP-1 (see cross-track doc).

## Depends on
Merge **#31** first (or set PR base to \`main\` after #31 lands and rebase).

## Tests
\`tests/unit/test_api_issue_32.py\`"

create_pr issue/32-post-cases-intake issue/33-reports-pipeline-stub \
  "feat(api): report routes + diagnostic pipeline stub (#33)" \
"## Summary
- \`GET /reports/{case_id}\`, \`GET /reports/{case_id}/status\`.
- \`tasks/pipeline.py\`: \`run_diagnostic_pipeline\` with orchestrator + fixture fallback (DEP-2).
- \`tests/fixtures/sample_report.json\`.

## Depends on
**#32** (stacked) or rebase onto \`main\` after prior merges.

## Tests
\`tests/unit/test_api_issue_33.py\`"

create_pr issue/33-reports-pipeline-stub issue/34-arq-worker-and-tests \
  "feat(api): arq worker, Dockerfile.api, compose worker, API tests (#34)" \
"## Summary
- \`tasks/worker.WorkerSettings\` — \`arq tasks.worker.WorkerSettings\`.
- \`docker-compose\` \`worker\` service; \`Dockerfile.api\`; \`INTAKE_QUEUE\` in \`.env.example\`.
- \`tests/unit/test_api_issue_34.py\`, \`test_api_routes.py\`, \`scripts/verify_api_branch_tests.sh\`.

## Depends on
**#33** (stacked) or rebase onto \`main\` after prior merges.

## Tests
Full \`pytest tests/\` on branch tip."

echo "Done. Open PRs: gh pr list --repo $REPO"
