"""Data proxy endpoints — forward requests to VM agent and return responses.

Returns graceful defaults when VM agent is unreachable (mock mode,
VM suspended, or not yet provisioned).
"""

from io import BytesIO

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

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


@router.get("/print")
async def proxy_print(user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.get_print_output()
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException, httpx.HTTPStatusError):
        return {"lines": [], "running": False}


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


@router.get("/files/{path:path}/download")
async def proxy_file_download(path: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        r = await client.download_file(path)
        return StreamingResponse(
            BytesIO(r.content),
            media_type=r.headers.get("content-type", "application/octet-stream"),
            headers={
                "content-disposition": r.headers.get(
                    "content-disposition", f'attachment; filename="{path.split("/")[-1]}"'
                ),
            },
        )
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "File not available")


@router.get("/files/{path:path}")
async def proxy_file(path: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.get_file(path)
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "File not available")
