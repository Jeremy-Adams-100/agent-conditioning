"""HTTP client for communicating with VM agents."""

import httpx
from fastapi import HTTPException

from explorer_platform import config


class VMClient:
    """Async HTTP client for a single VM agent."""

    def __init__(self, base_url: str, token: str):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def start(self, topic: str) -> dict:
        r = await self._client.post("/start", json={"topic": topic})
        r.raise_for_status()
        return r.json()

    async def stop(self) -> dict:
        r = await self._client.post("/stop")
        r.raise_for_status()
        return r.json()

    async def clear(self) -> dict:
        r = await self._client.post("/clear")
        r.raise_for_status()
        return r.json()

    async def guide(self, text: str) -> dict:
        r = await self._client.post("/guide", json={"text": text})
        r.raise_for_status()
        return r.json()

    async def get_status(self) -> dict:
        r = await self._client.get("/status")
        r.raise_for_status()
        return r.json()

    async def get_print_output(self, lines: int = 50) -> dict:
        r = await self._client.get("/print", params={"lines": lines})
        r.raise_for_status()
        return r.json()

    async def list_files(self) -> list:
        r = await self._client.get("/files")
        r.raise_for_status()
        return r.json()

    async def get_file(self, path: str) -> dict:
        r = await self._client.get(f"/files/{path}")
        r.raise_for_status()
        return r.json()

    async def download_file(self, path: str) -> httpx.Response:
        r = await self._client.get(f"/files/{path}/download")
        r.raise_for_status()
        return r

    async def list_sessions(self, query: str | None = None, limit: int = 20) -> list:
        params = {"limit": limit}
        if query:
            params["query"] = query
        r = await self._client.get("/sessions", params=params)
        r.raise_for_status()
        return r.json()

    async def get_session(self, session_id: str) -> dict:
        r = await self._client.get(f"/sessions/{session_id}")
        r.raise_for_status()
        return r.json()

    # --- Interact agent ---

    async def interact_query(self, prompt: str) -> dict:
        r = await self._client.post(
            "/interact/query", json={"prompt": prompt}, timeout=3600.0,
        )
        r.raise_for_status()
        return r.json()

    async def interact_clear(self) -> dict:
        r = await self._client.post("/interact/clear")
        r.raise_for_status()
        return r.json()

    async def interact_list_files(self) -> list:
        r = await self._client.get("/interact/files")
        r.raise_for_status()
        return r.json()

    async def interact_get_file(self, path: str) -> dict:
        r = await self._client.get(f"/interact/files/{path}")
        r.raise_for_status()
        return r.json()

    async def interact_download_file(self, path: str) -> httpx.Response:
        r = await self._client.get(f"/interact/files/{path}/download")
        r.raise_for_status()
        return r

    # --- Share packages ---

    async def share_install(self, package_url: str, topic_dir: str) -> dict:
        r = await self._client.post(
            "/share/install",
            json={"package_url": package_url, "topic_dir": topic_dir},
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()

    async def share_reset(self, topic_dir: str) -> dict:
        r = await self._client.post("/share/reset", json={"topic_dir": topic_dir})
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self._client.aclose()


def get_vm_client(user: dict) -> VMClient:
    """Build a VMClient from user dict. Raises 409 if VM not provisioned."""
    ip = user.get("vm_internal_ip")
    token = user.get("vm_agent_token")
    if not ip or not token:
        raise HTTPException(409, "VM not provisioned")
    return VMClient(
        base_url=f"http://{ip}:{config.VM_AGENT_PORT}",
        token=token,
    )
