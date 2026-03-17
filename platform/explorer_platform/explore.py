"""Exploration control endpoints: start, stop, clear, resume."""

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from explorer_platform import gcp
from explorer_platform.db import update_user_field
from explorer_platform.deps import get_current_user, get_db
from explorer_platform.vm_client import VMClient, get_vm_client

router = APIRouter(prefix="/api/explore", tags=["explore"])


class StartRequest(BaseModel):
    topic: str = ""


async def _ensure_vm_running(user: dict, conn) -> None:
    """Resume VM if suspended. Raises if VM not provisioned."""
    status = user.get("vm_status", "none")
    if status == "none":
        raise HTTPException(409, "VM not provisioned yet. Complete onboarding first.")
    if status == "provisioning":
        raise HTTPException(409, "VM still provisioning. Please wait.")
    if status == "provision_failed":
        raise HTTPException(409, "VM provisioning failed. Contact support.")

    if status == "suspended":
        await gcp.resume_vm(user["vm_zone"], user["vm_id"])
        # Poll until agent responds
        client = get_vm_client(user)
        for _ in range(15):
            try:
                await client.get_status()
                update_user_field(conn, user["id"], "vm_status", "running")
                return
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
                await asyncio.sleep(2)
        raise HTTPException(504, "VM resumed but agent not responding")


@router.post("/start")
async def start_exploration(body: StartRequest, user=Depends(get_current_user),
                            conn=Depends(get_db)):
    await _ensure_vm_running(user, conn)
    client = get_vm_client(user)
    try:
        result = await client.start(body.topic)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"VM agent error: {e.response.status_code}")
    update_user_field(conn, user["id"], "vm_status", "running")
    return result


@router.post("/stop")
async def stop_exploration(user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.stop()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"VM agent error: {e.response.status_code}")


@router.post("/clear")
async def clear_exploration(user=Depends(get_current_user)):
    client = get_vm_client(user)
    try:
        return await client.clear()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"VM agent error: {e.response.status_code}")


@router.post("/resume")
async def resume_exploration(user=Depends(get_current_user), conn=Depends(get_db)):
    await _ensure_vm_running(user, conn)
    client = get_vm_client(user)
    try:
        result = await client.start("")  # empty topic = resume
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"VM agent error: {e.response.status_code}")
    update_user_field(conn, user["id"], "vm_status", "running")
    return result
