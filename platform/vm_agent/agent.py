"""VM Agent — lightweight HTTP server running on each user's VM.

Exposes exploration control, interact chat, and file/session access over HTTP.
Secured with a bearer token. Runs standalone via uvicorn.

Usage:
    VM_AGENT_TOKEN=<token> DATA_DIR=<path> WORKING_DIR=<path> \
        uvicorn vm_agent.agent:app --port 8080
"""

import json
import os
import shutil
import subprocess
import tarfile
import uuid
import urllib.request
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
INTERACT_MODEL = os.environ.get("INTERACT_MODEL", "sonnet")

_proc: subprocess.Popen | None = None
_log_file = None  # open file handle for exploration stdout/stderr


def _auth(authorization: str = Header(default="")):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Unauthorized")


@app.post("/start")
def start(body: dict, _=Depends(_auth)):
    global _proc, _log_file
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
    # Close previous log file if any
    if _log_file:
        try:
            _log_file.close()
        except OSError:
            pass
    # Redirect exploration stdout/stderr to log file for the Print panel
    _log_file = open(DATA_DIR / "exploration.log", "w")
    # Run from parent of DATA_DIR (project root on VM, or agent-conditioning locally)
    cwd = os.environ.get("PROJECT_ROOT", str(DATA_DIR.parent))
    _proc = subprocess.Popen(cmd, cwd=cwd, stdout=_log_file, stderr=_log_file)
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


@app.get("/print")
def get_print(lines: int = 50, _=Depends(_auth)):
    """Return the last N lines of the exploration log for the Print panel."""
    log_path = DATA_DIR / "exploration.log"
    if not log_path.exists():
        return {"lines": [], "running": False}
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return {"lines": [], "running": False}
    tail = text.split("\n")[-lines:]
    running = _proc is not None and _proc.poll() is None
    return {"lines": tail, "running": running}


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

def _today_dir() -> Path:
    """Return today's date directory, creating logs/scripts/figures subdirs."""
    day = INTERACT_WORKSPACE / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for sub in ("logs", "scripts", "figures"):
        (day / sub).mkdir(parents=True, exist_ok=True)
    return day


def _save_interact_log(session_id: str, prompt: str, response: str) -> None:
    """Append Q&A to the session log (.md only, no PDF rendering)."""
    now = datetime.now(timezone.utc)
    log_dir = _today_dir() / "logs"
    short_id = session_id[:8]
    md_path = log_dir / f"session_{short_id}.md"
    entry = (
        f"## Q ({now.strftime('%H:%M:%S')})\n\n{prompt}\n\n"
        f"## A\n\n{response}\n\n---\n\n"
    )
    with open(md_path, "a") as f:
        f.write(entry)


def _cleanup_old_interactions(max_age_days: int = 30) -> None:
    """Delete interact workspace folders older than max_age_days."""
    if not INTERACT_WORKSPACE.exists():
        return
    cutoff = datetime.now(timezone.utc).date() - __import__("datetime").timedelta(days=max_age_days)
    for item in INTERACT_WORKSPACE.iterdir():
        if not item.is_dir():
            continue
        try:
            folder_date = datetime.strptime(item.name, "%Y-%m-%d").date()
            if folder_date < cutoff:
                import shutil
                shutil.rmtree(item, ignore_errors=True)
        except ValueError:
            pass  # not a date-named folder


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
        f"Bash({WOLFRAM_PATH} *)",
        "Bash(wolfram *)",
        "Bash(wolframscript *)",
        "Bash(pandoc *)",
        "WebSearch",
    ]


def _build_interact_system_prompt() -> str:
    return (
        "<role>\n"
        "You run Wolfram Language computations and generate figures for users.\n"
        "You are fast, concise, and action-oriented. Do the work, show the result.\n"
        "</role>\n\n"
        "<tools pre-approved=\"true\">\n"
        "All tools below are pre-approved. Use them directly. Never ask for permission.\n\n"
        f"Wolfram:  Write a .wls script, then run: {WOLFRAM_PATH} -script <file.wls>\n"
        "Pandoc:   pandoc file.md -o file.pdf --pdf-engine=tectonic -V geometry:margin=1in\n"
        "Files:    Read, Write, Edit, Glob, Grep — all pre-approved.\n"
        "Web:      WebSearch for lookups.\n"
        "</tools>\n\n"
        "<workspace>\n"
        f"Your workspace: {INTERACT_WORKSPACE} (read/write)\n"
        f"Explorer data:  {WORKING_DIR} (read-only reference)\n\n"
        "File structure — use today's date folder:\n"
        "  YYYY-MM-DD/scripts/  for .wls scripts\n"
        "  YYYY-MM-DD/figures/  for .png figures\n"
        "  YYYY-MM-DD/logs/     auto-managed (do not write here)\n"
        "</workspace>\n\n"
        "<figures>\n"
        "Static PNGs only: Export[\"name.png\", plot, ImageResolution -> 150]\n"
        "No Manipulate, Dynamic, or interactive graphics.\n"
        "1-5 figures per request. Validate symbol rendering.\n"
        "</figures>\n\n"
        "<budget>\n"
        "Do not restate the question. Do not list steps. Just act.\n"
        "One script per request. Summarize large outputs.\n"
        "If too complex, reduce scope and say so.\n"
        "</budget>"
    )


def _build_interact_cmd(session_id: str, is_resume: bool) -> list[str]:
    """Build the claude CLI command for an interact query."""
    cmd = ["claude", "-p", "--output-format", "json",
           "--model", INTERACT_MODEL, "--effort", "high"]
    if is_resume:
        cmd.extend(["--resume", session_id])
    else:
        cmd.extend(["--session-id", session_id])
        cmd.extend(["--system-prompt", _build_interact_system_prompt()])
    for tool in _build_interact_tools():
        cmd.extend(["--allowedTools", tool])
    return cmd


@app.post("/interact/query")
def interact_query(body: dict, _=Depends(_auth)):
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "No prompt provided")

    INTERACT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    _cleanup_old_interactions()

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    run_kwargs = dict(
        input=prompt, capture_output=True, text=True,
        timeout=3600, cwd=str(INTERACT_WORKSPACE), env=env,
    )

    # Session: resume existing or create new
    is_resume = INTERACT_SESSION_FILE.exists()
    if is_resume:
        session_id = INTERACT_SESSION_FILE.read_text().strip()
    else:
        session_id = str(uuid.uuid4())
        INTERACT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        INTERACT_SESSION_FILE.write_text(session_id)

    try:
        proc = subprocess.run(
            _build_interact_cmd(session_id, is_resume), **run_kwargs,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "message": "Query timed out."}

    # If resume failed (stale/dead session), retry once with a fresh session
    if proc.returncode != 0 and is_resume:
        INTERACT_SESSION_FILE.unlink(missing_ok=True)
        session_id = str(uuid.uuid4())
        INTERACT_SESSION_FILE.write_text(session_id)
        try:
            proc = subprocess.run(
                _build_interact_cmd(session_id, False), **run_kwargs,
            )
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "message": "Query timed out."}

    if proc.returncode != 0:
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

    _save_interact_log(session_id, prompt, result_text)

    # Context warning: flag when approaching the context window limit
    total_ctx = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("output_tokens", 0)
    )
    # Read context window from modelUsage (top-level envelope, not inside usage)
    model_usage = envelope.get("modelUsage", {})
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


# ---------------------------------------------------------------------------
# Share — package install/reset
# ---------------------------------------------------------------------------

@app.post("/share/install")
def share_install(body: dict, _=Depends(_auth)):
    """Download and extract a package into the explorer workspace."""
    package_url = body.get("package_url", "")
    topic_dir = body.get("topic_dir", "")
    if not package_url or not topic_dir:
        raise HTTPException(400, "Missing package_url or topic_dir")
    # Validate topic_dir is a simple name
    if "/" in topic_dir or ".." in topic_dir:
        raise HTTPException(400, "Invalid topic_dir")
    target = WORKING_DIR / topic_dir
    if target.exists():
        raise HTTPException(409, "Already installed")
    # Download tarball to temp file
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = WORKING_DIR / f"_pkg_{uuid.uuid4().hex[:8]}.tar.gz"
    try:
        # Download with 60s timeout (prevents hanging on unreachable URLs)
        req = urllib.request.urlopen(package_url, timeout=60)
        with open(tmp_path, "wb") as f:
            f.write(req.read())
        # Extract with safety check
        with tarfile.open(str(tmp_path), "r:gz") as tf:
            for member in tf.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    raise HTTPException(400, "Package contains unsafe paths")
            tf.extractall(path=str(WORKING_DIR))
        # Set timestamps to install time so files appear under today's date
        now = datetime.now(timezone.utc).timestamp()
        for p in target.rglob("*"):
            try:
                os.utime(p, (now, now))
            except OSError:
                pass
        return {"status": "installed", "topic_dir": topic_dir}
    except HTTPException:
        raise
    except Exception as e:
        # Clean up partial extraction
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(500, f"Install failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/share/reset")
def share_reset(body: dict, _=Depends(_auth)):
    """Remove an installed package from the explorer workspace."""
    topic_dir = body.get("topic_dir", "")
    if not topic_dir or "/" in topic_dir or ".." in topic_dir:
        raise HTTPException(400, "Invalid topic_dir")
    target = WORKING_DIR / topic_dir
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, "Not installed")
    shutil.rmtree(target)
    return {"status": "removed", "topic_dir": topic_dir}
