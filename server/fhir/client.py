"""Base FHIR R4 HTTP client — EMR-agnostic."""

import logging
import httpx
from typing import Optional, Any
from server.auth.smart import SMARTAuth

logger = logging.getLogger(__name__)


class FHIRClient:
    """Async FHIR R4 client with automatic token management."""

    def __init__(self, auth: SMARTAuth):
        self.auth = auth
        self._client: Optional[httpx.AsyncClient] = None
        self._default_search_params: dict = auth.emr.default_search_params

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.auth.emr.fhir_base_url,
                timeout=30.0,
            )
        return self._client

    async def _headers(self) -> dict:
        token = await self.auth.get_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }

    async def read(self, resource_type: str, resource_id: str) -> dict:
        """GET /ResourceType/id"""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.get(f"/{resource_type}/{resource_id}", headers=headers)
        resp.raise_for_status()
        logger.info(f"FHIR READ {resource_type}/{resource_id} -> {resp.status_code}")
        return resp.json()

    async def search(self, resource_type: str, params: Optional[dict] = None) -> dict:
        """GET /ResourceType?params -> Bundle"""
        client = await self._get_client()
        headers = await self._headers()
        merged = {**self._default_search_params, **(params or {})}
        resp = await client.get(f"/{resource_type}", params=merged, headers=headers)
        if not resp.is_success:
            logger.error(f"FHIR SEARCH {resource_type} failed -> {resp.status_code}: {resp.text[:200]}")
            # Return empty bundle on 403 (scope not granted) or 404 (resource type unsupported)
            # so callers degrade gracefully instead of crashing
            if resp.status_code in (400, 403, 404):
                return {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}
            resp.raise_for_status()
        logger.info(f"FHIR SEARCH {resource_type} -> {resp.status_code}")
        return resp.json()

    async def create(self, resource_type: str, resource: dict) -> dict:
        """POST /ResourceType -> create resource"""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.post(f"/{resource_type}", json=resource, headers=headers)
        if not resp.is_success:
            logger.error(f"FHIR CREATE {resource_type} failed -> {resp.status_code}")
        resp.raise_for_status()
        logger.info(f"FHIR CREATE {resource_type} -> {resp.status_code}")
        return resp.json()

    async def update(self, resource_type: str, resource_id: str, resource: dict) -> dict:
        """PUT /ResourceType/id -> update resource"""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.put(
            f"/{resource_type}/{resource_id}", json=resource, headers=headers
        )
        resp.raise_for_status()
        logger.info(f"FHIR UPDATE {resource_type}/{resource_id} -> {resp.status_code}")
        return resp.json()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
