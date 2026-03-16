"""VM Agent — lightweight HTTP server running on each user's VM.

Exposes exploration control and file/session access over HTTP.
Secured with a bearer token. Runs standalone via uvicorn.

Usage:
    VM_AGENT_TOKEN=<token> DATA_DIR=<path> WORKING_DIR=<path> \
        uvicorn vm_agent.agent:app --port 8080
"""

import json
import os
import subprocess
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Header

app = FastAPI(title="VM Agent")

TOKEN = os.environ.get("VM_AGENT_TOKEN", "")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/home/explorer/data"))
WORKING_DIR = Path(os.environ.get("WORKING_DIR", "/home/explorer/working"))
EXPLORATION_CMD = os.environ.get("EXPLORATION_CMD", "python -m agent.exploration")

_proc: subprocess.Popen | None = None


def _auth(authorization: str = Header(default="")):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Unauthorized")


@app.post("/start")
def start(body: dict, _=Depends(_auth)):
    global _proc
    topic = body.get("topic", "").strip()
    cmd = EXPLORATION_CMD.split() + ["start"]
    if topic:
        cmd.append(topic)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    _proc = subprocess.Popen(cmd, cwd=str(DATA_DIR.parent))
    return {"status": "starting", "pid": _proc.pid}


@app.post("/stop")
def stop(_=Depends(_auth)):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "exploration.stop").write_text("")
    return {"status": "stopping"}


@app.post("/clear")
def clear(_=Depends(_auth)):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "exploration.clear").write_text("")
    return {"status": "clearing"}


@app.get("/status")
def status(_=Depends(_auth)):
    result: dict = {"exploration_running": _proc is not None and _proc.poll() is None}

    status_path = DATA_DIR / "exploration_status.md"
    if status_path.exists():
        result["status_md"] = status_path.read_text()

    state_path = DATA_DIR / "exploration_state.json"
    if state_path.exists():
        try:
            result["state"] = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    return result


@app.get("/files")
def list_files(_=Depends(_auth)):
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(WORKING_DIR.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
                files.append({
                    "path": str(p.relative_to(WORKING_DIR)),
                    "size": st.st_size,
                    "modified": st.st_mtime,
                })
            except OSError:
                pass
    return files


@app.get("/files/{path:path}")
def get_file(path: str, _=Depends(_auth)):
    full = (WORKING_DIR / path).resolve()
    if not full.is_file() or not full.is_relative_to(WORKING_DIR.resolve()):
        raise HTTPException(404, "File not found")
    try:
        return {"path": path, "content": full.read_text(errors="replace")}
    except OSError:
        raise HTTPException(500, "Could not read file")


@app.get("/sessions")
def list_sessions(query: str = None, limit: int = 20, _=Depends(_auth)):
    db_path = DATA_DIR / "sessions.db"
    if not db_path.exists():
        return []
    from auto_compact.db import init_db, search_sessions, list_session_catalog
    conn = init_db(db_path)
    try:
        if query:
            return search_sessions(conn, query, min(limit, 50))
        return list_session_catalog(conn, limit=min(limit, 50))
    finally:
        conn.close()


@app.get("/sessions/{session_id}")
def get_session(session_id: str, _=Depends(_auth)):
    db_path = DATA_DIR / "sessions.db"
    if not db_path.exists():
        raise HTTPException(404, "No sessions database")
    from auto_compact.db import init_db, get_session_by_id
    conn = init_db(db_path)
    try:
        s = get_session_by_id(conn, session_id)
        if not s:
            raise HTTPException(404, "Session not found")
        return dict(s)
    finally:
        conn.close()
