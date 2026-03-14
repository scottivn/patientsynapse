"""PatientSynapse MCP Server — AI agent tools for Claude/LLM integration."""

import json
import logging
from mcp.server.fastmcp import FastMCP
from server.llm import get_llm
from server.llm.base import LLMMessage

logger = logging.getLogger(__name__)

mcp = FastMCP("PatientSynapse")


# ---- Referral Processing Tools ----

@mcp.tool()
async def extract_referral_data(fax_text: str) -> str:
    """Extract structured patient and referral data from fax text using AI.
    Returns JSON with patient demographics, referring provider, diagnosis codes, and urgency."""
    llm = get_llm()
    result = await llm.extract_referral_data(fax_text)
    return json.dumps(result, indent=2)


@mcp.tool()
async def classify_document(document_text: str) -> str:
    """Classify a fax document type (referral, lab_result, insurance_auth, medical_records, other)."""
    llm = get_llm()
    category = await llm.classify_document(document_text)
    return category


@mcp.tool()
async def summarize_referral(fax_text: str) -> str:
    """Provide a brief clinical summary of a referral fax for quick review."""
    llm = get_llm()
    messages = [
        LLMMessage(
            role="system",
            content="You are a medical assistant. Provide a brief 2-3 sentence summary of this referral fax, highlighting the patient name, referring provider, reason for referral, and urgency.",
        ),
        LLMMessage(role="user", content=fax_text),
    ]
    response = await llm.complete(messages, temperature=0.2, max_tokens=200)
    return response.content


# ---- Patient Tools ----

@mcp.tool()
async def search_patient(first_name: str, last_name: str, date_of_birth: str) -> str:
    """Search for a patient in eCW by name and date of birth.
    date_of_birth format: YYYY-MM-DD.
    Returns matching patient records or empty list."""
    # Requires active FHIR client — will be wired via app state
    return json.dumps({
        "status": "not_connected",
        "message": "FHIR client not initialized. Complete OAuth flow first.",
        "search_params": {"first_name": first_name, "last_name": last_name, "dob": date_of_birth},
    })


@mcp.tool()
async def get_patient_summary(patient_id: str) -> str:
    """Get a summary of a patient including demographics, conditions, and insurance."""
    return json.dumps({
        "status": "not_connected",
        "message": "FHIR client not initialized. Complete OAuth flow first.",
        "patient_id": patient_id,
    })


# ---- Scheduling Tools ----

@mcp.tool()
async def find_available_providers(specialty: str) -> str:
    """Find providers by specialty for referral scheduling.
    Returns list of matching practitioners with their locations."""
    return json.dumps({
        "status": "not_connected",
        "message": "FHIR client not initialized. Complete OAuth flow first.",
        "specialty": specialty,
    })


@mcp.tool()
async def verify_patient_insurance(patient_id: str) -> str:
    """Verify a patient's insurance coverage status."""
    return json.dumps({
        "status": "not_connected",
        "message": "FHIR client not initialized. Complete OAuth flow first.",
        "patient_id": patient_id,
    })


# ---- RCM Tools ----

@mcp.tool()
async def get_patient_billing(patient_id: str) -> str:
    """Get billing context for a patient: encounters, diagnoses, procedures, insurance."""
    return json.dumps({
        "status": "not_connected",
        "message": "FHIR client not initialized. Complete OAuth flow first.",
        "patient_id": patient_id,
    })


@mcp.tool()
async def analyze_diagnosis_codes(fax_text: str) -> str:
    """Extract and validate ICD-10 diagnosis codes from referral text."""
    llm = get_llm()
    messages = [
        LLMMessage(
            role="system",
            content="""Extract all ICD-10 diagnosis codes from this referral text.
For each diagnosis mentioned, provide:
- The ICD-10-CM code
- The display name
- Whether it was explicitly stated or inferred
Return as JSON array: [{"code": "E11.9", "display": "Type 2 diabetes", "source": "explicit|inferred"}]
Return ONLY valid JSON.""",
        ),
        LLMMessage(role="user", content=fax_text),
    ]
    response = await llm.complete(messages, temperature=0.1, response_format="json_object")
    return response.content


# ---- System Tools ----

@mcp.tool()
async def check_system_status() -> str:
    """Check PatientSynapse system status: LLM provider, FHIR connection, and configuration."""
    from server.config import get_settings
    settings = get_settings()
    return json.dumps({
        "llm_provider": settings.llm_provider,
        "fhir_base_url": settings.ecw_fhir_base_url,
        "fhir_connected": False,  # Updated when OAuth completes
        "app_env": settings.app_env,
    }, indent=2)
