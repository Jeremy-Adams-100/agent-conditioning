"""VM Agent — lightweight HTTP server running on each user's VM.

Exposes exploration control, interact chat, and file/session access over HTTP.
Secured with a bearer token. Runs standalone via uvicorn.

Usage:
    VM_AGENT_TOKEN=<token> DATA_DIR=<path> WORKING_DIR=<path> \
        uvicorn vm_agent.agent:app --port 8080
"""

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.responses import FileResponse

app = FastAPI(title="VM Agent")

TOKEN = os.environ.get("VM_AGENT_TOKEN", "")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/home/explorer/data"))
WORKING_DIR = Path(os.environ.get("WORKING_DIR", "/home/explorer/working"))
EXPLORATION_CMD = os.environ.get("EXPLORATION_CMD", "python -m agent.exploration")
WOLFRAM_PATH = os.environ.get("WOLFRAM_PATH", "/usr/local/bin/wolfram")
INTERACT_WORKSPACE = Path(os.environ.get(
    "INTERACT_WORKSPACE", str(Path(WORKING_DIR).parent / "interact")))
INTERACT_SESSION_FILE = DATA_DIR / "interact_session_id"

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
    # Clear stale signal files so the new process doesn't exit immediately
    for sig in ("exploration.stop", "exploration.clear", "exploration.guide"):
        sig_path = DATA_DIR / sig
        if sig_path.exists():
            sig_path.unlink(missing_ok=True)
    # Run from parent of DATA_DIR (project root on VM, or agent-conditioning locally)
    cwd = os.environ.get("PROJECT_ROOT", str(DATA_DIR.parent))
    _proc = subprocess.Popen(cmd, cwd=cwd)
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


@app.post("/guide")
def guide(body: dict, _=Depends(_auth)):
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "No guidance text provided")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "exploration.guide").write_text(text)
    return {"status": "guidance_queued"}


@app.get("/detect-tier")
def detect_tier(_=Depends(_auth)):
    """Test if the user's Claude account supports opus (Max plan)."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", "opus", "--no-session-persistence"],
            input="Say ok",
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return {"tier": "max"}
    except (subprocess.TimeoutExpired, OSError):
        pass
    return {"tier": "free"}


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


@app.get("/files/{path:path}/download")
def download_file(path: str, _=Depends(_auth)):
    full = (WORKING_DIR / path).resolve()
    if not full.is_file() or not full.is_relative_to(WORKING_DIR.resolve()):
        raise HTTPException(404, "File not found")
    return FileResponse(full, filename=full.name)


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


# ---------------------------------------------------------------------------
# Interact agent — independent chat session
# ---------------------------------------------------------------------------

def _save_interact_log(prompt: str, response: str) -> None:
    now = datetime.now(timezone.utc)
    log_dir = INTERACT_WORKSPACE / "logs" / now.strftime("%Y-%m-%d")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{now.strftime('%H%M%S')}.md"
    log_path.write_text(f"# Query\n\n{prompt}\n\n# Response\n\n{response}\n")


def _build_interact_tools() -> list[str]:
    """Build --allowedTools flags for the interact agent.

    Write/Edit are unscoped (CWD enforcement prevents writes outside the
    interact workspace). Read/Glob/Grep are unscoped to allow reading
    both the explorer and interact workspaces. Bash is restricted to
    wolfram + pandoc only.

    Note: path-scoped --allowedTools (e.g. Write(//path/**)) does NOT
    auto-approve in -p mode — only unscoped tool names do. CWD-based
    enforcement is the effective workspace isolation mechanism.
    """
    return [
        "Read", "Write", "Edit", "Glob", "Grep",
        f"Bash({WOLFRAM_PATH} *)", "Bash(pandoc *)", "WebSearch",
    ]


def _build_interact_system_prompt() -> str:
    return (
        "You are an interactive research assistant on the Q.E.D. platform.\n\n"
        "WORKSPACES:\n"
        f"- Explorer workspace: {WORKING_DIR} (READ ONLY — do not modify)\n"
        "  Contains scripts, libraries, and data from the autonomous exploration cycle.\n"
        f"- Your workspace: {INTERACT_WORKSPACE} (read/write)\n"
        "  Save all your files here — scripts, data, reports, figures.\n\n"
        "TOOLS:\n"
        f"- Wolfram Language: write .wls scripts to your workspace, run with {WOLFRAM_PATH}\n"
        "- pandoc + tectonic for PDF reports:\n"
        "    pandoc file.md -o file.pdf --pdf-engine=tectonic -V geometry:margin=1in\n"
        "- WebSearch for looking things up\n\n"
        "Be helpful and concise. Show your work. When running computations,\n"
        "explain what you're doing and what the results mean."
    )


@app.post("/interact/query")
def interact_query(body: dict, _=Depends(_auth)):
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "No prompt provided")

    INTERACT_WORKSPACE.mkdir(parents=True, exist_ok=True)

    # Session: resume or create
    cmd = ["claude", "-p", "--output-format", "json", "--model", "opus"]

    if INTERACT_SESSION_FILE.exists():
        session_id = INTERACT_SESSION_FILE.read_text().strip()
        cmd.extend(["--resume", session_id])
    else:
        session_id = str(uuid.uuid4())
        INTERACT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        INTERACT_SESSION_FILE.write_text(session_id)
        cmd.extend(["--session-id", session_id])
        cmd.extend(["--system-prompt", _build_interact_system_prompt()])

    # Tool permissions
    for tool in _build_interact_tools():
        cmd.extend(["--allowedTools", tool])

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=600, cwd=str(INTERACT_WORKSPACE), env=env,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "message": "Query timed out after 10 minutes."}

    if proc.returncode != 0:
        # Session is likely dead — delete so next query starts fresh
        INTERACT_SESSION_FILE.unlink(missing_ok=True)
        return {
            "error": "agent_error",
            "message": proc.stderr[:500] if proc.stderr else "Agent returned an error.",
        }

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "parse_error", "message": "Failed to parse agent response."}

    result_text = envelope.get("result", "")
    usage = envelope.get("usage", {})

    _save_interact_log(prompt, result_text)

    # Context warning: flag when approaching the context window limit
    total_ctx = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("output_tokens", 0)
    )
    # Context window depends on tier (200k free, 1M max); use model usage if available
    model_usage = usage.get("modelUsage", {})
    context_window = 200_000
    for model_info in model_usage.values():
        if isinstance(model_info, dict) and model_info.get("contextWindow"):
            context_window = model_info["contextWindow"]
            break
    context_pct = total_ctx / context_window if context_window else 0
    context_warning = None
    if context_pct >= 0.80:
        context_warning = (
            f"Context is {context_pct:.0%} full ({total_ctx:,} / {context_window:,} tokens). "
            "Click Clear to start a new session before context runs out."
        )

    return {
        "result": result_text, "usage": usage, "session_id": session_id,
        "context_warning": context_warning,
    }


@app.post("/interact/clear")
def interact_clear(_=Depends(_auth)):
    """Clear the interact session. Deletes session ID only — workspace files
    (logs, scripts, reports) are preserved so users retain their work."""
    INTERACT_SESSION_FILE.unlink(missing_ok=True)
    return {"status": "cleared"}


@app.get("/interact/files")
def interact_list_files(_=Depends(_auth)):
    INTERACT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(INTERACT_WORKSPACE.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
                files.append({
                    "path": str(p.relative_to(INTERACT_WORKSPACE)),
                    "size": st.st_size,
                    "modified": st.st_mtime,
                })
            except OSError:
                pass
    return files


@app.get("/interact/files/{path:path}/download")
def interact_download_file(path: str, _=Depends(_auth)):
    full = (INTERACT_WORKSPACE / path).resolve()
    if not full.is_file() or not full.is_relative_to(INTERACT_WORKSPACE.resolve()):
        raise HTTPException(404, "File not found")
    return FileResponse(full, filename=full.name)


@app.get("/interact/files/{path:path}")
def interact_get_file(path: str, _=Depends(_auth)):
    full = (INTERACT_WORKSPACE / path).resolve()
    if not full.is_file() or not full.is_relative_to(INTERACT_WORKSPACE.resolve()):
        raise HTTPException(404, "File not found")
    try:
        return {"path": path, "content": full.read_text(errors="replace")}
    except OSError:
        raise HTTPException(500, "Could not read file")
