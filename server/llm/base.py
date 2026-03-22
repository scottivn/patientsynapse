"""Abstract base class for LLM providers. Plug-and-play architecture."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None  # prompt_tokens, completion_tokens


class LLMProvider(ABC):
    """Abstract LLM provider. Implement this to add a new LLM backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    async def extract_referral_data(self, text: str) -> dict:
        """Standard prompt for extracting data from a referral fax."""
        messages = [
            LLMMessage(
                role="system",
                content="""You are a medical document processor. Extract structured data from referral fax text.
Return a JSON object with these fields (use null for missing data):
{
    "patient": {
        "first_name": str,
        "last_name": str,
        "date_of_birth": "YYYY-MM-DD",
        "gender": "male|female|other",
        "phone": str,
        "address": {"line": str, "city": str, "state": str, "zip": str},
        "insurance_id": str,
        "insurance_name": str
    },
    "referral": {
        "referring_provider": str,
        "referring_practice": str,
        "referring_phone": str,
        "referring_fax": str,
        "reason": str,
        "diagnosis_codes": [{"code": "ICD-10 code", "display": str}],
        "urgency": "routine|urgent|stat",
        "notes": str
    }
}
Return ONLY valid JSON, no markdown or explanation.""",
            ),
            LLMMessage(role="user", content=f"Extract data from this referral fax:\n\n{text}"),
        ]
        response = await self.complete(messages, temperature=0.1, response_format="json_object")
        import json
        return json.loads(response.content)

    async def extract_prescription_data(self, text: str) -> dict:
        """Extract structured data from a DME prescription document."""
        messages = [
            LLMMessage(
                role="system",
                content="""You are a medical document processor specializing in DME (Durable Medical Equipment) prescriptions.
Extract structured data from the prescription text.
Return a JSON object with these fields (use null for missing data):
{
    "patient": {
        "first_name": str,
        "last_name": str,
        "date_of_birth": "YYYY-MM-DD",
        "phone": str
    },
    "prescriber": {
        "name": str,
        "npi": str,
        "practice": str,
        "phone": str,
        "fax": str
    },
    "diagnosis": {
        "code": "ICD-10 code",
        "description": str,
        "severity": "mild|moderate|severe" or null
    },
    "equipment": [
        {
            "description": str,
            "hcpcs_code": str or null,
            "category": str
        }
    ],
    "clinical": {
        "ahi": float or null,
        "pressure_settings": str or null,
        "compliance_note": str or null,
        "is_resupply": boolean,
        "notes": str or null
    }
}

For the equipment category field, use one of these exact values:
"CPAP Machine", "BiPAP / ASV Machine", "CPAP Mask — Full Face", "CPAP Mask — Nasal",
"CPAP Mask — Nasal Pillow", "Mask Cushion / Pillow Replacement", "Headgear",
"Heated Tubing", "Standard Tubing", "Water Chamber / Humidifier",
"Filters — Disposable", "Filters — Non-Disposable", "Other Sleep DME"

Return ONLY valid JSON, no markdown or explanation.""",
            ),
            LLMMessage(role="user", content=f"Extract data from this DME prescription:\n\n{text}"),
        ]
        response = await self.complete(messages, temperature=0.1, response_format="json_object")
        import json
        return json.loads(response.content)

    async def classify_document(self, text: str) -> str:
        """Classify a fax document type."""
        messages = [
            LLMMessage(
                role="system",
                content="""Classify this fax document into one of these categories:
- referral: A patient referral from another provider
- lab_result: Laboratory test results
- insurance_auth: Insurance authorization or pre-auth
- medical_records: Patient medical records request
- other: Anything else
Return ONLY the category name, nothing else.""",
            ),
            LLMMessage(role="user", content=text[:2000]),
        ]
        response = await self.complete(messages, temperature=0.0, max_tokens=20)
        return response.content.strip().lower()
