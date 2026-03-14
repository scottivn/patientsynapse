# PatientSynapse — Complete Codebase Reference

> **Version:** 0.1.0  
> **Generated:** 2026-03-14  
> **Stack:** FastAPI (Python 3.12) + React 18 + Vite + Tailwind CSS  
> **Purpose:** Intelligent referral processing, smart scheduling, and revenue cycle management for medical practices  

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Directory Structure](#directory-structure)
- [Root Files](#root-files)
  - [requirements.txt](#requirementstxt)
  - [.env.example / .env](#envexample--env)
  - [.gitignore](#gitignore)
- [Backend — `server/`](#backend--server)
  - [server/config.py — Configuration](#serverconfigpy--configuration)
  - [server/main.py — Application Entry Point](#servermainpy--application-entry-point)
  - [server/emr/ — EMR Abstraction Layer](#serveremr--emr-abstraction-layer)
    - [server/emr/base.py — Abstract Base + AuthMethod Enum](#serveremrbasepy--abstract-base--authmethod-enum)
    - [server/emr/ecw.py — eClinicalWorks Provider](#serveremrecwpy--eclinicalworks-provider)
    - [server/emr/athena.py — athenahealth Provider](#serveremrathenapy--athenahealth-provider)
    - [server/emr/\_\_init\_\_.py — EMR Factory](#serveremr__init__py--emr-factory)
  - [server/auth/ — SMART on FHIR OAuth2](#serverauth--smart-on-fhir-oauth2)
    - [server/auth/smart.py — SMARTAuth Class](#serverauthsmartpy--smartauth-class)
  - [server/fhir/ — FHIR R4 Client & Models](#serverfhir--fhir-r4-client--models)
    - [server/fhir/models.py — Pydantic FHIR Resource Models](#serverfhirmodelspy--pydantic-fhir-resource-models)
    - [server/fhir/client.py — Async HTTP Client](#serverfhirclientpy--async-http-client)
    - [server/fhir/resources.py — High-Level Resource Operations](#serverfhirresourcespy--high-level-resource-operations)
  - [server/llm/ — LLM Abstraction Layer](#serverllm--llm-abstraction-layer)
    - [server/llm/base.py — Abstract Base + Prompts](#serverllmbasepy--abstract-base--prompts)
    - [server/llm/grok.py — Grok (X.AI) Provider](#serverllmgrokpy--grok-xai-provider)
    - [server/llm/openai_provider.py — OpenAI Provider](#serverllmopenai_providerpy--openai-provider)
    - [server/llm/anthropic_provider.py — Anthropic Provider](#serverllmanthropic_providerpy--anthropic-provider)
    - [server/llm/ollama.py — Ollama Local Provider](#serverllmollamapy--ollama-local-provider)
    - [server/llm/\_\_init\_\_.py — LLM Factory](#serverllm__init__py--llm-factory)
  - [server/services/ — Business Logic Services](#serverservices--business-logic-services)
    - [server/services/ocr.py — OCR Text Extraction](#serverservicesocrpy--ocr-text-extraction)
    - [server/services/referral.py — Referral Processing Pipeline](#serverservicesreferralpy--referral-processing-pipeline)
    - [server/services/scheduling.py — Smart Scheduling](#serverservicesschedulingpy--smart-scheduling)
    - [server/services/rcm.py — Revenue Cycle Management](#serverservicesrcmpy--revenue-cycle-management)
  - [server/mcp/ — MCP Server (AI Agent Tools)](#servermcp--mcp-server-ai-agent-tools)
    - [server/mcp/server.py — FastMCP Tool Definitions](#servermcpserverpy--fastmcp-tool-definitions)
  - [server/api/ — REST API Routes](#serverapi--rest-api-routes)
    - [server/api/routes.py — All HTTP Endpoints](#serverapiroutespy--all-http-endpoints)
- [Frontend — `frontend/`](#frontend--frontend)
  - [Build Tooling](#build-tooling)
    - [package.json](#packagejson)
    - [vite.config.js](#viteconfigjs)
    - [tailwind.config.js](#tailwindconfigjs)
    - [postcss.config.js](#postcssconfigjs)
    - [index.html](#indexhtml)
  - [Source — `frontend/src/`](#source--frontendsrc)
    - [main.jsx — React Entry Point](#mainjsx--react-entry-point)
    - [App.jsx — Router / Page Layout](#appjsx--router--page-layout)
    - [index.css — Global Styles (Tailwind)](#indexcss--global-styles-tailwind)
    - [services/api.js — API Client](#servicesapijs--api-client)
    - [components/Layout.jsx — Shell (Sidebar + Content)](#componentslayoutjsx--shell-sidebar--content)
    - [components/FileUpload.jsx — Drag-and-Drop Upload](#componentsfileuploadjsx--drag-and-drop-upload)
    - [components/StatCard.jsx — Dashboard Stat Widget](#componentsstatcardjsx--dashboard-stat-widget)
    - [components/StatusBadge.jsx — Referral Status Badge](#componentsstatusbadgejsx--referral-status-badge)
    - [pages/Dashboard.jsx — Main Dashboard](#pagesdashboardjsx--main-dashboard)
    - [pages/Referrals.jsx — Referral Inbox](#pagesreferralsjsx--referral-inbox)
    - [pages/ReferralDetail.jsx — Single Referral View](#pagesreferraldetailjsx--single-referral-view)
    - [pages/Scheduling.jsx — Smart Scheduling](#pagesschedulingjsx--smart-scheduling)
    - [pages/RCM.jsx — Revenue Cycle Management](#pagesrcmjsx--revenue-cycle-management)
    - [pages/Settings.jsx — Configuration & Status](#pagessettingsjsx--configuration--status)
- [Assets — `assets/`](#assets--assets)
- [Data Flow Diagrams](#data-flow-diagrams)
  - [Referral Processing Pipeline](#referral-processing-pipeline-1)
  - [OAuth2 Authentication Flow](#oauth2-authentication-flow)
- [API Endpoint Reference](#api-endpoint-reference)
- [Environment Variables Reference](#environment-variables-reference)
- [How to Run](#how-to-run)

---

## Architecture Overview

PatientSynapse is a **layered monorepo** with a Python backend and React frontend:

```
┌──────────────────────────────────────────────────────────┐
│                 React 18 + Vite + Tailwind               │  Port 5173 (dev)
│   Dashboard │ Referrals │ Scheduling │ RCM │ Settings    │
├──────────────────────────────────────────────────────────┤
│                   /api proxy (Vite dev)                   │
├──────────────────────────────────────────────────────────┤
│                  FastAPI REST API                         │  Port 8443
│          /api/auth  /api/referrals  /api/rcm  etc.       │
├──────────────────────────────────────────────────────────┤
│  EMR Abstraction    │  LLM Abstraction    │  MCP Server  │
│  (eCW, Athena)      │  (Grok,OpenAI,...)  │  (FastMCP)   │
├──────────────────────────────────────────────────────────┤
│  SMART on FHIR Auth │  FHIR R4 Client     │  OCR Service │
├──────────────────────────────────────────────────────────┤
│  Business Services: Referral │ Scheduling │ RCM          │
└──────────────────────────────────────────────────────────┘
          ↓                    ↓                  ↓
   EMR FHIR API         LLM API (X.AI)     Fax PDFs/Images
```

**Key design principles:**
- **Plug-and-play EMR**: Switch between eClinicalWorks and athenahealth via `EMR_PROVIDER` env var
- **Plug-and-play LLM**: Switch between Grok, OpenAI, Anthropic, Ollama via `LLM_PROVIDER` env var
- **EMR-agnostic core**: All business logic talks FHIR R4 — EMR specifics are isolated in `server/emr/`
- **MCP-ready**: AI agents (Claude, etc.) can call PatientSynapse tools via the MCP server

---

## Directory Structure

```
patient_bridge/
├── .env                          # Local secrets (gitignored)
├── .env.example                  # Template for .env
├── .gitignore                    # Git ignore rules
├── requirements.txt              # Python dependencies
├── README.md                     # Project readme
├── assets/
│   └── logos/
│       ├── logo.svg              # Full logo
│       ├── logo-icon.svg         # Icon only
│       └── logo-banner.svg       # Banner (185×35)
├── server/                       # Python backend
│   ├── __init__.py               # (empty)
│   ├── config.py                 # Centralized settings
│   ├── main.py                   # FastAPI app entry point
│   ├── auth/
│   │   ├── __init__.py           # (empty)
│   │   └── smart.py              # SMART on FHIR OAuth2
│   ├── emr/
│   │   ├── __init__.py           # EMR factory (get_emr)
│   │   ├── base.py               # Abstract EMRProvider + AuthMethod enum
│   │   ├── ecw.py                # eClinicalWorks implementation
│   │   └── athena.py             # athenahealth implementation
│   ├── fhir/
│   │   ├── __init__.py           # (empty)
│   │   ├── models.py             # Pydantic FHIR R4 resource models
│   │   ├── client.py             # Async FHIR HTTP client
│   │   └── resources.py          # High-level FHIR resource operations
│   ├── llm/
│   │   ├── __init__.py           # LLM factory (get_llm)
│   │   ├── base.py               # Abstract LLMProvider + shared prompts
│   │   ├── grok.py               # Grok (X.AI) — default
│   │   ├── openai_provider.py    # OpenAI GPT-4o
│   │   ├── anthropic_provider.py # Anthropic Claude
│   │   └── ollama.py             # Ollama local LLM
│   ├── services/
│   │   ├── __init__.py           # (empty)
│   │   ├── ocr.py                # PDF/image text extraction
│   │   ├── referral.py           # Core referral processing pipeline
│   │   ├── scheduling.py         # Provider matching + insurance verification
│   │   └── rcm.py                # Revenue cycle analytics
│   ├── mcp/
│   │   ├── __init__.py           # (empty)
│   │   └── server.py             # FastMCP tool definitions
│   └── api/
│       ├── __init__.py           # (empty)
│       └── routes.py             # FastAPI REST endpoints
├── frontend/                     # React 18 SPA
│   ├── index.html                # HTML shell
│   ├── package.json              # Node dependencies
│   ├── vite.config.js            # Vite dev server + proxy
│   ├── tailwind.config.js        # Tailwind CSS config
│   ├── postcss.config.js         # PostCSS config
│   ├── public/
│   │   └── logo.svg              # Favicon
│   └── src/
│       ├── main.jsx              # React entry point
│       ├── App.jsx               # Router layout
│       ├── index.css             # Tailwind base + utility classes
│       ├── services/
│       │   └── api.js            # Backend API client
│       ├── components/
│       │   ├── Layout.jsx        # Sidebar + content shell
│       │   ├── FileUpload.jsx    # Drag-and-drop file upload
│       │   ├── StatCard.jsx      # Dashboard stat widget
│       │   └── StatusBadge.jsx   # Referral status badge
│       └── pages/
│           ├── Dashboard.jsx     # Main dashboard
│           ├── Referrals.jsx     # Referral inbox + upload
│           ├── ReferralDetail.jsx# Single referral detail + approve/reject
│           ├── Scheduling.jsx    # Provider search + insurance verify
│           ├── RCM.jsx           # Revenue cycle dashboard
│           └── Settings.jsx      # EMR/LLM config, connection status
└── _archive/                     # Old files (gitignored, local only)
```

---

## Root Files

### requirements.txt

Python package dependencies:

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥0.115.0 | Web framework (async) |
| `uvicorn[standard]` | ≥0.32.0 | ASGI server with hot-reload |
| `pydantic` | ≥2.0 | Data validation / models |
| `pydantic-settings` | ≥2.0 | Settings from env vars |
| `httpx` | ≥0.27.0 | Async HTTP client (for FHIR + LLM calls) |
| `PyJWT` | ≥2.9.0 | JWT creation for SMART auth |
| `cryptography` | ≥43.0 | RSA key generation for JWT |
| `pypdf` | ≥4.0 | PDF text extraction (embedded) |
| `Pillow` | ≥10.0 | Image handling for OCR |
| `pytesseract` | ≥0.3.10 | Tesseract OCR wrapper |
| `mcp[cli]` | ≥1.0 | Model Context Protocol server |
| `python-dotenv` | ≥1.0 | .env file loading |

Commented-out optional: `openai`, `anthropic`, `pdf2image` (for scanned PDFs, requires poppler).

### .env.example / .env

Template for environment configuration. The `.env` file is gitignored and contains actual secrets (API keys, client secrets).

**Sections:**
1. **EMR Provider** — `EMR_PROVIDER` (ecw|athena), `EMR_REDIRECT_URI`
2. **eCW settings** — `ECW_FHIR_BASE_URL`, `ECW_CLIENT_ID`, `ECW_JWKS_URL`, `ECW_TOKEN_URL`, `ECW_AUTHORIZE_URL`
3. **Athena settings** — `ATHENA_FHIR_BASE_URL`, `ATHENA_CLIENT_ID`, `ATHENA_CLIENT_SECRET`, `ATHENA_AUTHORIZE_URL`, `ATHENA_TOKEN_URL`, `ATHENA_PRACTICE_ID`
4. **LLM Provider** — `LLM_PROVIDER` (grok|openai|anthropic|ollama) + provider-specific keys
5. **App Settings** — `APP_SECRET_KEY`, `APP_HOST`, `APP_PORT`, `APP_ENV`, `LOG_LEVEL`
6. **Fax Processing** — `FAX_POLL_INTERVAL_SECONDS`, `FAX_UPLOAD_DIR`
7. **Database** — `DATABASE_URL`

### .gitignore

Ignores: `__pycache__/`, `.venv/`, `.env`, `*.pem`, `keys/`, `node_modules/`, `frontend/dist/`, `_archive/`, IDE files, OS files, logs.

---

## Backend — `server/`

### server/config.py — Configuration

**Class: `Settings(BaseSettings)`**

Centralized configuration loaded from environment variables (with `.env` file support via pydantic-settings).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `emr_provider` | `Literal["ecw", "athena"]` | `"ecw"` | Active EMR provider |
| `emr_redirect_uri` | `str` | `"https://localhost:8443/api/auth/callback"` | OAuth redirect URI |
| `ecw_fhir_base_url` | `str` | `"https://localhost/fhir/r4/practice"` | eCW FHIR R4 endpoint |
| `ecw_client_id` | `str` | `""` | eCW OAuth client ID |
| `ecw_jwks_url` | `str` | `"https://localhost:8443/.well-known/jwks.json"` | Public key endpoint |
| `ecw_token_url` | `str` | `""` | eCW token endpoint |
| `ecw_authorize_url` | `str` | `""` | eCW authorize endpoint |
| `athena_fhir_base_url` | `str` | `"https://api.platform.athenahealth.com/fhir/r4"` | Athena FHIR endpoint |
| `athena_client_id` | `str` | `""` | Athena OAuth client ID |
| `athena_client_secret` | `str` | `""` | Athena OAuth secret |
| `athena_authorize_url` | `str` | Athena default | Athena authorize URL |
| `athena_token_url` | `str` | Athena default | Athena token URL |
| `athena_practice_id` | `str` | `""` | Athena practice ID |
| `llm_provider` | `Literal["grok","openai","anthropic","ollama"]` | `"grok"` | Active LLM provider |
| `xai_api_key` | `str` | `""` | Grok/X.AI API key |
| `xai_model` | `str` | `"grok-3"` | Grok model name |
| `openai_api_key` | `str` | `""` | OpenAI API key |
| `openai_model` | `str` | `"gpt-4o"` | OpenAI model name |
| `anthropic_api_key` | `str` | `""` | Anthropic API key |
| `anthropic_model` | `str` | `"claude-sonnet-4-20250514"` | Anthropic model name |
| `ollama_base_url` | `str` | `"http://localhost:11434"` | Ollama server URL |
| `ollama_model` | `str` | `"llama3"` | Ollama model name |
| `app_secret_key` | `str` | `"change-me-in-production"` | App secret key |
| `app_host` | `str` | `"0.0.0.0"` | Bind host |
| `app_port` | `int` | `8443` | Bind port |
| `app_env` | `Literal["development","staging","production"]` | `"development"` | Environment |
| `log_level` | `str` | `"INFO"` | Log level |
| `fax_poll_interval_seconds` | `int` | `300` | Fax poll interval |
| `fax_upload_dir` | `str` | `"./uploads"` | Upload directory |
| `database_url` | `str` | `"sqlite:///./patientsynapse.db"` | Database URL |

**Function: `get_settings() -> Settings`**
- Cached singleton via `@lru_cache()`
- Call this anywhere to get the global settings instance

---

### server/main.py — Application Entry Point

Creates and configures the FastAPI application.

**Module-level:**

| Symbol | Description |
|--------|-------------|
| `lifespan(app)` | `@asynccontextmanager` — logs startup info (env, EMR name, LLM provider, FHIR base URL), creates upload directory, logs shutdown |
| `app` | `FastAPI` instance with title="PatientSynapse", version="0.1.0" |

**Middleware:**
- `CORSMiddleware` — allows origins `http://localhost:5173`, `http://localhost:3000`, `https://localhost:8443`; all methods/headers; credentials enabled

**Routes mounted:**
- `router` from `server.api.routes` (all `/api/*` endpoints)
- `GET /.well-known/jwks.json` — returns public JWKS from `SMARTAuth` (for eCW JWT validation)
- Static file mount for `frontend/dist/assets/` (production build)
- Catch-all `GET /{full_path:path}` — serves `index.html` for SPA routing (only when `frontend/dist/` exists)

**`if __name__ == "__main__"`:**
- Runs `uvicorn` with `server.main:app`, host/port from settings, auto-reload in development

---

### server/emr/ — EMR Abstraction Layer

Plug-and-play EMR support. Each EMR vendor implements the same abstract interface.

#### server/emr/base.py — Abstract Base + AuthMethod Enum

**Enum: `AuthMethod(str, Enum)`**

| Value | String | Used By |
|-------|--------|---------|
| `ASYMMETRIC_JWT` | `"private_key_jwt"` | eCW, Epic |
| `CLIENT_SECRET` | `"client_secret_basic"` | Athena |
| `CLIENT_SECRET_POST` | `"client_secret_post"` | (reserved) |

**ABC: `EMRProvider`**

Abstract properties every EMR must implement:

| Property | Return Type | Abstract? | Description |
|----------|-------------|-----------|-------------|
| `name` | `str` | **Yes** | Human-readable EMR name |
| `fhir_base_url` | `str` | **Yes** | FHIR R4 base URL |
| `authorize_url` | `str` | **Yes** | OAuth2 authorization endpoint |
| `token_url` | `str` | **Yes** | OAuth2 token endpoint |
| `client_id` | `str` | **Yes** | OAuth client ID |
| `redirect_uri` | `str` | **Yes** | OAuth redirect URI |
| `scopes` | `list[str]` | **Yes** | SMART on FHIR scopes |
| `auth_method` | `AuthMethod` | **Yes** | Client auth method |
| `client_secret` | `Optional[str]` | No | Default: `None` |
| `jwks_url` | `Optional[str]` | No | Default: `None` |
| `supports_refresh` | `bool` | No | Default: `True` |
| `supported_resources` | `list[str]` | No | Default: `[]` (assume all) |
| `notes` | `str` | No | Default: `""` |

#### server/emr/ecw.py — eClinicalWorks Provider

**Class: `ECWProvider(EMRProvider)`**

| Property | Value |
|----------|-------|
| `name` | `"eClinicalWorks"` |
| `auth_method` | `AuthMethod.ASYMMETRIC_JWT` |
| `fhir_base_url` | from `settings.ecw_fhir_base_url` |
| `authorize_url` | from `settings.ecw_authorize_url` |
| `token_url` | from `settings.ecw_token_url` |
| `client_id` | from `settings.ecw_client_id` |
| `redirect_uri` | from `settings.emr_redirect_uri` |
| `jwks_url` | from `settings.ecw_jwks_url` |

**Scopes (20):**
- Core: `openid`, `fhirUser`, `offline_access`
- Read (12): `user/Patient.read`, `user/Condition.read`, `user/Coverage.read`, `user/Encounter.read`, `user/DocumentReference.read`, `user/ServiceRequest.read`, `user/Practitioner.read`, `user/PractitionerRole.read`, `user/Location.read`, `user/Organization.read`, `user/Procedure.read`, `user/Provenance.read`
- Write (5): `user/Patient.write`, `user/Condition.write`, `user/DocumentReference.write`, `user/ServiceRequest.write`, `user/Encounter.write`, `user/Task.write`, `user/Communication.write`

**Supported resources (14):** Patient, Condition, Coverage, Encounter, DocumentReference, ServiceRequest, Practitioner, PractitionerRole, Location, Organization, Procedure, Provenance, Task, Communication

**Notes:** Appointment booking requires healow Open Access API. Claim submission requires clearinghouse integration.

#### server/emr/athena.py — athenahealth Provider

**Class: `AthenaProvider(EMRProvider)`**

| Property | Value |
|----------|-------|
| `name` | `"athenahealth"` |
| `auth_method` | `AuthMethod.CLIENT_SECRET` |
| `fhir_base_url` | from `settings.athena_fhir_base_url` |
| `authorize_url` | from `settings.athena_authorize_url` |
| `token_url` | from `settings.athena_token_url` |
| `client_id` | from `settings.athena_client_id` |
| `client_secret` | from `settings.athena_client_secret` |
| `redirect_uri` | from `settings.emr_redirect_uri` |

**Scopes (18):**
- Core: `openid`, `fhirUser`, `offline_access`
- Read (12): Same as eCW minus Provenance, plus `user/AllergyIntolerance.read`, `user/MedicationRequest.read`, `user/Observation.read`, `user/DiagnosticReport.read`
- Write (3): `user/Patient.write`, `user/Condition.write`, `user/DocumentReference.write`, `user/ServiceRequest.write`, `user/Encounter.write`

**Supported resources (16):** Patient, Condition, Coverage, Encounter, DocumentReference, ServiceRequest, Practitioner, PractitionerRole, Location, Organization, Procedure, AllergyIntolerance, MedicationRequest, Observation, DiagnosticReport, Immunization

**Notes:** Uses client_secret auth (not JWT). Scheduling via Athena Scheduling API. Task/Communication may have limited support.

#### server/emr/\_\_init\_\_.py — EMR Factory

**Function: `get_emr() -> EMRProvider`**
- Cached via `@lru_cache()`
- Reads `settings.emr_provider` and uses `match/case` to instantiate `ECWProvider` or `AthenaProvider`
- Raises `ValueError` for unknown provider

---

### server/auth/ — SMART on FHIR OAuth2

#### server/auth/smart.py — SMARTAuth Class

**Dataclass: `TokenSet`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `access_token` | `str` | (required) | OAuth access token |
| `token_type` | `str` | `"Bearer"` | Token type |
| `expires_in` | `int` | `3600` | Token lifetime seconds |
| `refresh_token` | `Optional[str]` | `None` | Refresh token |
| `scope` | `str` | `""` | Granted scopes |
| `id_token` | `Optional[str]` | `None` | OIDC id token |
| `issued_at` | `float` | `time.time()` | Timestamp of issue |

**Property:** `is_expired -> bool` — True if within 60s of expiry.

**Class: `SMARTAuth`**

Constructor: `__init__(self, emr: EMRProvider)`
- Stores EMR provider reference
- Creates `keys/` directory for RSA keys
- Only generates/loads RSA private key when `emr.auth_method == ASYMMETRIC_JWT`

**Private methods:**

| Method | Description |
|--------|-------------|
| `_load_or_generate_key() -> RSAPrivateKey` | Loads `keys/private_key.pem` if exists, otherwise generates 2048-bit RSA key pair, saves both PEM files, returns private key |
| `_build_token_data(**extra) -> dict` | Builds token POST body. For JWT auth: adds `client_assertion_type` + `client_assertion`. For secret_post: adds `client_id` + `client_secret`. For secret_basic: nothing (uses header) |
| `_build_auth_header() -> Optional[tuple]` | Returns `(client_id, client_secret)` tuple for HTTP Basic auth when `CLIENT_SECRET`, otherwise `None` |
| `_build_client_assertion() -> str` | Creates signed JWT with RS384: `iss`=client_id, `sub`=client_id, `aud`=token_url, `exp`=now+300, `iat`=now, `jti`=random UUID. Header includes `kid`="patientsynapse-1" |

**Public methods:**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_jwks()` | — | `dict` | Returns JWKS JSON with RSA public key (for JWT auth). Empty `{"keys":[]}` if not JWT auth. Key format: `kty`=RSA, `alg`=RS384, `kid`=patientsynapse-1 |
| `get_authorize_url(state?)` | `state: Optional[str]` | `str` | Builds OAuth2 authorization URL with `response_type=code`, `client_id`, `redirect_uri`, `scope` (space-joined), `state` (random UUID if not provided), `aud`=FHIR base URL |
| `exchange_code(code)` | `code: str` | `TokenSet` | POST to token endpoint with `grant_type=authorization_code`, stores result as `self._token` |
| `refresh()` | — | `TokenSet` | POST to token endpoint with `grant_type=refresh_token`, preserves refresh token if not returned |
| `get_valid_token()` | — | `str` | Returns access token, auto-refreshes if expired. Raises `ValueError` if not authenticated |
| `is_authenticated` | — | `bool` | Property: True if `_token` is not None |

---

### server/fhir/ — FHIR R4 Client & Models

#### server/fhir/models.py — Pydantic FHIR Resource Models

All models use Pydantic `BaseModel` with optional fields.

**Common FHIR Types:**

| Type | Key Fields |
|------|------------|
| `Coding` | `system`, `code`, `display` |
| `CodeableConcept` | `coding: List[Coding]`, `text` |
| `Reference` | `reference`, `display` |
| `HumanName` | `use`, `family`, `given[]`, `prefix[]`, `suffix[]` + `full_name` property |
| `Address` | `use`, `line[]`, `city`, `state`, `postalCode`, `country` |
| `ContactPoint` | `system` (phone/email/fax), `value`, `use` (home/work/mobile) |
| `Period` | `start`, `end` |
| `Identifier` | `system`, `value`, `use` |

**FHIR Resources:**

| Resource | Key Fields | Properties |
|----------|------------|------------|
| `Patient` | `id`, `identifier[]`, `name[]`, `birthDate`, `gender`, `address[]`, `telecom[]` | `primary_name` |
| `Condition` | `id`, `clinicalStatus`, `verificationStatus`, `category[]`, `code`, `subject`, `encounter`, `onsetDateTime`, `recordedDate` | — |
| `Coverage` | `id`, `status`, `type`, `subscriber`, `beneficiary`, `payor[]`, `class_` (alias `class`), `period` | — |
| `Encounter` | `id`, `status`, `class_` (alias `class`), `type[]`, `subject`, `participant[]`, `period`, `reasonCode[]`, `diagnosis[]` | — |
| `DocumentReference` | `id`, `status`, `type`, `subject`, `date`, `description`, `content[]` | — |
| `ServiceRequest` | `id`, `status`, `intent`, `category[]`, `code`, `subject`, `requester`, `performer[]`, `reasonCode[]`, `priority`, `note[]` | — |
| `Practitioner` | `id`, `identifier[]`, `name[]`, `telecom[]`, `qualification[]` | — |
| `PractitionerRole` | `id`, `practitioner`, `organization`, `code[]`, `specialty[]`, `location[]` | — |
| `Location` | `id`, `name`, `type[]`, `telecom[]`, `address` | — |
| `Organization` | `id`, `identifier[]`, `name`, `type[]`, `telecom[]`, `address[]` | — |
| `Procedure` | `id`, `status`, `code`, `subject`, `performedDateTime`, `performer[]` | — |
| `Task` | `id`, `status`, `intent`, `code`, `description`, `for_` (alias `for`), `requester`, `owner`, `note[]` | — |
| `Communication` | `id`, `status`, `category[]`, `subject`, `sender`, `recipient[]`, `payload[]`, `sent` | — |

**Bundle types:**

| Type | Fields |
|------|--------|
| `BundleEntry` | `resource: Optional[dict]`, `fullUrl` |
| `Bundle` | `resourceType`, `type`, `total`, `entry: List[BundleEntry]`, `link[]` |

#### server/fhir/client.py — Async HTTP Client

**Class: `FHIRClient`**

Constructor: `__init__(self, auth: SMARTAuth)` — stores auth reference, lazy-creates httpx client.

| Method | HTTP | Path | Description |
|--------|------|------|-------------|
| `read(resource_type, resource_id)` | `GET` | `/{type}/{id}` | Fetch single resource |
| `search(resource_type, params?)` | `GET` | `/{type}?params` | Search, returns Bundle dict |
| `create(resource_type, resource)` | `POST` | `/{type}` | Create resource |
| `update(resource_type, resource_id, resource)` | `PUT` | `/{type}/{id}` | Update resource |
| `close()` | — | — | Close httpx client |

**Details:**
- `_get_client()` — lazy-creates `httpx.AsyncClient` with `base_url` from `self.auth.emr.fhir_base_url`, 30s timeout
- `_headers()` — gets valid token from auth, returns `Authorization: Bearer {token}` + FHIR JSON content type
- All methods log the operation and status code

#### server/fhir/resources.py — High-Level Resource Operations

Each class wraps `FHIRClient` and provides typed, domain-specific operations.

**Class: `PatientResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `search_by_name_dob(family, given, birthdate)` | `str, str, str` | `List[Patient]` | FHIR search with `family`, `given`, `birthdate` params |
| `search_by_identifier(identifier)` | `str` | `List[Patient]` | FHIR search by identifier |
| `get(patient_id)` | `str` | `Patient` | Fetch by ID |
| `create(patient)` | `Patient` | `Patient` | Create new patient |
| `update(patient)` | `Patient` | `Patient` | Update existing patient |

**Class: `ConditionResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `search_by_patient(patient_id)` | `str` | `List[Condition]` | All conditions for patient |
| `create_problem(patient_id, code, system, display)` | `str, str, str, str` | `Condition` | Create problem-list-item with ICD-10 code |
| `create_encounter_diagnosis(patient_id, encounter_id, code, system, display)` | 5 strs | `Condition` | Create encounter-diagnosis |

**Class: `CoverageResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_by_patient(patient_id)` | `str` | `List[Coverage]` |

**Class: `EncounterResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `search_by_patient(patient_id)` | `str` | `List[Encounter]` | All encounters |
| `create_telephone_encounter(patient_id, reason)` | `str, str` | `Encounter` | Creates virtual/telephone encounter |

**Class: `DocumentReferenceResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `search_by_patient(patient_id)` | `str` | `List[DocumentReference]` | All documents |
| `attach_pdf(patient_id, pdf_bytes, description)` | `str, bytes, str` | `DocumentReference` | Attach PDF as base64 inline, type=Referral note (LOINC 57133-1) |

**Class: `ServiceRequestResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `search_by_patient(patient_id)` | `str` | `List[ServiceRequest]` | All service requests |
| `create_referral(patient_id, referring_provider, reason, priority)` | `str, str, str, str` | `ServiceRequest` | Create referral with SNOMED code 3457005 (Patient referral) |

**Class: `PractitionerResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_by_name(name)` | `str` | `List[Practitioner]` |
| `get(practitioner_id)` | `str` | `Practitioner` |

**Class: `PractitionerRoleResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_by_specialty(specialty)` | `str` | `List[PractitionerRole]` |
| `search_by_practitioner(practitioner_id)` | `str` | `List[PractitionerRole]` |

**Class: `LocationResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_all()` | — | `List[Location]` |
| `get(location_id)` | `str` | `Location` |

**Class: `OrganizationResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_by_name(name)` | `str` | `List[Organization]` |
| `search_payors()` | — | `List[Organization]` (type=pay) |

**Class: `ProcedureResource`**

| Method | Params | Returns |
|--------|--------|---------|
| `search_by_patient(patient_id)` | `str` | `List[Procedure]` |

**Class: `TaskResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `create_review_task(patient_id, description, owner?)` | `str, str, Optional[str]` | `Task` | Create review task |

**Class: `CommunicationResource`**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `send_notification(patient_id, message, recipient?)` | `str, str, Optional[str]` | `Communication` | Send notification message |

---

### server/llm/ — LLM Abstraction Layer

#### server/llm/base.py — Abstract Base + Prompts

**Dataclass: `LLMMessage`**

| Field | Type | Description |
|-------|------|-------------|
| `role` | `str` | `"system"`, `"user"`, or `"assistant"` |
| `content` | `str` | Message content |

**Dataclass: `LLMResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Response text |
| `model` | `str` | Model name used |
| `usage` | `Optional[Dict[str, int]]` | Token usage (`prompt_tokens`, `completion_tokens`) |

**ABC: `LLMProvider`**

| Method | Params | Returns | Abstract? | Description |
|--------|--------|---------|-----------|-------------|
| `name` (property) | — | `str` | **Yes** | Provider name |
| `complete(messages, temperature?, max_tokens?, response_format?)` | `List[LLMMessage], float=0.3, int=4096, Optional[str]` | `LLMResponse` | **Yes** | Chat completion |
| `extract_referral_data(text)` | `str` | `dict` | No | Extracts structured JSON from referral fax text |
| `classify_document(text)` | `str` | `str` | No | Classifies fax as: referral, lab_result, insurance_auth, medical_records, other |

**`extract_referral_data` system prompt** instructs the LLM to return JSON with:
```json
{
  "patient": {
    "first_name", "last_name", "date_of_birth", "gender",
    "phone", "address": {"line","city","state","zip"},
    "insurance_id", "insurance_name"
  },
  "referral": {
    "referring_provider", "referring_practice", "referring_phone",
    "referring_fax", "reason",
    "diagnosis_codes": [{"code","display"}],
    "urgency": "routine|urgent|stat", "notes"
  }
}
```

#### server/llm/grok.py — Grok (X.AI) Provider

**Class: `GrokProvider(LLMProvider)`**

| Attribute | Value |
|-----------|-------|
| `BASE_URL` | `"https://api.x.ai/v1"` |
| `name` | `"grok"` |

- **`complete()`**: POST to `/chat/completions` (OpenAI-compatible API)
- Auth: `Authorization: Bearer {xai_api_key}`
- Model: from `settings.xai_model` (default: `grok-3`)
- Supports `response_format: {"type": "json_object"}`
- Timeout: 60s

#### server/llm/openai_provider.py — OpenAI Provider

**Class: `OpenAIProvider(LLMProvider)`**

| Attribute | Value |
|-----------|-------|
| `BASE_URL` | `"https://api.openai.com/v1"` |
| `name` | `"openai"` |

- Identical structure to Grok (both are OpenAI-compatible)
- Auth: `Authorization: Bearer {openai_api_key}`
- Model: from `settings.openai_model` (default: `gpt-4o`)

#### server/llm/anthropic_provider.py — Anthropic Provider

**Class: `AnthropicProvider(LLMProvider)`**

| Attribute | Value |
|-----------|-------|
| `BASE_URL` | `"https://api.anthropic.com/v1"` |
| `name` | `"anthropic"` |

- **`complete()`**: POST to `/messages` (Anthropic Messages API)
- Auth: `x-api-key: {anthropic_api_key}`, `anthropic-version: 2023-06-01`
- Model: from `settings.anthropic_model` (default: `claude-sonnet-4-20250514`)
- **Anthropic-specific**: System message is extracted to top-level `system` field (not in `messages` array)
- For JSON mode: appends `"\nRespond with valid JSON only."` to system prompt
- Maps `input_tokens` → `prompt_tokens`, `output_tokens` → `completion_tokens`

#### server/llm/ollama.py — Ollama Local Provider

**Class: `OllamaProvider(LLMProvider)`**

| Attribute | Value |
|-----------|-------|
| `name` | `"ollama"` |

- **`complete()`**: POST to `{ollama_base_url}/api/chat` (Ollama API)
- No auth needed (local server)
- Model: from `settings.ollama_model` (default: `llama3`)
- `stream: False`
- Options: `temperature`, `num_predict` (= max_tokens)
- JSON mode: `format: "json"`
- Timeout: 120s (local inference can be slow)

#### server/llm/\_\_init\_\_.py — LLM Factory

**Function: `get_llm() -> LLMProvider`**
- **Not cached** (creates new instance each call, unlike EMR factory)
- Uses `match/case` on `settings.llm_provider`
- Lazy imports each provider class
- Raises `ValueError` for unknown provider

---

### server/services/ — Business Logic Services

#### server/services/ocr.py — OCR Text Extraction

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| `extract_text_from_pdf(pdf_bytes)` | `bytes` | `str` | Extracts text from PDF. Uses `pypdf` for embedded text first. Falls back to OCR via `_ocr_pdf()` if embedded text < 50 chars |
| `extract_text_from_image(image_bytes)` | `bytes` | `str` | Uses `pytesseract` + `Pillow` to OCR an image |
| `_ocr_pdf(pdf_bytes)` | `bytes` | `str` | Converts PDF pages to images via `pdf2image`, then OCRs each page with `pytesseract` |

All functions are `async` and handle `ImportError` gracefully (returns empty string if dependencies missing).

#### server/services/referral.py — Referral Processing Pipeline

**Enum: `ReferralStatus(str, Enum)`**

| Value | Description |
|-------|-------------|
| `PENDING` | Just uploaded, not yet processed |
| `PROCESSING` | AI is extracting data |
| `REVIEW` | Awaiting human review |
| `APPROVED` | Reviewed, ready to push to EMR |
| `COMPLETED` | Pushed to EMR successfully |
| `FAILED` | Error during processing |
| `REJECTED` | Manually rejected |

**Dataclass: `ExtractedReferral`**

All fields `Optional[str]` except:
- `diagnosis_codes: list` (default `[]`) — list of `{code, display}` dicts
- `urgency: str` (default `"routine"`)
- `confidence: float` (default `0.0`)

Full field list: `patient_first_name`, `patient_last_name`, `patient_dob`, `patient_gender`, `patient_phone`, `patient_address_line/city/state/zip`, `insurance_id`, `insurance_name`, `referring_provider`, `referring_practice`, `referring_phone`, `referring_fax`, `reason`, `diagnosis_codes`, `urgency`, `notes`, `confidence`

**Dataclass: `ReferralRecord`**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | 8-char UUID prefix |
| `filename` | `str` | Original filename |
| `status` | `ReferralStatus` | Current status |
| `uploaded_at` | `str` | ISO timestamp |
| `extracted_data` | `Optional[ExtractedReferral]` | LLM-extracted data |
| `patient_id` | `Optional[str]` | FHIR Patient ID after push |
| `service_request_id` | `Optional[str]` | FHIR ServiceRequest ID |
| `error` | `Optional[str]` | Error message |
| `reviewed_by` | `Optional[str]` | Reviewer name |
| `completed_at` | `Optional[str]` | ISO timestamp |

**Class: `ReferralService`**

Constructor: `__init__(self, fhir_client: FHIRClient)`
- Creates instances of all needed resource classes (PatientResource, ConditionResource, etc.)
- Gets LLM via `get_llm()`
- Stores referrals in-memory dict `self._referrals` (to be swapped with DB)

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `process_fax(fax_text, filename)` | `str, str` | `ReferralRecord` | **Step 1**: Creates record (PROCESSING), calls `llm.extract_referral_data()`, parses result, sets status to REVIEW. On error → FAILED |
| `approve_and_push(ref_id, overrides?)` | `str, Optional[dict]` | `ReferralRecord` | **Steps 2-5**: Applies overrides, matches/creates patient, adds conditions (ICD-10), creates ServiceRequest, sends notification. On error → FAILED + creates review task |
| `_match_or_create_patient(data)` | `ExtractedReferral` | `Patient` | Searches by name+DOB; if match found, returns it. Otherwise creates new patient with demographics |
| `_parse_extracted(raw)` | `dict` | `ExtractedReferral` | Converts LLM JSON (nested `patient`/`referral` keys) to flat `ExtractedReferral` |

#### server/services/scheduling.py — Smart Scheduling

**Dataclass: `ProviderMatch`**

| Field | Type | Description |
|-------|------|-------------|
| `practitioner_id` | `str` | FHIR Practitioner ID |
| `practitioner_name` | `str` | Display name |
| `specialty` | `str` | Specialty display |
| `location_name` | `Optional[str]` | Practice location |
| `location_id` | `Optional[str]` | FHIR Location ID |
| `score` | `float` | Match confidence (default 0.0) |

**Dataclass: `SchedulingContext`**

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | `str` | FHIR Patient ID |
| `patient_name` | `str` | Patient name |
| `reason` | `str` | Referral reason |
| `urgency` | `str` | Urgency level |
| `insurance_verified` | `bool` | Whether insurance is verified |
| `insurance_name` | `Optional[str]` | Payer name |
| `matched_providers` | `List[ProviderMatch]` | Matching providers |
| `selected_provider` | `Optional[ProviderMatch]` | Selected provider |

**Class: `SchedulingService`**

Constructor: `__init__(self, fhir_client: FHIRClient)` — creates PractitionerResource, PractitionerRoleResource, LocationResource, CoverageResource

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `find_providers(specialty)` | `str` | `List[ProviderMatch]` | Searches PractitionerRole by specialty, extracts practitioner name, specialty display, location |
| `verify_insurance(patient_id)` | `str` | `dict` | Checks Coverage resources. Returns `{verified, reason/coverage_id/payor/status}` |
| `prepare_scheduling(patient_id, patient_name, reason, urgency, specialty?)` | 5 params | `SchedulingContext` | Builds full scheduling context: verifies insurance + finds matching providers |
| `get_locations()` | — | `List[Location]` | Returns all practice locations |

#### server/services/rcm.py — Revenue Cycle Management

**Dataclass: `RCMSummary`**

| Field | Type |
|-------|------|
| `total_encounters` | `int` |
| `encounters_this_month` | `int` |
| `top_diagnoses` | `List[dict]` |
| `payer_mix` | `List[dict]` |
| `procedures_count` | `int` |
| `generated_at` | `str` |

**Dataclass: `PatientBillingContext`**

| Field | Type |
|-------|------|
| `patient_id` | `str` |
| `encounters` | `List[dict]` |
| `diagnoses` | `List[dict]` |
| `procedures` | `List[dict]` |
| `insurance` | `Optional[dict]` |

**Class: `RCMService`**

Constructor: `__init__(self, fhir_client: FHIRClient)` — creates EncounterResource, ConditionResource, CoverageResource, ProcedureResource, OrganizationResource

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_patient_billing_context(patient_id)` | `str` | `PatientBillingContext` | Fetches encounters (id/status/type/period/dx count), conditions (code/display/category), procedures (code/display/status/date), insurance (payor/status) |
| `get_payer_mix(patient_ids)` | `List[str]` | `List[dict]` | Counts active coverages by payer across patients. Returns `{payor, count, percentage}` sorted by frequency |
| `get_top_diagnoses(patient_ids, limit?)` | `List[str], int=10` | `List[dict]` | Counts conditions by ICD-10 code across patients. Returns `{code, display, count}` top N |

---

### server/mcp/ — MCP Server (AI Agent Tools)

#### server/mcp/server.py — FastMCP Tool Definitions

Creates: `mcp = FastMCP("PatientSynapse")`

**MCP Tools (10):**

| Tool | Params | Returns | Connected? | Description |
|------|--------|---------|------------|-------------|
| `extract_referral_data` | `fax_text: str` | JSON string | **No** (uses LLM directly) | AI extracts patient/referral data from fax text |
| `classify_document` | `document_text: str` | category string | **No** (uses LLM) | Classifies fax type |
| `summarize_referral` | `fax_text: str` | summary string | **No** (uses LLM) | 2-3 sentence clinical summary |
| `search_patient` | `first_name, last_name, date_of_birth` | JSON string | Stub (not connected) | Searches patient in EMR |
| `get_patient_summary` | `patient_id: str` | JSON string | Stub | Patient demographics + conditions + insurance |
| `find_available_providers` | `specialty: str` | JSON string | Stub | Providers by specialty |
| `verify_patient_insurance` | `patient_id: str` | JSON string | Stub | Insurance coverage check |
| `get_patient_billing` | `patient_id: str` | JSON string | Stub | Billing context |
| `analyze_diagnosis_codes` | `fax_text: str` | JSON string | **No** (uses LLM) | Extracts/validates ICD-10 codes |
| `check_system_status` | — | JSON string | **Yes** | Returns LLM provider, FHIR URL, env |

**Note:** Tools marked "Stub" return `{"status": "not_connected"}` until FHIR client is wired after OAuth flow.

---

### server/api/ — REST API Routes

#### server/api/routes.py — All HTTP Endpoints

**Module-level globals:**
- `router = APIRouter(prefix="/api")` — all routes prefixed with `/api`
- `_referral_service: Optional[ReferralService]` — module-level service reference, injected from `main.py`

**Helper functions:**
- `set_referral_service(svc)` — sets the global referral service
- `get_referral_service()` — returns the service or raises HTTP 503
- `_serialize_referral(record)` — converts `ReferralRecord` to JSON-safe dict (with `status` as string)

**Request/Response models:**
- `ReferralApproval` — `overrides: Optional[dict]`
- `ReferralReject` — `reason: Optional[str]`

**Endpoints:**

| Method | Path | Function | Description |
|--------|------|----------|-------------|
| `GET` | `/api/auth/status` | `auth_status()` | Returns `{authenticated, emr_provider, fhir_base_url}` |
| `GET` | `/api/auth/login` | `auth_login()` | Returns `{authorize_url}` — the OAuth URL to redirect to |
| `GET` | `/api/auth/callback` | `auth_callback(code, state?)` | Exchanges auth code for token. Returns `{status, emr, scope}` |
| `POST` | `/api/referrals/upload` | `upload_referral(file)` | Upload PDF/image file → OCR → LLM extract → returns referral record |
| `POST` | `/api/referrals/upload-text` | `upload_referral_text(body)` | Upload raw text (for testing) → LLM extract → returns referral record |
| `GET` | `/api/referrals` | `list_referrals(status?)` | List all referrals, optional filter by status |
| `GET` | `/api/referrals/{ref_id}` | `get_referral(ref_id)` | Get single referral |
| `POST` | `/api/referrals/{ref_id}/approve` | `approve_referral(ref_id, body?)` | Approve + push to EMR |
| `POST` | `/api/referrals/{ref_id}/reject` | `reject_referral(ref_id, body?)` | Reject referral |
| `GET` | `/api/scheduling/providers` | `search_providers(specialty?)` | Stub: "not_connected" |
| `GET` | `/api/scheduling/insurance/{patient_id}` | `verify_insurance(patient_id)` | Stub: "not_connected" |
| `GET` | `/api/rcm/patient/{patient_id}` | `patient_billing(patient_id)` | Stub: "not_connected" |
| `GET` | `/api/rcm/dashboard` | `rcm_dashboard()` | Returns placeholder RCM stats with dynamic EMR name |
| `GET` | `/api/status` | `system_status()` | Returns `{status, emr_provider, emr_provider_key, llm_provider, fhir_connected, app_env}` |

---

## Frontend — `frontend/`

### Build Tooling

#### package.json

| Field | Value |
|-------|-------|
| `name` | `patientsynapse-frontend` |
| `version` | `0.1.0` |
| `type` | `module` |

**Dependencies:**
- `react` ^18.3.1
- `react-dom` ^18.3.1
- `react-router-dom` ^6.28.0
- `lucide-react` ^0.460.0 (icons)

**Dev Dependencies:**
- `@vitejs/plugin-react` ^4.3.4
- `tailwindcss` ^3.4.15
- `autoprefixer`, `postcss`
- `vite` ^6.0.0

**Scripts:** `dev` = `vite`, `build` = `vite build`, `preview` = `vite preview`

#### vite.config.js

- Plugin: `react()`
- Dev server port: `5173`
- Proxy: `/api` → `http://localhost:8443`, `/.well-known` → `http://localhost:8443`

#### tailwind.config.js

Content scan: `index.html`, `src/**/*.{js,jsx}`

Custom colors:
- `brand.*` — Blue palette (50-900), primary = `brand-500` (#2563eb)
- `medical.green` — #10b981
- `medical.sky` — #0ea5e9

#### postcss.config.js

Standard Tailwind setup: `tailwindcss`, `autoprefixer`

#### index.html

- Title: "PatientSynapse"
- Favicon: `/logo.svg`
- Body classes: `bg-gray-50 text-gray-900 antialiased`
- Root div mounts React

### Source — `frontend/src/`

#### main.jsx — React Entry Point

Renders `<App />` inside `<BrowserRouter>` and `<React.StrictMode>`.

#### App.jsx — Router / Page Layout

Uses `react-router-dom` `Routes`/`Route`:

| Path | Component |
|------|-----------|
| `/` | `Dashboard` |
| `/referrals` | `Referrals` |
| `/referrals/:id` | `ReferralDetail` |
| `/scheduling` | `Scheduling` |
| `/rcm` | `RCM` |
| `/settings` | `Settings` |
| `*` | Redirects to `/` |

All routes wrapped in `<Layout />` (via `<Route element={<Layout />}>`).

#### index.css — Global Styles (Tailwind)

Tailwind directives: `@tailwind base; @tailwind components; @tailwind utilities;`

**Custom component classes:**

| Class | Description |
|-------|-------------|
| `.card` | White rounded-xl card with shadow and border |
| `.btn-primary` | Blue button (`brand-500`) |
| `.btn-secondary` | Gray button |
| `.btn-success` | Green button (`emerald-500`) |
| `.btn-danger` | Red button |
| `.badge` | Inline flex pill badge |
| `.badge-pending` | Amber badge |
| `.badge-review` | Blue badge |
| `.badge-completed` | Green badge |
| `.badge-failed` | Red badge |
| `.input` | Form input with focus ring |

#### services/api.js — API Client

Base: `/api` (relative, proxied to backend)

**`request(path, options)`** — Core fetch wrapper. Adds JSON headers. Throws on non-OK with `detail` from response body.

**Exported functions:**

| Function | HTTP | Path | Description |
|----------|------|------|-------------|
| `getAuthStatus()` | GET | `/auth/status` | Check OAuth status |
| `getLoginUrl()` | GET | `/auth/login` | Get authorize URL |
| `loginAuth` | — | — | Alias of `getLoginUrl` |
| `uploadReferralFile(file)` | POST | `/referrals/upload` | FormData upload |
| `uploadReferralText(text, filename)` | POST | `/referrals/upload-text` | Text upload |
| `listReferrals(status?)` | GET | `/referrals?status=` | List referrals |
| `getReferral(id)` | GET | `/referrals/{id}` | Get single referral |
| `approveReferral(id, overrides?)` | POST | `/referrals/{id}/approve` | Approve |
| `rejectReferral(id, reason?)` | POST | `/referrals/{id}/reject` | Reject |
| `searchProviders(specialty?)` | GET | `/scheduling/providers` | Provider search |
| `verifyInsurance(patientId)` | GET | `/scheduling/insurance/{id}` | Insurance check |
| `getRCMDashboard()` | GET | `/rcm/dashboard` | RCM stats |
| `getPatientBilling(patientId)` | GET | `/rcm/patient/{id}` | Patient billing |
| `getSystemStatus()` | GET | `/status` | System health |
| `getStatus` | — | — | Alias of `getSystemStatus` |

#### components/Layout.jsx — Shell (Sidebar + Content)

Full-height flex layout:
- **Left sidebar** (w-60): Logo (inline SVG + "Patient**Bridge**" text), nav links, status footer
- **Main content**: `<Outlet />` from react-router

**Navigation items:**

| Path | Icon | Label |
|------|------|-------|
| `/` | `LayoutDashboard` | Dashboard |
| `/referrals` | `FileText` | Referrals |
| `/scheduling` | `CalendarClock` | Scheduling |
| `/rcm` | `DollarSign` | RCM |
| `/settings` | `Settings` | Settings |

Active link: `bg-brand-50 text-brand-600`. Footer shows `Activity` icon + "System Online".

#### components/FileUpload.jsx — Drag-and-Drop Upload

**Props:** `onUpload: (file) => Promise`, `accept: string` (default: `.pdf,.png,.jpg,.jpeg,.tiff`)

**State:** `dragOver`, `file`, `uploading`, `error`

**Behavior:**
1. Drag-and-drop zone with dashed border (highlights blue on drag over)
2. Hidden `<input type="file">` triggered by label click
3. Selected file shown with name/size, "Upload & Process" button, X to clear
4. Calls `onUpload(file)` on submit, shows error on failure

#### components/StatCard.jsx — Dashboard Stat Widget

**Props:** `icon: Component`, `label: string`, `value: any`, `sub?: string`, `color?: string`

Renders: Icon in colored circle + large value + label + optional sub-text.

**Color options:** `brand` (blue), `green`, `amber`, `red`, `sky`

#### components/StatusBadge.jsx — Referral Status Badge

**Props:** `status: string`

Maps status to Tailwind badge styles:

| Status | Style |
|--------|-------|
| `pending` | Amber |
| `processing` | Purple |
| `review` | Blue |
| `approved` | Blue |
| `completed` | Green |
| `failed` | Red |
| `rejected` | Gray |

#### pages/Dashboard.jsx — Main Dashboard

**State:** `referrals[]`, `status`, `loading`

**On mount:** Fetches `listReferrals()` and `getSystemStatus()` in parallel via `Promise.allSettled`.

**Sections:**
1. **Connection banner** — Amber warning if FHIR not connected, links to Settings
2. **Stats row** — 4 `StatCard`s: Total Referrals, Pending Review, Completed, Failed
3. **Quick action cards** — Links to Referral Inbox, Scheduling, RCM Analytics
4. **Recent referrals** — Last 5 referrals with filename, patient name, date, status badge

#### pages/Referrals.jsx — Referral Inbox

**State:** `referrals[]`, `filter`, `loading`, `showTextInput`, `textInput`

**Sections:**
1. **Header** — Title + "Paste Text" toggle button
2. **Upload area** — `FileUpload` component (file mode) or textarea (text mode)
3. **Filter tabs** — all, review, processing, completed, failed, rejected
4. **Referral list** — Cards with filename, patient name, referring provider, urgency badge, upload date, status badge. Links to `ReferralDetail`.

**Upload handlers:**
- `handleFileUpload(file)` → `uploadReferralFile(file)` → prepends to list
- `handleTextUpload()` → `uploadReferralText(textInput)` → prepends to list

#### pages/ReferralDetail.jsx — Single Referral View

**State:** `referral`, `loading`, `acting`

**On mount:** Fetches `getReferral(id)`, redirects to `/referrals` on error.

**Sections:**
1. **Header** — Back button, referral ID, status badge, Approve/Reject buttons (only in `review` status)
2. **Error banner** — Red alert if `referral.error` exists
3. **Patient Information card** — Name, DOB, gender, phone, address, insurance (from `extracted_data`)
4. **Referral Details card** — Referring provider/practice/phone/fax, reason, urgency, notes
5. **Diagnosis Codes** — Grid of ICD-10 code cards (only if codes exist)
6. **Processing Details** — Upload time, completion time, Patient ID, ServiceRequest ID

**Helper:** `Field({ label, value, highlight })` — renders label-value row.

#### pages/Scheduling.jsx — Smart Scheduling

Two side-by-side cards:

**Provider Search (left):**
- Search input for specialty + Search button
- Calls `searchProviders(specialty)` → displays provider cards with name, specialty, location, phone

**Insurance Verification (right):**
- Patient ID input + Verify button
- Calls `verifyInsurance(patientId)` → displays coverage cards (payor, status, subscriber ID, period) or "no coverage" warning

**Info banner:** Explains healow Open Access API needed for actual booking.

#### pages/RCM.jsx — Revenue Cycle Management

**State:** `dashboard`, `patientId`, `billing`, `loading`, `lookingUp`

**On mount:** Fetches `getRCMDashboard()`.

**Sections:**
1. **Stats row** — Referrals Processed, Pending Review, Pushed to eCW, Rejected
2. **Payer Mix** — Horizontal bar chart of payer distribution
3. **Top Diagnoses** — Table of most common ICD-10 codes with counts
4. **Patient Billing Lookup** — Patient ID input → shows encounters and conditions

#### pages/Settings.jsx — Configuration & Status

**State:** `auth`, `status`, `loading`

**On mount:** Fetches `getAuthStatus()` and `getStatus()` in parallel.

**Sections:**

1. **EMR Provider card** — Shows eCW and Athena options, highlights active one. Explains `EMR_PROVIDER` env var.

2. **FHIR Connection card** — Connected/Not connected status with green/gray indicator. "Connect to {emrName}" button → calls `loginAuth()` → opens authorize URL in new tab. Shows FHIR Base URL and Client ID.

3. **LLM Provider card** — Shows Grok, OpenAI, Anthropic, Ollama options, highlights active one. Explains `LLM_PROVIDER` env var.

4. **System Status card** — 4 status dots: Server, FHIR, LLM, MCP Server.

5. **Environment Variables Reference** — Table of all env vars with descriptions.

**Helper components:**
- `StatusItem({ label, ok })` — green/gray dot + label
- `EnvRow({ name, desc })` — table row with monospace var name

---

## Assets — `assets/`

| File | Description |
|------|-------------|
| `assets/logos/logo.svg` | Full PatientSynapse logo (bridge + cross icon + text) |
| `assets/logos/logo-icon.svg` | Icon only (bridge + cross) |
| `assets/logos/logo-banner.svg` | Banner format (185×35) |
| `frontend/public/logo.svg` | Favicon copy |

Logo design: Blue bridge arches + green medical cross, "Patient" in dark + "Bridge" in brand blue.

---

## Data Flow Diagrams

### Referral Processing Pipeline

```
Fax PDF/Image
     │
     ▼
[Upload to /api/referrals/upload]
     │
     ▼
[OCR: extract_text_from_pdf() or extract_text_from_image()]
     │  Uses pypdf → pytesseract fallback
     ▼
[LLM: extract_referral_data(text)]
     │  Grok/OpenAI/Anthropic/Ollama
     │  Returns structured JSON
     ▼
[ReferralService.process_fax()]
     │  Creates ReferralRecord (status=REVIEW)
     │  Parses LLM JSON → ExtractedReferral
     ▼
[Human Review in UI]
     │  /referrals/{id} page
     │  Approve or Reject
     ▼
[ReferralService.approve_and_push()]
     │
     ├─→ [1] Match or create Patient (FHIR)
     ├─→ [2] Create Conditions for each ICD-10 code (FHIR)
     ├─→ [3] Create ServiceRequest (referral) (FHIR)
     └─→ [4] Send Communication notification (FHIR)
           │
           ▼
     [status=COMPLETED]
```

### OAuth2 Authentication Flow

```
[Frontend Settings page]
     │
     ▼
[GET /api/auth/login]
     │  Returns authorize_url
     ▼
[Redirect to EMR authorize_url]
     │  EMR login widget (eCW or Athena)
     │  Provider authenticates
     ▼
[EMR redirects to /api/auth/callback?code=xxx]
     │
     ▼
[SMARTAuth.exchange_code(code)]
     │
     ├─ eCW:    POST token_url with client_assertion (JWT, RS384)
     │          client_assertion_type = urn:ietf:params:oauth:client-assertion-type:jwt-bearer
     │
     └─ Athena: POST token_url with HTTP Basic Auth (client_id:client_secret)
     │
     ▼
[TokenSet stored in memory]
     │  access_token, refresh_token, scope, expires_in
     ▼
[FHIR Client uses Bearer token for all API calls]
     │  Auto-refreshes when expired
```

---

## API Endpoint Reference

| Method | Endpoint | Auth Required? | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/auth/status` | No | Check OAuth status |
| `GET` | `/api/auth/login` | No | Get authorize URL |
| `GET` | `/api/auth/callback` | No | OAuth callback (code exchange) |
| `POST` | `/api/referrals/upload` | FHIR (for push) | Upload fax file for processing |
| `POST` | `/api/referrals/upload-text` | FHIR (for push) | Upload raw text |
| `GET` | `/api/referrals` | No | List referrals |
| `GET` | `/api/referrals/{id}` | No | Get referral detail |
| `POST` | `/api/referrals/{id}/approve` | FHIR | Approve + push to EMR |
| `POST` | `/api/referrals/{id}/reject` | No | Reject referral |
| `GET` | `/api/scheduling/providers` | FHIR | Search providers by specialty |
| `GET` | `/api/scheduling/insurance/{id}` | FHIR | Verify patient insurance |
| `GET` | `/api/rcm/dashboard` | No | RCM summary |
| `GET` | `/api/rcm/patient/{id}` | FHIR | Patient billing context |
| `GET` | `/api/status` | No | System health check |
| `GET` | `/.well-known/jwks.json` | No | Public JWKS for JWT auth |

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMR_PROVIDER` | No | `ecw` | `ecw` or `athena` |
| `EMR_REDIRECT_URI` | No | `https://localhost:8443/api/auth/callback` | OAuth callback |
| `ECW_FHIR_BASE_URL` | When ecw | — | eCW FHIR R4 URL |
| `ECW_CLIENT_ID` | When ecw | — | eCW client ID |
| `ECW_JWKS_URL` | When ecw | `https://localhost:8443/.well-known/jwks.json` | JWKS endpoint |
| `ECW_TOKEN_URL` | When ecw | — | eCW token endpoint |
| `ECW_AUTHORIZE_URL` | When ecw | — | eCW authorize endpoint |
| `ATHENA_FHIR_BASE_URL` | When athena | `https://api.platform.athenahealth.com/fhir/r4` | Athena FHIR URL |
| `ATHENA_CLIENT_ID` | When athena | — | Athena client ID |
| `ATHENA_CLIENT_SECRET` | When athena | — | Athena client secret |
| `ATHENA_AUTHORIZE_URL` | When athena | Athena default | Athena authorize |
| `ATHENA_TOKEN_URL` | When athena | Athena default | Athena token |
| `ATHENA_PRACTICE_ID` | When athena | — | Athena practice ID |
| `LLM_PROVIDER` | No | `grok` | `grok`, `openai`, `anthropic`, `ollama` |
| `XAI_API_KEY` | When grok | — | X.AI API key |
| `XAI_MODEL` | No | `grok-3` | Grok model name |
| `OPENAI_API_KEY` | When openai | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model |
| `ANTHROPIC_API_KEY` | When anthropic | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Anthropic model |
| `OLLAMA_BASE_URL` | When ollama | `http://localhost:11434` | Ollama URL |
| `OLLAMA_MODEL` | No | `llama3` | Ollama model |
| `APP_SECRET_KEY` | Yes (prod) | `change-me-in-production` | Session secret |
| `APP_HOST` | No | `0.0.0.0` | Bind host |
| `APP_PORT` | No | `8443` | Bind port |
| `APP_ENV` | No | `development` | Environment |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `FAX_POLL_INTERVAL_SECONDS` | No | `300` | Fax polling interval |
| `FAX_UPLOAD_DIR` | No | `./uploads` | Upload directory |
| `DATABASE_URL` | No | `sqlite:///./patientsynapse.db` | Database URL |

---

## How to Run

**Prerequisites:** Python 3.12+, Node.js 18+

```bash
# Backend
cd patient_bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Then fill in secrets
python -m server.main   # Runs on port 8443

# Frontend (separate terminal)
cd frontend
npm install
npx vite                # Runs on port 5173
```

Open http://localhost:5173 in browser.
