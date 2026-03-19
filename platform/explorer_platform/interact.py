"""Interact agent endpoints: query, clear, and file access."""

from io import BytesIO

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from explorer_platform.deps import get_current_user, get_db
from explorer_platform.explore import _ensure_vm_running
from explorer_platform.vm_client import get_vm_client

router = APIRouter(prefix="/api/interact", tags=["interact"])


class QueryRequest(BaseModel):
    prompt: str = ""


@router.post("/query")
async def interact_query(body: QueryRequest, user=Depends(get_current_user),
                         conn=Depends(get_db)):
    await _ensure_vm_running(user, conn)
    client = get_vm_client(user)
    try:
        return await client.interact_query(body.prompt)
    except httpx.TimeoutException:
        return {"error": "timeout", "message": "Query timed out."}
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(502, "VM agent unreachable")


@router.post("/clear")
async def interact_clear(user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.interact_clear()
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ConnectTimeout):
        return {"status": "no_vm"}


@router.get("/files")
async def interact_files(user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.interact_list_files()
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException, httpx.HTTPStatusError):
        return []


@router.get("/files/{path:path}/download")
async def interact_file_download(path: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        r = await client.interact_download_file(path)
        return StreamingResponse(
            BytesIO(r.content),
            media_type=r.headers.get("content-type", "application/octet-stream"),
            headers={
                "content-disposition": r.headers.get(
                    "content-disposition",
                    f'attachment; filename="{path.split("/")[-1]}"',
                ),
            },
        )
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "File not available")


@router.get("/files/{path:path}")
async def interact_file(path: str, user=Depends(get_current_user)):
    try:
        client = get_vm_client(user)
        return await client.interact_get_file(path)
    except (HTTPException, httpx.ConnectError, httpx.ConnectTimeout,
            httpx.TimeoutException):
        raise HTTPException(404, "File not available")
