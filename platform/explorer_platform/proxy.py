"""Data proxy endpoints — forward requests to VM agent and return responses.

Returns graceful defaults when VM agent is unreachable (mock mode,
VM suspended, or not yet provisioned).
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from explorer_platform.deps import get_current_user
from explorer_platform.vm_client import get_vm_client

router = APIRouter(prefix="/api/data", tags=["data"])

# Default response when VM is unreachable
_DEFAULT_STATUS = {"exploration_running": False, "status_md": "", "state": None}


@router.get("/status")
async def proxy_status(user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.get_status()
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException, httpx.HTTPStatusError):
        return _DEFAULT_STATUS


@router.get("/sessions")
async def proxy_sessions(query: str = None, limit: int = 20,
                         user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.list_sessions(query, limit)
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException, httpx.HTTPStatusError):
        return []


@router.get("/sessions/{session_id}")
async def proxy_session(session_id: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.get_session(session_id)
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "Session not available")


@router.get("/files")
async def proxy_files(user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.list_files()
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException, httpx.HTTPStatusError):
        return []


@router.get("/files/{path:path}")
async def proxy_file(path: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.get_file(path)
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "File not available")
