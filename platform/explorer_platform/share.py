"""Share endpoints: list packages, install, reset, download, docs."""

import io
import json
import os
import tarfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from explorer_platform.deps import get_current_user, get_db
from explorer_platform.explore import _ensure_vm_running
from explorer_platform.vm_client import get_vm_client

router = APIRouter(prefix="/api/share", tags=["share"])

PACKAGES_DIR = Path(__file__).resolve().parent.parent / "packages"
PLATFORM_INTERNAL_URL = os.environ.get("PLATFORM_INTERNAL_URL", "http://127.0.0.1:8000")


def _load_manifest() -> list[dict]:
    manifest_path = PACKAGES_DIR / "packages.json"
    if not manifest_path.exists():
        return []
    try:
        return json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _find_package(package_id: str) -> dict:
    for pkg in _load_manifest():
        if pkg["id"] == package_id:
            return pkg
    raise HTTPException(404, f"Package not found: {package_id}")


class PackageRequest(BaseModel):
    package_id: str


@router.get("/packages")
async def list_packages():
    """List available packages. No auth required."""
    return _load_manifest()


@router.get("/download/{filename}")
async def download_package(filename: str):
    """Serve a package tarball. Called by VM agent during install."""
    filepath = (PACKAGES_DIR / filename).resolve()
    if not filepath.is_file() or not filepath.is_relative_to(PACKAGES_DIR.resolve()):
        raise HTTPException(404, "Package file not found")
    return FileResponse(filepath, filename=filename,
                        media_type="application/gzip")


@router.get("/docs/{package_id}/files")
async def list_package_docs(package_id: str):
    """List viewable files (.wls, .pdf, .md) in a package. No auth required."""
    pkg = _find_package(package_id)
    tarpath = PACKAGES_DIR / pkg["file"]
    if not tarpath.is_file():
        raise HTTPException(404, "Package file not found")
    viewable = (".wls", ".pdf", ".md")
    files = []
    with tarfile.open(str(tarpath), "r:gz") as tf:
        for member in tf.getmembers():
            if member.isfile() and any(member.name.endswith(ext) for ext in viewable):
                files.append({"path": member.name, "size": member.size})
    return files


@router.get("/docs/{package_id}/file/{path:path}")
async def get_package_doc(package_id: str, path: str):
    """Read a single file from a package tarball. No auth, no download."""
    pkg = _find_package(package_id)
    tarpath = PACKAGES_DIR / pkg["file"]
    if not tarpath.is_file():
        raise HTTPException(404, "Package file not found")
    # Validate path safety
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    with tarfile.open(str(tarpath), "r:gz") as tf:
        try:
            member = tf.getmember(path)
        except KeyError:
            raise HTTPException(404, "File not found in package")
        f = tf.extractfile(member)
        if f is None:
            raise HTTPException(404, "Not a regular file")
        data = f.read()
    # Return text for .wls/.md, binary for .pdf
    if path.endswith(".pdf"):
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": "inline"})
    return {"path": path, "content": data.decode("utf-8", errors="replace")}


@router.post("/install")
async def install_package(body: PackageRequest, user=Depends(get_current_user),
                          conn=Depends(get_db)):
    """Install a package onto the user's VM."""
    pkg = _find_package(body.package_id)
    await _ensure_vm_running(user, conn)
    client = get_vm_client(user)
    package_url = f"{PLATFORM_INTERNAL_URL}/api/share/download/{pkg['file']}"
    try:
        return await client.share_install(package_url, pkg["topic_dir"])
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            raise HTTPException(409, "Package already installed. Reset first to reinstall.")
        raise HTTPException(502, "VM agent error")
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(502, "VM agent unreachable")


@router.post("/reset")
async def reset_package(body: PackageRequest, user=Depends(get_current_user),
                        conn=Depends(get_db)):
    """Remove an installed package from the user's VM."""
    pkg = _find_package(body.package_id)
    await _ensure_vm_running(user, conn)
    client = get_vm_client(user)
    try:
        return await client.share_reset(pkg["topic_dir"])
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, "Package not installed")
        raise HTTPException(502, "VM agent error")
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(502, "VM agent unreachable")
