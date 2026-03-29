# Shadi — Product Requirements

<!-- One checkbox per requirement. Format: - [x] Outcome title <!-- prd:ID --> -->

Progress is tracked per owner. Check boxes are synced automatically by Cursor Automation when PRs declare `PRD: <ID>` in their body.

---

## Frontend (Ericsen) — FE-*

- [x] PR template updated to reference Cursor Automation for PRD sync <!-- prd:FE-001 -->
- [x] Role-selection landing page with Nurse and Doctor chooser cards <!-- prd:nurse-role-selection -->
- [x] Nurse triage intake form with chief-complaint validation and case submission <!-- prd:nurse-triage-form -->
- [x] Doctor cases view with live status badges and New Case navigation <!-- prd:doctor-cases-view -->
- [x] Cases breadcrumb on report page linking back to doctor view <!-- prd:doctor-breadcrumb -->

---

## FHIR bundle & EHR integration (Noah) — FHIR-*

- [x] FHIR R4 normalizer converts Bundles to CaseObject <!-- prd:FHIR-001 -->
- [x] Triage bundle builder creates valid FHIR Bundles from nurse text <!-- prd:FHIR-002 -->
- [x] MCP server with OAuth token management and subscription lifecycle <!-- prd:FHIR-003 -->
- [x] Webhook HMAC verification for inbound FHIR Subscription notifications <!-- prd:FHIR-004 -->
- [x] Mock EHR server for local OAuth + Subscription + rest-hook demos <!-- prd:FHIR-005 -->

---

## Backend / API platform (Manny) — API-*

- [x] Database schema with cases table, status lifecycle, and pipeline_step tracking <!-- prd:API-001 -->
- [x] POST /cases/intake nurse triage route with FHIR normalization <!-- prd:API-002 -->
- [x] GET /reports/:id status-aware report endpoint with pipeline step <!-- prd:API-003 -->
- [x] POST /cases/:id/feedback doctor thumbs-up/down with toggle support <!-- prd:API-004 -->
- [x] arq worker with run_diagnostic_pipeline job and error recovery <!-- prd:API-005 -->
- [x] Configurable CORS origins via CORS_ORIGINS env var <!-- prd:API-006 -->

---

## Agents & orchestration (Josh) — AGENT-*

- [x] Four Meditron specialist agents with domain-specific prompts (ADR-004) <!-- prd:AGENT-001 -->
- [x] Evidence grounding agent with embedding retrieval and claim evaluation <!-- prd:AGENT-002 -->
- [x] A2A debate protocol with ENDORSE/CHALLENGE/MODIFY messages <!-- prd:AGENT-003 -->
- [x] Orchestrator synthesis producing ranked differential diagnosis <!-- prd:AGENT-004 -->
- [x] Safety veto agent with fail-closed parsing (phi4:14b) <!-- prd:AGENT-005 -->
- [x] IntakeAgent wired into pipeline for SNOMED/LOINC/RxNorm extraction <!-- prd:AGENT-006 -->
- [x] ImageAnalysisAgent wired into pipeline for multimodal imaging <!-- prd:AGENT-007 -->
- [x] Evidence grounding results fed into debate and synthesis stages <!-- prd:AGENT-008 -->
