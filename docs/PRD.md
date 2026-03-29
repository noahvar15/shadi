# Product requirements (Shadi)

Checkboxes below are updated **automatically** when a PR merges to `main` **if** the PR description includes a line like:

```text
PRD: FE-001, API-002
```

Use comma- or space-separated IDs. IDs must match the `<!-- prd:... -->` markers on each line.

---

## Dashboard — nurse & doctor UX

- [ ] <!-- prd:FE-001 --> Landing page: choose nurse vs doctor
- [ ] <!-- prd:FE-002 --> Nurse: triage notes form and submit
- [ ] <!-- prd:FE-003 --> Doctor: live pipeline / agent progress while case runs
- [ ] <!-- prd:FE-004 --> Doctor: differential report view (when complete)

## Platform / API

- [ ] <!-- prd:API-001 --> `POST /cases` intake stable for dashboard
- [ ] <!-- prd:API-002 --> `GET /reports/{id}` status + report for polling

## FHIR / EHR integration

- [ ] <!-- prd:FHIR-001 --> Mock EHR + subscription demo path
- [ ] <!-- prd:FHIR-002 --> Triage → valid FHIR bundle for pipeline

---

*Maintained by `.github/workflows/prd-sync.yml` — do not hand-edit `[x]` without merging a PR that lists the corresponding `PRD:` IDs (or edit and list IDs in a follow-up PR).*
