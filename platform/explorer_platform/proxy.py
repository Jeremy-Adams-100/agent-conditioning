"""Data proxy endpoints — forward requests to VM agent and return responses."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from explorer_platform.deps import get_current_user
from explorer_platform.vm_client import get_vm_client

router = APIRouter(prefix="/api/data", tags=["data"])


def _handle_vm_error(e: httpx.HTTPStatusError):
    raise HTTPException(502, f"VM agent error: {e.response.status_code}")


@router.get("/status")
async def proxy_status(user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.get_status()
    except httpx.HTTPStatusError as e:
        _handle_vm_error(e)


@router.get("/sessions")
async def proxy_sessions(query: str = None, limit: int = 20,
                         user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.list_sessions(query, limit)
    except httpx.HTTPStatusError as e:
        _handle_vm_error(e)


@router.get("/sessions/{session_id}")
async def proxy_session(session_id: str, user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.get_session(session_id)
    except httpx.HTTPStatusError as e:
        _handle_vm_error(e)


@router.get("/files")
async def proxy_files(user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.list_files()
    except httpx.HTTPStatusError as e:
        _handle_vm_error(e)


@router.get("/files/{path:path}")
async def proxy_file(path: str, user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.get_file(path)
    except httpx.HTTPStatusError as e:
        _handle_vm_error(e)
