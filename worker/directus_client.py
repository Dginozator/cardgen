"""Directus REST API client for the worker."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import DIRECTUS_TOKEN, DIRECTUS_URL

logger = logging.getLogger(__name__)


class DirectusClient:
    """Thin wrapper over Directus REST API."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or DIRECTUS_URL).rstrip("/")
        self.token = token or DIRECTUS_TOKEN

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def _request(
        self, method: str, path: str, *, json: Any = None, params: dict | None = None, content: bytes | None = None, headers: dict | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        hdrs = self._headers()
        if headers:
            hdrs.update(headers)

        # Tag generation_tasks requests for easy filtering
        tag = "[GENERATION_TASKS] " if "/items/generation_tasks" in path else ""

        logger.info(
            "%s%s %s | params=%s | payload=%s",
            tag, method, url, params, json,
        )

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.request(method, url, headers=hdrs, json=json, params=params, content=content)
                elapsed = time.perf_counter() - t0
                logger.info(
                    "%s%s %s -> %s (%d bytes) in %.3fs",
                    tag, method, url, resp.status_code, len(resp.content), elapsed,
                )
                resp.raise_for_status()
                if not resp.content:
                    return None
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    return data["data"]
                return data
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.error(
                "%s%s %s FAILED in %.3fs: %s",
                tag, method, url, elapsed, exc,
            )
            raise

    # --- Templates ---

    async def get_templates(self, *, is_active: bool = True) -> list[dict]:
        params: dict[str, Any] = {"sort": "sort,name"}
        if is_active:
            params["filter"] = '{"is_active":{"_eq":true}}'
        return await self._request("GET", "/items/templates", params=params)

    async def get_me(self) -> dict:
        """Return current user info (id, email, etc.) for the active token."""
        return await self._request("GET", "/users/me?fields=id,email")

    async def get_template(self, template_id: str) -> dict:
        return await self._request("GET", f"/items/templates/{template_id}")

    async def update_template(self, template_id: str, payload: dict) -> dict:
        return await self._request("PATCH", f"/items/templates/{template_id}", json=payload)

    async def create_template(self, payload: dict) -> dict:
        return await self._request("POST", "/items/templates", json=payload)

    async def delete_template(self, template_id: str) -> None:
        await self._request("DELETE", f"/items/templates/{template_id}")

    # --- Generation Tasks ---

    async def create_task(self, payload: dict) -> dict:
        return await self._request("POST", "/items/generation_tasks", json=payload)

    async def get_task(self, task_id: str) -> dict:
        return await self._request("GET", f"/items/generation_tasks/{task_id}")

    async def update_task(self, task_id: str, payload: dict) -> dict:
        return await self._request("PATCH", f"/items/generation_tasks/{task_id}", json=payload)

    # --- Files ---

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/png") -> dict:
        """Upload a file to Directus and return the file record."""
        url = f"{self.base_url}/files"
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers=headers,
                files={"file": (filename, file_bytes, content_type)},
                data={"title": filename},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", data)

    async def download_file(self, file_id: str) -> bytes:
        """Download a file asset from Directus."""
        url = f"{self.base_url}/assets/{file_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.content