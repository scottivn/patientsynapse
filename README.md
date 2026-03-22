# PatientSynapse

**Intelligent referral processing, DME fulfillment, and revenue cycle management for sleep medicine practices.**

PatientSynapse automates fax-to-EMR data entry with an AI-powered pipeline: OCR → LLM extraction → FHIR patient matching → EMR push. It also manages the full DME/CPAP supply lifecycle from prescription through delivery, referral authorization tracking for HMO patients, and insurance allowable rate lookups.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12), async, Pydantic v2 |
| Frontend | React 18 + Vite + Tailwind CSS |
| Database | SQLite (dev) → PostgreSQL (prod), aiosqlite |
| Auth | JWT in HttpOnly cookies (app auth) + SMART on FHIR OAuth2 (EMR auth) |
| EMR | eClinicalWorks + athenahealth via FHIR R4 (plug-and-play) |
| LLM | Grok (X.AI) default; OpenAI, Anthropic, Ollama, AWS Bedrock hot-swappable |
| OCR | PyPDF2 + pytesseract |
| Deployment | AWS EC2 (t3.small), nginx, Let's Encrypt, systemd |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- API keys for your chosen LLM provider (or `USE_STUB_FHIR=true` + Ollama for fully local dev)

### Installation

```bash
cd patientsynapse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

### Configuration

```bash
cp .env.example .env
```

Key settings in `.env`:
- `EMR_PROVIDER` — `ecw` or `athena`
- `USE_STUB_FHIR=true` — use in-memory FHIR store (no EMR connection needed)
- `LLM_PROVIDER` — `grok`, `openai`, `anthropic`, `ollama`, or `bedrock`
- `ADMIN_DEFAULT_USERNAME` / `ADMIN_DEFAULT_PASSWORD` — seeded on first run
- See `.env.example` for all options

### Running

**Backend** (terminal 1):
```bash
source .venv/bin/activate
uvicorn server.main:app --reload --port 8000
```

**Frontend** (terminal 2):
```bash
cd frontend && npm run dev
```

- API: http://localhost:8000 | Docs: http://localhost:8000/docs
- UI: http://localhost:5173

Default admin login: username and password from `ADMIN_DEFAULT_USERNAME` / `ADMIN_DEFAULT_PASSWORD` in `.env`.

---

## File Structure

```
server/
  main.py                     App entry point, lifespan, middleware
  config.py                   Settings (Pydantic BaseSettings from .env)
  db.py                       Centralized DB schema + async helpers (init_all_tables, db_execute, db_fetch_*)
  api/
    routes.py                 All HTTP endpoints (thin handlers)
  auth/
    smart.py                  SMART on FHIR OAuth2 (EMR auth)
    jwt_auth.py               JWT creation/validation (app auth)
    users.py                  Admin user DB, password hashing
    dependencies.py           FastAPI Depends: require_admin, require_role, require_dev_env
    audit.py                  HIPAA audit logging middleware
  emr/
    base.py                   EMRProvider abstract class
    ecw.py                    eClinicalWorks provider
    athena.py                 athenahealth provider
    __init__.py               Factory: get_emr(), switch_emr()
  fhir/
    client.py                 Async FHIR R4 HTTP client
    resources.py              FHIR resource helpers (Patient, Condition, etc.)
    models.py                 Pydantic FHIR resource models
    stub_client.py            In-memory FHIR store for testing
  llm/
    base.py                   LLMProvider abstract class + standard prompts
    grok.py                   Grok (X.AI) provider
    openai_provider.py        OpenAI provider
    anthropic_provider.py     Anthropic (direct API) provider
    ollama.py                 Ollama (local) provider
    bedrock.py                AWS Bedrock provider (HIPAA-eligible under BAA)
    __init__.py               Factory: get_llm(), switch_llm()
  services/
    referral.py               Referral fax processing pipeline
    fax_ingestion.py          Fax inbox polling + OCR trigger
    prescription_monitor.py   eCW Rx polling → LLM extraction → DME order creation
    ocr.py                    PDF/image text extraction
    dme.py                    DME order lifecycle management
    referral_auth.py          HMO referral authorization tracking
    allowable_rates.py        Insurance allowable rate lookups
frontend/
  src/
    App.jsx                   Routes + AuthProvider wrapper
    services/api.js           Centralized API client (all backend calls)
    contexts/AuthContext.jsx   Session state (user, login, logout)
    components/
      Layout.jsx              Sidebar navigation + outlet
      ProtectedRoute.jsx      Auth guard (redirect to /login)
      ErrorBanner.jsx         Dismissible error display
    pages/
      Login.jsx               Admin login form
      Dashboard.jsx           KPI cards + system status
      FaxInbox.jsx            Fax upload, polling, classification
      Referrals.jsx           Referral document list + filter
      ReferralDetail.jsx      Single referral review + approve/reject
      ReferralAuths.jsx       HMO authorization tracking
      Scheduling.jsx          Provider search + insurance verification
      RCM.jsx                 Revenue cycle dashboard
      Settings.jsx            EMR/LLM provider switcher + OAuth
      DMEOrder.jsx            Patient-facing DME info page (public)
      DMEConfirm.jsx          Patient confirmation via token (public)
      DMEAdmin.jsx            Staff DME pipeline dashboard (protected)
      AllowableRates.jsx      Insurance rate management
      UserManagement.jsx      Admin user CRUD (roles, activate/deactivate)
tests/
  conftest.py                 Shared fixtures (test DB, async client, user factories)
  auth/
    test_rbac.py              Role-based route guard tests
    test_user_management.py   User CRUD endpoint tests
```

---

## Authentication

### App Auth (JWT + RBAC)

JWT tokens in HttpOnly cookies with role-based access control. Flow:

1. `POST /api/admin/login` — verify username + bcrypt hash, set `access_token` (with role claim) + `refresh_token` cookies
2. Every request reads `access_token` cookie via `get_current_user` dependency
3. 15-minute inactivity timeout — `last_activity` claim checked on each request, token refreshed on success
4. `POST /api/admin/refresh` — exchange refresh cookie for new access token (re-reads role from DB)
5. `POST /api/admin/logout` — clear cookies

Production blocks startup if `APP_SECRET_KEY` is the default value.

### Roles

| Role | Landing Page | Access |
|---|---|---|
| `admin` | `/` (Dashboard) | Full access to all features |
| `front_office` | `/faxes` (Fax Inbox) | Faxes, referrals, referral auths, scheduling |
| `dme` | `/dme/admin` (DME Workflow) | DME workflow, prescriptions, allowable rates |

**Route protection:** Backend uses `require_role("admin", "front_office")` or `require_role("admin", "dme")` dependency guards. Frontend uses `ProtectedRoute` with `allowedRoles` prop — unauthorized users are redirected to their role's landing page. Sidebar navigation filters items by role.

### User Management (Admin Only)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/users` | Admin | List all users (no password hashes) |
| POST | `/admin/users` | Admin | Create user (username, password ≥8 chars, role) |
| PUT | `/admin/users/{id}` | Admin | Update role and/or active status (blocks self-deactivation) |
| POST | `/admin/users/{id}/reset-password` | Admin | Reset password (≥8 chars) |
| DELETE | `/admin/users/{id}` | Admin | Delete user (cannot delete yourself) |
| GET | `/admin/roles` | Any auth | List available roles with descriptions |

### EMR Auth (SMART on FHIR)

OAuth2 connection to eCW or Athena:

- `GET /api/auth/login` — get authorization URL for 3-legged OAuth
- `GET /api/auth/callback` — exchange authorization code for access token
- `POST /api/auth/connect-service` — 2-legged client_credentials grant (sandbox/automation)
- `GET /.well-known/jwks.json` — JWKS endpoint for SMART on FHIR

### DME Patient Auth (Token-Gated)

No login — patients access their order via a cryptographically random, time-limited URL token:

- `GET /api/dme/confirm/{token}` — validate token, return patient-safe order data
- `POST /api/dme/confirm/{token}` — submit confirmation (address, fulfillment choice)

Tokens expire after 48 hours.

---

## Database

SQLite in development (`patientsynapse.db`), PostgreSQL planned for production.

### `admin_users`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| username | TEXT UNIQUE | |
| password_hash | TEXT | bcrypt |
| role | TEXT | `admin`, `front_office`, or `dme` (default: `admin`) |
| is_active | INTEGER | 1=active, 0=deactivated (default: 1) |
| created_at | TEXT | datetime('now') |
| last_login | TEXT | Updated on each login |

### `phi_audit_log`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| timestamp | TEXT | datetime('now') |
| user_type | TEXT | admin, anonymous, invalid_token |
| user_id | TEXT | Username or sub claim |
| action | TEXT | e.g. "GET /api/referrals" |
| resource_type | TEXT | referral, fax, dme_order, etc. |
| resource_id | TEXT | Extracted from URL path |
| ip_address | TEXT | |
| user_agent | TEXT | Truncated to 200 chars |

### `allowable_rates`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| payer | TEXT | e.g. "BCBS", "Medicare" |
| payer_plan | TEXT | e.g. "commercial", "medicare_advantage" |
| hcpcs_code | TEXT | e.g. "A7030", "E0601" |
| description | TEXT | |
| supply_months | INTEGER | 3 or 6 |
| allowed_amount | REAL | Dollar amount |
| effective_year | INTEGER | |
| notes | TEXT | |
| created_at | TEXT | |
| updated_at | TEXT | |

Unique constraint on `(payer, payer_plan, hcpcs_code, supply_months, effective_year)`.

### `referrals`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| filename | TEXT | Source fax filename |
| status | TEXT | pending, approved, rejected, pushed, error |
| document_type | TEXT | referral, prior_auth, lab_result, clinical_note, unknown |
| raw_text | TEXT | OCR-extracted text |
| extracted_data | TEXT (JSON) | LLM-structured output |
| patient_id | TEXT | Matched FHIR Patient ID |
| error | TEXT | Error message if failed |
| uploaded_at | TEXT | ISO datetime |

Indexed on `status`.

### `dme_orders`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| status | TEXT | DMEOrderStatus enum value |
| patient_first_name / last_name / dob / phone / id | TEXT | Patient demographics |
| equipment_category / description | TEXT | Equipment info |
| quantity | INTEGER | |
| hcpcs_codes | TEXT (JSON) | Array of HCPCS codes |
| diagnosis_code / description | TEXT | ICD-10 |
| insurance_name / id / type | TEXT | Insurance info |
| insurance_verified | INTEGER | Boolean (0/1) |
| auto_replace | INTEGER | Boolean — triggers resupply cycle |
| confirmation_token | TEXT UNIQUE | Cryptographic token for patient portal |
| documents | TEXT (JSON) | Attached documents array |
| pricing_details | TEXT (JSON) | Bundle pricing from allowable rates |
| ... | ... | 60+ columns covering full DME lifecycle |

Indexed on `status`, `confirmation_token` (unique), `auto_replace`.

### `referral_auths`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| patient_id | TEXT | FHIR Patient reference |
| patient_first_name / last_name | TEXT | |
| insurance_name / type / member_id / npi | TEXT | |
| referral_number | TEXT | PCP referral number |
| referring_pcp_name / npi / phone / fax | TEXT | |
| start_date / end_date | TEXT | Auth validity period |
| visits_allowed / visits_used | INTEGER | Visit tracking |
| status | TEXT | active, expiring_soon, expired, exhausted, pending_renewal, cancelled |
| notes | TEXT | |
| renewal_requested_at | TEXT | |
| created_at / updated_at | TEXT | |

Indexed on `status`, `patient_id`.

### `prescriptions`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | FHIR DocumentReference ID |
| patient_ref | TEXT | FHIR Patient reference |
| date | TEXT | Prescription date |
| description | TEXT | |
| author / author_npi | TEXT | Prescribing physician |
| status | TEXT | detected, extracting, extracted, order_created, failed |
| raw_text | TEXT | Extracted prescription text |
| extracted_data | TEXT (JSON) | LLM-structured output |
| dme_order_id | TEXT | Linked DME order if created |
| error | TEXT | |
| detected_at / processed_at | TEXT | |

Indexed on `status`.

### `fax_processed`

| Column | Type | Notes |
|---|---|---|
| filename | TEXT PK | Fax filename |
| result_id | TEXT | Referral ID or error string |
| processed_at | TEXT | DEFAULT CURRENT_TIMESTAMP |

Tracks which fax files have been ingested to prevent reprocessing.

---

## API Endpoints

All endpoints prefixed with `/api`. Auth column: **Admin** = `require_admin`, **Admin, Front Office** = `require_role("admin", "front_office")`, **Admin, DME** = `require_role("admin", "dme")`, **Public** = no auth, **Dev** = `require_dev_env`.

### Admin Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/admin/login` | Public | Authenticate, set JWT cookies |
| POST | `/admin/refresh` | Public | Refresh access token via refresh cookie |
| POST | `/admin/logout` | Public | Clear auth cookies |
| GET | `/admin/me` | Admin | Return current user info |

### EMR OAuth (SMART on FHIR)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/status` | Admin | Check FHIR OAuth state |
| GET | `/auth/login` | Admin | Get OAuth authorization URL |
| GET | `/auth/callback` | Admin | Handle OAuth callback with auth code |
| POST | `/auth/connect-service` | Admin | 2-legged client_credentials connect |

### Referral Processing

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/referrals/upload` | Admin, Front Office | Upload PDF/image for OCR + LLM extraction |
| POST | `/referrals/upload-text` | Admin, Front Office | Submit raw text for extraction (testing) |
| GET | `/referrals` | Admin, Front Office | List referrals, filter by `?status=` and `?doc_type=` |
| GET | `/referrals/{ref_id}` | Admin, Front Office | Get single referral |
| POST | `/referrals/{ref_id}/approve` | Admin, Front Office | Approve and push to EMR via FHIR |
| POST | `/referrals/{ref_id}/reject` | Admin, Front Office | Reject with optional reason |

### Fax Ingestion

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/faxes/poll` | Admin, Front Office | Scan IncomingFaxes/ dir, OCR + process |
| GET | `/faxes/status` | Admin, Front Office | Current fax inbox state |
| POST | `/faxes/reset` | Admin, Front Office | Reset processed tracking for re-ingestion |

### Prescription Monitor

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/prescriptions/poll` | Admin, DME | Poll eCW FHIR for new Rx documents, extract via LLM, create DME orders |
| GET | `/prescriptions/status` | Admin, DME | Monitor status (polling state, counts by status) |
| GET | `/prescriptions` | Admin, DME | List all detected prescriptions, filter by `?status=` |
| GET | `/prescriptions/{doc_id}` | Admin, DME | Get single prescription detail |
| POST | `/prescriptions/reset` | Admin | Reset monitor — clear tracked prescriptions |

### DME Orders — Staff

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dme/orders` | Admin, DME | List all DME orders, filter by `?status=` |
| GET | `/dme/orders/{order_id}` | Admin, DME | Get single order |
| POST | `/dme/orders/{order_id}/verify-insurance` | Admin, DME | Run FHIR coverage lookup + allowable rate pricing |
| POST | `/dme/orders/{order_id}/approve` | Admin, DME | Approve order |
| POST | `/dme/orders/{order_id}/reject` | Admin, DME | Reject with reason |
| POST | `/dme/orders/{order_id}/fulfill` | Admin, DME | Mark fulfilled, schedule next auto-replace |
| POST | `/dme/orders/{order_id}/hold` | Admin, DME | Place on hold with reason |
| POST | `/dme/orders/{order_id}/resume` | Admin, DME | Resume held order |
| POST | `/dme/orders/{order_id}/send-confirmation` | Admin, DME | Generate patient confirmation token + URL |
| POST | `/dme/orders/{order_id}/mark-ordered` | Admin, DME | Record vendor name + order ID |
| POST | `/dme/orders/{order_id}/mark-shipped` | Admin, DME | Record tracking, carrier, est. delivery |
| POST | `/dme/orders/{order_id}/compliance` | Admin, DME | Update compliance data (AirPM) |
| POST | `/dme/orders/{order_id}/encounter` | Admin, DME | Update encounter tracking |
| POST | `/dme/orders/{order_id}/documents` | Admin, DME | Attach document for insurance approval |
| DELETE | `/dme/orders/{order_id}/documents/{doc_id}` | Admin, DME | Remove document |

### DME Orders — Queues

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dme/orders/incoming` | Admin, DME | New orders needing initial review |
| GET | `/dme/orders/auto-replace-due` | Admin, DME | Fulfilled orders past auto-replace date |
| GET | `/dme/orders/auto-refill-pending` | Admin, DME | Auto-refill orders due or pending |
| GET | `/dme/orders/in-progress` | Admin, DME | Orders being actively worked |
| GET | `/dme/orders/awaiting-patient` | Admin, DME | Sent to patient, no response yet |
| GET | `/dme/orders/patient-confirmed` | Admin, DME | Patient confirmed, ready to order |
| GET | `/dme/orders/on-hold` | Admin, DME | Held orders |
| GET | `/dme/orders/encounter-expired` | Admin, DME | Orders with expired encounters |
| GET | `/dme/dashboard` | Admin, DME | Counts by status + queue sizes |

### DME Orders — Patient (Public)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/dme/orders` | Public | Create DME order (Pydantic-validated input) |
| POST | `/dme/patient-verify` | Public | Verify patient identity (ID + DOB) |
| GET | `/dme/equipment-categories` | Public | List equipment categories, bundles, HCPCS map |
| GET | `/dme/confirm/{token}` | Public | Validate confirmation token, return safe order data |
| POST | `/dme/confirm/{token}` | Public | Submit patient confirmation |

### Referral Authorizations

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/referral-auths` | Admin, Front Office | Create authorization record |
| GET | `/referral-auths` | Admin, Front Office | List auths, filter by `?status=` and `?patient_id=` |
| GET | `/referral-auths/dashboard` | Admin, Front Office | Summary stats |
| GET | `/referral-auths/expiring` | Admin, Front Office | Expiring within `?days=` (default 14) |
| GET | `/referral-auths/{auth_id}` | Admin, Front Office | Get single auth |
| PUT | `/referral-auths/{auth_id}` | Admin, Front Office | Update auth fields |
| POST | `/referral-auths/{auth_id}/record-visit` | Admin, Front Office | Increment visit count |
| POST | `/referral-auths/{auth_id}/request-renewal` | Admin, Front Office | Request PCP renewal |
| GET | `/referral-auths/{auth_id}/renewal-content` | Admin, Front Office | Get fax content for renewal request |
| POST | `/referral-auths/{auth_id}/cancel` | Admin, Front Office | Cancel authorization |

### Scheduling

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/scheduling/providers` | Admin, Front Office | Search providers by `?specialty=` |
| GET | `/scheduling/insurance/{patient_id}` | Admin, Front Office | Verify patient insurance |
| GET | `/scheduling/referral-check/{patient_id}` | Admin, Front Office | Check referral auth for scheduling |

### RCM (Revenue Cycle)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/rcm/dashboard` | Admin | Revenue cycle summary |
| GET | `/rcm/patient/{patient_id}` | Admin | Patient billing context |

### Allowable Rates

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/allowable-rates` | Admin, DME | List rates, filter by `?payer=`, `?hcpcs_code=`, `?year=` |
| GET | `/allowable-rates/payers` | Admin, DME | Distinct payers with counts |
| GET | `/allowable-rates/lookup` | Admin, DME | Single rate lookup |
| POST | `/allowable-rates/bundle-pricing` | Admin, DME | Calculate total for bundle of HCPCS codes |

### Settings

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/settings/emr` | Admin | Current EMR provider info |
| POST | `/settings/emr` | Admin | Hot-swap EMR provider |
| GET | `/settings/llm` | Admin | Current LLM provider |
| POST | `/settings/llm` | Admin | Hot-swap LLM provider |

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/status` | Public | Health check (no PHI) |

---

## Service Layer

### ReferralService (`server/services/referral.py`)

Processes referral faxes through the full pipeline.

| Method | Description |
|---|---|
| `process_fax(text, filename)` | OCR text → LLM extraction → review status |
| `classify_and_process(text, filename)` | Classify document type first, then route (referral gets full extraction, others stored for review) |
| `approve_and_push(ref_id, overrides)` | After human review: patient match/create → conditions → ServiceRequest → notification → complete |
| `list_referrals(status)` | List all referrals, optionally filtered |
| `get_referral(ref_id)` | Get single referral |

### DMEService (`server/services/dme.py`)

Manages DME orders from creation through fulfillment. Sleep-medicine focused (CPAP, BiPAP, masks, supplies).

**Order Lifecycle:** pending → verifying → verified → awaiting_approval → approved → patient_contacted → patient_confirmed → ordering → shipped → fulfilled

**Key Methods:**

| Method | Description |
|---|---|
| `create_order(data)` | Create order with auto-replace scheduling |
| `verify_insurance(order_id)` | FHIR Coverage lookup + allowable rate pricing |
| `approve_order(order_id, notes)` | Staff approves |
| `reject_order(order_id, reason)` | Staff rejects |
| `hold_order(order_id, reason)` | Place on hold |
| `resume_order(order_id)` | Resume held order |
| `generate_confirmation_token(order_id, send_via)` | Generate 48hr token for patient link |
| `validate_confirmation_token(token)` | Look up order by token, check expiry |
| `patient_confirm(token, data)` | Patient confirms address + fulfillment choice |
| `get_patient_safe_order(order)` | Return patient-safe projection (no internal fields) |
| `mark_ordered(order_id, vendor_name, vendor_order_id)` | Record vendor order |
| `mark_shipped(order_id, tracking, carrier, est_delivery)` | Record shipment/pickup-ready |
| `fulfill_order(order_id)` | Mark delivered, schedule next auto-replace |
| `get_auto_replace_due()` | Fulfilled orders past replace date |
| `get_incoming_requests()` | New non-auto-refill orders |
| `get_awaiting_patient()` | Sent to patient, no response |
| `get_patient_confirmed()` | Ready for vendor ordering |
| `get_in_progress()` | Actively being worked |
| `get_on_hold()` | Held orders |
| `get_dashboard()` | Counts by status |
| `update_compliance(order_id, data)` | Update compliance from AirPM |

### PrescriptionMonitorService (`server/services/prescription_monitor.py`)

Polls eCW FHIR for new DME prescriptions (DocumentReference type `57833-6`), extracts structured data via LLM, matches patients, and auto-creates DME orders. Mirrors the fax ingestion pattern.

**Pipeline:** Detect DocumentReference → extract prescription text → LLM `extract_prescription_data()` → match FHIR Patient → create DME order (origin=prescription)

| Method | Description |
|---|---|
| `poll_once()` | Search FHIR for new DocumentReferences since last check |
| `process_detected()` | Run LLM extraction + DME order creation on unprocessed Rx |
| `poll_and_process()` | Combined poll + process (used by the API endpoint) |
| `start_polling(interval)` | Start background polling loop |
| `stop_polling()` | Stop background polling |
| `list_prescriptions(status)` | List detected Rx, optionally filtered |
| `get_prescription(doc_id)` | Get single Rx detail |
| `get_status()` | Monitor status (polling state, counts) |
| `reset()` | Clear tracked prescriptions and checkpoint |

**Prescription States:** `detected` → `extracting` → `extracted` → `order_created` (or `failed` / `skipped`)

### ReferralAuthService (`server/services/referral_auth.py`)

Tracks HMO referral authorizations — visit counts, expiration, PCP renewal requests.

| Method | Description |
|---|---|
| `create_auth(data)` | Create auth record |
| `list_auths(status, patient_id)` | List with optional filters |
| `get_auth(auth_id)` | Get single auth |
| `update_auth(auth_id, data)` | Update fields |
| `record_visit(auth_id)` | Increment visits_used |
| `request_renewal(auth_id)` | Mark as pending renewal |
| `get_renewal_content(auth_id)` | Generate fax content for PCP |
| `cancel_auth(auth_id)` | Cancel authorization |
| `get_expiring_soon(days)` | Auths expiring within N days |
| `get_dashboard()` | Summary stats |
| `check_scheduling_eligibility(patient_id)` | Check if patient has valid auth |

### AllowableRatesService (`server/services/allowable_rates.py`)

Insurance reimbursement rate lookups by payer + HCPCS code. Used during DME order pricing.

| Function | Description |
|---|---|
| `init_rates_table()` | Create DB table on startup |
| `list_rates(payer, hcpcs_code, year)` | Query rates with filters |
| `get_rate(payer, hcpcs_code, supply_months, year)` | Single rate lookup |
| `get_bundle_pricing(payer, codes, supply_months)` | Total reimbursement for bundle |
| `list_payers(year)` | Distinct payers with counts |

---

## Provider Interfaces

### EMR Providers

Configured via `EMR_PROVIDER` env var. Hot-swappable at runtime via `POST /api/settings/emr`.

| Provider | Class | Config |
|---|---|---|
| eClinicalWorks | `ECWProvider` | `ECW_FHIR_BASE_URL`, `ECW_CLIENT_ID`, `ECW_TOKEN_URL`, etc. |
| athenahealth | `AthenaProvider` | `ATHENA_FHIR_BASE_URL`, `ATHENA_CLIENT_ID`, `ATHENA_CLIENT_SECRET`, etc. |

Both implement the `EMRProvider` base class and expose FHIR R4 endpoints. The `StubFHIRClient` (`USE_STUB_FHIR=true`) provides an in-memory FHIR store for testing without EMR credentials.

### LLM Providers

Configured via `LLM_PROVIDER` env var. Hot-swappable at runtime via `POST /api/settings/llm`.

| Provider | Class | Config |
|---|---|---|
| Grok (X.AI) | `GrokProvider` | `XAI_API_KEY`, `XAI_MODEL` |
| OpenAI | `OpenAIProvider` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Anthropic | `AnthropicProvider` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| Ollama | `OllamaProvider` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| AWS Bedrock | `BedrockProvider` | `BEDROCK_MODEL_ID`, `BEDROCK_REGION` (IAM role auth, no API key) |

All implement the `LLMProvider` base class with three standard prompts:

- **`extract_referral_data(text)`** — structured JSON extraction from referral fax OCR text
- **`extract_prescription_data(text)`** — structured JSON extraction from DME prescription documents (patient, prescriber, diagnosis, equipment with HCPCS codes, clinical notes)
- **`classify_document(text)`** — categorize fax as referral, lab_result, insurance_auth, medical_records, or other

Bedrock uses the Anthropic messages format via `invoke_model` API and requires a BAA for HIPAA compliance.

---

## Frontend Pages

### Protected (Role-Gated)

| Route | Page | Roles | Purpose |
|---|---|---|---|
| `/` | Dashboard | admin | KPIs, system status, quick-action cards |
| `/faxes` | FaxInbox | admin, front_office | Upload/poll faxes, view by status + doc type |
| `/faxes/:id` | ReferralDetail | admin, front_office | Review extracted data, approve/reject |
| `/referrals` | Referrals | admin, front_office | Referral-only filtered list |
| `/referrals/:id` | ReferralDetail | admin, front_office | Same detail view |
| `/referral-auths` | ReferralAuths | admin, front_office | HMO auth tracking, visit counts, renewals |
| `/scheduling` | Scheduling | admin, front_office | Provider search, insurance verification |
| `/rcm` | RCM | admin | Revenue cycle dashboard |
| `/settings` | Settings | admin | EMR/LLM provider switcher, OAuth connect |
| `/admin/users` | UserManagement | admin | Create/edit/delete users, assign roles |
| `/dme/admin` | DMEAdmin | admin, dme | Pipeline-based DME workflow (6 queue lanes) |
| `/allowable-rates` | AllowableRates | admin, dme | Insurance rate management |

Users who navigate to a route they don't have access to are redirected to their role's landing page (admin → `/`, front_office → `/faxes`, dme → `/dme/admin`).

### Public (No Login)

| Route | Page | Purpose |
|---|---|---|
| `/login` | Login | Admin login form |
| `/dme` | DMEOrder | Patient-facing DME info page |
| `/dme/confirm/:token` | DMEConfirm | Patient confirmation (address, pickup/ship) |

---

## DME Workflow

Orders originate internally (prescription, auto-refill, staff-initiated, patient request). Patients do not submit orders — they receive a tokenized confirmation link to verify details.

### Statuses

| Status | Description |
|---|---|
| `pending` | Created, needs eligibility checks |
| `verifying` | Insurance/compliance check running |
| `verified` | Eligible, ready for staff review |
| `awaiting_approval` | Staff reviewed, waiting sign-off |
| `approved` | Ready to send confirmation to patient |
| `patient_contacted` | Confirmation link sent, awaiting response |
| `patient_confirmed` | Patient confirmed, ready for vendor order |
| `ordering` | Order placed with vendor |
| `shipped` | Shipped or ready for pickup |
| `fulfilled` | Patient received equipment |
| `rejected` | Denied |
| `on_hold` | Paused |
| `cancelled` | Patient declined or order cancelled |

### Equipment Categories (Sleep Medicine)

CPAP Machine, BiPAP / ASV Machine, CPAP Mask (Full Face / Nasal / Nasal Pillow), Mask Cushion / Pillow Replacement, Headgear, Heated Tubing, Standard Tubing, Water Chamber / Humidifier, Filters (Disposable / Non-Disposable), Chinstrap, CPAP Travel Case, CPAP Cleaning Supplies, Oral Appliance (MAD), Positional Therapy Device, Other Sleep DME.

Each category maps to HCPCS codes for automatic allowable rate lookups. Common supply bundles (Full Resupply, Cushion + Filters, Tubing + Chamber) are predefined.

---

## Security

### HIPAA Controls

- **Audit logging** — `AuditMiddleware` logs all PHI-accessing requests to `phi_audit_log` table
- **No PHI in logs** — patient names, DOB, SSN never logged; IDs only
- **No PHI in error responses** — global exception handler returns generic messages
- **No caching PHI** — `Cache-Control: no-store` on all API responses
- **Session timeout** — 15-minute inactivity timeout via JWT `last_activity` claim
- **TLS** — HSTS in production, TLS 1.3 via nginx + Let's Encrypt
- **Login rate limiting** — IP-based, 5 failed attempts within 5 minutes triggers 429 lockout. Successful login clears the counter.
- **Data persistence** — All business entities (referrals, DME orders, referral auths, prescriptions, fax tracking) persisted to SQLite via `server/db.py`. No in-memory-only stores — server restarts preserve all data.

### Security Headers

Applied via middleware on every response:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'`
- `Strict-Transport-Security` (production only)

### CORS

Allowed origins: `localhost:5173`, `localhost:3000`, `localhost:8443`, `patientsynapse.com`.
Credentials: enabled. Methods: GET, POST, PUT, DELETE, OPTIONS.

---

## Configuration Reference

All settings are loaded from `.env` via Pydantic `BaseSettings` in `server/config.py`.

| Variable | Default | Description |
|---|---|---|
| `EMR_PROVIDER` | `ecw` | EMR backend: `ecw` or `athena` |
| `USE_STUB_FHIR` | `false` | Use in-memory FHIR store |
| `LLM_PROVIDER` | `grok` | LLM backend: `grok`, `openai`, `anthropic`, `ollama`, `bedrock` |
| `XAI_API_KEY` | | Grok API key |
| `XAI_MODEL` | `grok-3` | Grok model |
| `OPENAI_API_KEY` | | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3` | Ollama model |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock inference profile ID |
| `BEDROCK_REGION` | `us-east-1` | AWS region |
| `APP_SECRET_KEY` | `change-me-in-production` | JWT signing key (must change for prod) |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8443` | Bind port |
| `APP_ENV` | `development` | `development`, `staging`, `production` |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ADMIN_DEFAULT_USERNAME` | `admin` | Default admin username |
| `ADMIN_DEFAULT_PASSWORD` | | Default admin password (required for seed) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `SESSION_INACTIVITY_TIMEOUT_MINUTES` | `15` | Inactivity timeout |
| `FAX_UPLOAD_DIR` | `./uploads` | Upload directory |
| `DATABASE_URL` | `sqlite:///./patientsynapse.db` | Database connection string |

EMR-specific variables (eCW, Athena) are documented in `.env.example`.

---

## Testing

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests use an isolated SQLite database (temp file), `USE_STUB_FHIR=true`, and `httpx.AsyncClient` with `ASGITransport` — no running server needed.

### Test Coverage

| Suite | File | Tests |
|---|---|---|
| RBAC Route Guards | `tests/auth/test_rbac.py` | Admin-only routes block front_office + DME, front office routes allow admin + front_office but block DME, DME routes allow admin + DME but block front_office, unauthenticated rejected, deactivated user rejected, login returns correct role for all 3 roles, `/admin/me` returns correct role |
| User Management | `tests/auth/test_user_management.py` | CRUD lifecycle, duplicate username, short password, invalid role, self-deactivation blocked, reset password, DME blocked from admin endpoints |
| Security Hardening | `tests/auth/test_security.py` | Login rate limiting (429 after 5 failures, reset on success), SMART OAuth routes require admin (401 unauth, 403 non-admin), CSP + security headers present, DME order Pydantic validation (missing fields → 422, empty name → 422, bad quantity → 422, valid input accepted) |
| DME Order Lifecycle | `tests/services/test_dme.py` | Create order, list/get/filter orders, approve, reject (with reason), hold/resume, full fulfillment flow (approve→ordered→shipped→fulfilled), confirmation token generation + public validation + patient submission, insurance verification, encounter tracking, compliance updates, document add/remove, dashboard stats, queue endpoints (8 filter views), status filter, encounter types + equipment categories endpoints |
| Referral Authorizations | `tests/services/test_referral_auth.py` | Create auth, list/get/filter auths, update fields, record visit (count tracking), visits-exhausted status, expired/expiring-soon status computation, request renewal + renewal content, cancel auth, dashboard stats, expiring-soon endpoint, scheduling eligibility (with/without active auth) |
| System & Rates | `tests/services/test_system_and_rates.py` | System status, EMR/LLM config endpoints, settings require admin, logout, provider search (with specialty filter), insurance verification stub, RCM dashboard + patient billing, allowable rates CRUD (create, lookup, delete, bundle pricing, list payers, 404 on missing), prescription/fax status endpoints, DME patient verify stub |

---

## Deployment

- **Instance:** AWS EC2 in us-east-1 (see AWS Console for instance ID and Elastic IP)
- **Domain:** `patientsynapse.com` (Route53)
- **Deploy script:** `bash scripts/deploy.sh`
- **Start instance:** `aws ec2 start-instances --instance-ids <instance-id> --region us-east-1`
- **IAM role:** EC2 instance role with `AmazonBedrockFullAccess` for HIPAA-eligible LLM access
