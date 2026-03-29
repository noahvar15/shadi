# Mock EHR (issue #70)

Minimal **FHIR R4** surface for local demos:

- `POST /oauth/token` — `client_credentials` (form body), same shape Shadi’s MCP uses
- `POST /Subscription` / `DELETE /Subscription/{id}` — in-memory only
- `POST /$demo/simulate-arrived-encounter` — builds a triage bundle (`shadi_fhir.triage_bundle`) and POSTs it to Shadi’s `/fhir/notify`
- `GET /health`

## Run

From the repo root:

```bash
python -m tools.mock_ehr
```

Default: `http://127.0.0.1:9001`. Override with `MOCK_EHR_HOST`, `MOCK_EHR_PORT`.

## Pair with Shadi

Point Shadi at the mock FHIR base and token URL (see `.env.example` **Mock EHR (issue #70)**). Example:

| Variable | Example |
|----------|---------|
| `FHIR_BASE_URL` | `http://127.0.0.1:9001` |
| `FHIR_TOKEN_URL` | `http://127.0.0.1:9001/oauth/token` |
| `FHIR_CLIENT_ID` / `FHIR_CLIENT_SECRET` | match `MOCK_EHR_CLIENT_ID` / `MOCK_EHR_CLIENT_SECRET` |
| `NOTIFICATION_ENDPOINT` | public URL of Shadi `POST /fhir/notify` (e.g. `http://127.0.0.1:8000/fhir/notify`) |

Start Shadi with MCP enabled (`fhir_mcp_enabled` — all FHIR + webhook env vars set). On startup, Shadi registers a Subscription against this mock.

## Simulate rest-hook without a real EHR event

With Shadi running:

```bash
curl -sS -X POST "http://127.0.0.1:9001/\$demo/simulate-arrived-encounter" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"demo-p1","triage_text":"Fever and cough x3 days."}'
```

Optional: set `MOCK_EHR_SHADI_WEBHOOK_SECRET` to match Shadi `FHIR_WEBHOOK_SECRET` if your API verifies HMAC on notify.

## Triage bundle shape

Documented in `shadi_fhir/triage_bundle.py`: LOINC **34109-9** observation carries full triage text into `CaseObject.triage_notes_raw`.
