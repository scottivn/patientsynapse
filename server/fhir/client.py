"""Base FHIR R4 HTTP client for eClinicalWorks."""

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

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.auth.settings.ecw_fhir_base_url,
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
        resp = await client.get(f"/{resource_type}", params=params or {}, headers=headers)
        resp.raise_for_status()
        logger.info(f"FHIR SEARCH {resource_type} params={params} -> {resp.status_code}")
        return resp.json()

    async def create(self, resource_type: str, resource: dict) -> dict:
        """POST /ResourceType -> create resource"""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.post(f"/{resource_type}", json=resource, headers=headers)
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
