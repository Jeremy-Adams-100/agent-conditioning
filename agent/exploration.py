#!/usr/bin/env python3
"""Continuous Autonomous Exploration Conductor.

Runs a sequential three-agent loop (research → worker → audit) until
stopped via Ctrl+C or max_cycles reached. Each agent maintains a
persistent Claude Code session via --session-id / --resume, giving
continuous context across cycles without clearing.

Auto-compact integration: when an agent's context exceeds the compact
threshold, the session is compacted (summary generated, stored in
sessions.db, fresh session created with summary as bootstrap).

Control:
    Start:  python -m agent.exploration score.yaml
    Stop:   Ctrl+C  OR  touch data/exploration.stop
    Clear:  touch data/exploration.clear  (stops + clears context)
    Resume: python -m agent.exploration score.yaml
    Fresh:  python -m agent.exploration score.yaml --clear
"""

import argparse
import json
import os
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agent.conductor import (
    build_agent_config,
    build_agent_prompt,
    build_role_block,
    parse_outputs,
)
from agent.orchestrator import (
    assemble_system_prompt,
    build_allowed_tools_flags,
    generate_mcp_config,
    load_config,
)
from auto_compact.db import init_db, store_session

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_STATE_PATH = SCRIPT_DIR / "data" / "exploration_state.json"

# ---------------------------------------------------------------------------
# Graceful shutdown via SIGINT / SIGTERM / signal files
# ---------------------------------------------------------------------------

_stop_requested = False
_clear_requested = False


def _on_signal(signum, frame):
    global _stop_requested
    _stop_requested = True
    print("\n[exploration] Stop requested. Finishing current agent...", flush=True)


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


def _check_signal_files(data_dir: Path) -> None:
    """Check for stop/clear signal files. Sets global flags and removes files."""
    global _stop_requested, _clear_requested

    clear_file = data_dir / "exploration.clear"
    stop_file = data_dir / "exploration.stop"

    if clear_file.exists():
        clear_file.unlink()
        _stop_requested = True
        _clear_requested = True
        print("[exploration] Clear signal received.", flush=True)
    elif stop_file.exists():
        stop_file.unlink()
        _stop_requested = True
        print("[exploration] Stop signal received.", flush=True)


# ---------------------------------------------------------------------------
# Score loading
# ---------------------------------------------------------------------------


def load_exploration_score(path: str | Path) -> dict:
    """Load an exploration score YAML."""
    with open(path) as f:
        score = yaml.safe_load(f)
    for key in ("task", "agents", "flow"):
        if key not in score:
            raise ValueError(f"Exploration score missing required key: {key}")
    return score


# ---------------------------------------------------------------------------
# State persistence (stop / resume)
# ---------------------------------------------------------------------------


def save_state(path: Path, cycle: int, results: dict, failures: dict,
               last_session_id: str | None = None,
               agent_sessions: dict | None = None,
               agent_summaries: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "cycle": cycle,
        "results": results,
        "failures": failures,
        "last_session_id": last_session_id,
        "agent_sessions": agent_sessions or {},
        "agent_summaries": agent_summaries or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(state, indent=2, default=str))


def load_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _archive_state(state_path: Path) -> Path | None:
    """Copy current state file to a timestamped archive. Returns archive path."""
    if not state_path.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    archive = state_path.with_name(f"exploration_state_{ts}.json")
    try:
        archive.write_text(state_path.read_text())
        print(f"[exploration] Archived state: {archive.name}", flush=True)
        return archive
    except OSError as e:
        print(f"[exploration] Archive failed: {e}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Token usage helpers
# ---------------------------------------------------------------------------


def _total_context_tokens(usage: dict) -> int:
    """Compute total context from usage envelope (includes cached tokens)."""
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("output_tokens", 0)
    )


# ---------------------------------------------------------------------------
# Claude CLI with session persistence
# ---------------------------------------------------------------------------


COMPACTION_PROMPT = """\
[CONTEXT COMPACTION — do NOT produce your normal output format]

Your context window is approaching its limit. Produce a summary of \
everything you know and have done so far. This summary will bootstrap \
your context in a fresh session.

Include:
- Current state of the exploration (sub-topics explored, what's pending)
- Key findings, decisions, and their rationale
- Important constraints or issues discovered
- What you were working on and what should happen next
- Any critical facts that would be lost without this summary

Be thorough but concise. Write in plain text or markdown. \
Do NOT use [OUTPUT:] markers."""


def _call_exploration_agent(
    agent_name: str,
    agent_def: dict,
    task: str,
    config: dict,
    results: dict,
    score_inputs: dict,
    agent_sessions: dict,
    agent_summaries: dict,
) -> dict:
    """Call an agent with persistent session context.

    First call (no session): creates session via --session-id, sets system prompt.
    Subsequent calls: resumes session via --resume (context preserved).
    Post-compaction: creates new session with summary appended to system prompt.

    Returns dict matching run_agent() format:
        {status, outputs, usage, duration_ms, error}
    """
    agent_config = build_agent_config(config, agent_def)

    # Build user prompt (same format as conductor)
    user_prompt = build_agent_prompt(
        score_task=task,
        step_agent_name=agent_name,
        agent_def=agent_def,
        results=results,
        score_inputs=score_inputs,
    )

    # Base command
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", agent_config.get("model", "opus"),
    ]

    # Session: create or resume
    session_id = agent_sessions.get(agent_name)
    if session_id:
        cmd.extend(["--resume", session_id])
    else:
        session_id = str(uuid.uuid4())
        agent_sessions[agent_name] = session_id
        cmd.extend(["--session-id", session_id])

        # System prompt only on first call — retained on resume
        role_block = build_role_block(
            role_text=agent_def.get("role", f"You are the {agent_name} agent."),
            inputs=agent_def.get("inputs", []),
            outputs=agent_def.get("outputs", []),
        )
        system_prompt = assemble_system_prompt(agent_config, role=role_block)

        # If resuming after compaction, append the summary
        summary = agent_summaries.pop(agent_name, None)
        if summary:
            system_prompt += (
                "\n\n[RESTORED CONTEXT — compacted from previous session]\n\n"
                + summary
                + "\n\n[Continue from where you left off. "
                "Do not re-do completed work.]"
            )

        cmd.extend(["--system-prompt", system_prompt])

    # Permission flags
    perm_flags = build_allowed_tools_flags(agent_config, include_mcp=False)
    if perm_flags:
        cmd.extend(perm_flags)

    # MCP config (session search tools)
    if agent_def.get("mcp", False):
        db_path = agent_config.get("compact_db", "")
        if db_path:
            cmd.extend(["--mcp-config", generate_mcp_config(db_path)])

    # Execute
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        proc = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=agent_config.get("cli_timeout") or None,
            cwd=agent_config.get("working_directory") or "/tmp",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return _error_result(agent_name, agent_def, "CLI timed out")

    if proc.returncode != 0:
        return _error_result(agent_name, agent_def, proc.stderr[:500])

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _error_result(agent_name, agent_def, "Failed to parse CLI JSON")

    response_text = envelope.get("result", "")
    expected_outputs = agent_def.get("outputs", [])
    outputs = parse_outputs(response_text, expected_outputs)
    usage = envelope.get("usage", {})

    return {
        "agent": agent_name,
        "outputs": outputs,
        "usage": usage,
        "duration_ms": envelope.get("duration_ms", 0),
        "status": "ok",
        "error": None,
    }


def _compact_agent_session(
    agent_name: str,
    agent_def: dict,
    config: dict,
    agent_sessions: dict,
    agent_summaries: dict,
    conn,
    cycle: int,
    last_session_id: str | None,
) -> str | None:
    """Compact an agent's session: generate summary, store, reset session.

    Resumes the old session with a compaction prompt to extract a summary.
    Stores the summary in sessions.db. Deletes the old session UUID so the
    next call creates a fresh session bootstrapped with the summary.

    Returns the new last_session_id, or the original on failure.
    """
    old_session_id = agent_sessions.get(agent_name)
    if not old_session_id:
        return last_session_id

    agent_config = build_agent_config(config, agent_def)

    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", agent_config.get("model", "opus"),
        "--resume", old_session_id,
    ]

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        proc = subprocess.run(
            cmd,
            input=COMPACTION_PROMPT,
            capture_output=True,
            text=True,
            timeout=agent_config.get("cli_timeout") or None,
            cwd=agent_config.get("working_directory") or "/tmp",
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[exploration]   Compaction failed: {e}", flush=True)
        return last_session_id

    if proc.returncode != 0:
        print(f"[exploration]   Compaction failed: {proc.stderr[:200]}", flush=True)
        return last_session_id

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("[exploration]   Compaction failed: bad JSON", flush=True)
        return last_session_id

    summary = envelope.get("result", "").strip()
    if not summary:
        print("[exploration]   Compaction produced empty summary", flush=True)
        return last_session_id

    # Store summary in sessions.db
    session_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        store_session(
            conn,
            session_id=session_id,
            parent_id=last_session_id,
            depth=cycle,
            timestamp=timestamp,
            summary_xml=summary,
            philosophy=agent_def.get("philosophy"),
            framework=agent_def.get("framework"),
            token_estimate=len(summary) // 4,
            record_type="compaction",
        )
        last_session_id = session_id
    except Exception as e:
        print(f"[exploration]   Compaction DB write failed: {e}", flush=True)

    # Reset session: delete old UUID, store summary for bootstrap
    del agent_sessions[agent_name]
    agent_summaries[agent_name] = summary

    print(
        f"[exploration]   {agent_name} compacted "
        f"(~{len(summary)//4} tokens summary). "
        f"Fresh session on next cycle.",
        flush=True,
    )

    return last_session_id


def _error_result(agent_name: str, agent_def: dict, error: str) -> dict:
    """Build a failure result dict."""
    expected_outputs = agent_def.get("outputs", [])
    return {
        "agent": agent_name,
        "outputs": {name: f"[FAILED: {agent_name}] {error}" for name in expected_outputs},
        "usage": {},
        "duration_ms": 0,
        "status": "error",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Sessions.db logging — single source of truth
# ---------------------------------------------------------------------------


def _extract_topic(output_text: str) -> str | None:
    """Extract topic from agent output. Deterministic — no agent involvement.

    Looks for '## Current Sub-Topic' (researcher output format) and
    extracts the first line after it, stripping markdown bold markers.
    """
    if not output_text:
        return None
    import re
    # Match "## Current Sub-Topic" followed by the topic line
    match = re.search(
        r"##\s*Current Sub-?Topic\s*\n+\*{0,2}([^\n*]+)\*{0,2}",
        output_text, re.IGNORECASE
    )
    if match:
        topic = match.group(1).strip()
        if topic:
            return topic[:100]  # cap length
    return None


def _store_agent_output(
    conn, agent_name: str, agent_def: dict, output_text: str,
    cycle: int, parent_id: str | None, current_topic: str | None = None,
) -> str:
    """Store an agent's output in sessions.db.

    Returns the new session_id on success, or the original parent_id
    on failure (so the chain stays connected to the last successful record).
    """
    # Extract topic from researcher output, or use the current cycle's topic
    topic = _extract_topic(output_text) or current_topic or "Untitled"

    session_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        store_session(
            conn,
            session_id=session_id,
            parent_id=parent_id,
            depth=cycle,
            timestamp=timestamp,
            summary_xml=output_text,
            philosophy=agent_def.get("philosophy"),
            framework=agent_def.get("framework"),
            token_estimate=len(output_text) // 4,
            record_type="exploration",
            topic=topic,
            keywords=agent_name,  # use agent name as keyword for identification
        )
        return session_id
    except Exception as e:
        print(f"[exploration]   DB write failed: {e}", flush=True)
        return parent_id or ""


# ---------------------------------------------------------------------------
# Status file — deterministic, overwritten each cycle
# ---------------------------------------------------------------------------


def update_status_file(output_dir: Path, cycle: int, status: str,
                       failures: dict) -> None:
    """Write a simple status file with only deterministic data."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        fail_lines = "\n".join(
            f"- {k}: {v} consecutive" for k, v in failures.items() if v > 0
        ) or "None"

        md = (
            f"# Exploration Status\n\n"
            f"**Cycles Completed:** {cycle}\n"
            f"**Status:** {status}\n"
            f"**Updated:** {datetime.now(timezone.utc).isoformat()[:19]}Z\n\n"
            f"## Failure Tracking\n{fail_lines}\n"
        )
        (output_dir / "exploration_status.md").write_text(md)
    except OSError as e:
        print(f"[exploration] Status file write failed: {e}", flush=True)


# ---------------------------------------------------------------------------
# Adaptive cooldown
# ---------------------------------------------------------------------------


def adaptive_cooldown(base_seconds: int, recent_failure_cycles: int) -> int:
    """Cooldown between cycles. On failure streaks, back off hard.

    0 failures: base cooldown (from config)
    1-2 failures: 60s
    3+ failures: 10min (likely an outage, don't keep hammering)
    """
    if recent_failure_cycles == 0:
        return base_seconds
    elif recent_failure_cycles <= 2:
        return 60
    else:
        return 600


def _sleep_interruptible(seconds: int, data_dir: Path | None = None) -> None:
    """Sleep in 1-second increments, checking for stop/clear signals."""
    for _ in range(max(0, int(seconds))):
        if _stop_requested:
            return
        if data_dir:
            _check_signal_files(data_dir)
            if _stop_requested:
                return
        time.sleep(1)


# ---------------------------------------------------------------------------
# Fallback audit (used when audit agent fails)
# ---------------------------------------------------------------------------

FALLBACK_AUDIT = (
    "## Validation Summary\nAudit unavailable this cycle.\n\n"
    "## Decision\nCONTINUE\n\n"
    "## Rationale\n"
    "Audit agent was unavailable. Continuing current sub-topic "
    "for re-evaluation next cycle.\n\n"
    "## Guidance for Research Agent\n"
    "Continue with the current sub-topic. The previous cycle's "
    "work has not been validated.\n"
)


# ---------------------------------------------------------------------------
# Main exploration loop
# ---------------------------------------------------------------------------


def run_exploration(
    score_path: str,
    config_path: str | None = None,
    output_dir: Path | None = None,
    state_path: Path | None = None,
    task_override: str | None = None,
) -> None:
    global _stop_requested, _clear_requested

    score = load_exploration_score(score_path)
    config = load_config(config_path)
    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    state_path = Path(state_path or DEFAULT_STATE_PATH)
    data_dir = state_path.parent

    # Initialize sessions.db
    conn = init_db(Path(config["compact_db"]))

    loop_cfg = score.get("loop", {})
    max_cycles = loop_cfg.get("max_cycles")
    base_cooldown = loop_cfg.get("cycle_cooldown_seconds", 0)

    flow = score["flow"]  # list of agent name strings
    agents = score["agents"]
    task = task_override or score["task"]
    score_inputs = {"directive": task}

    # Apply score-level tool restrictions (overrides config.yaml for all agents)
    if "allowed_tools" in score:
        config["allowed_tools"] = score["allowed_tools"]

    # Compaction config
    context_window = config.get("context_window", 1_000_000)
    compact_threshold = config.get("compact_threshold", 0.90)
    compact_at = int(context_window * compact_threshold)

    # Seed inputs
    seed = score.get("seed", {})
    if seed.get("starting_subtopic"):
        score_inputs["starting_subtopic"] = seed["starting_subtopic"]

    # Initialize or resume
    state = load_state(state_path)
    if state:
        results = state["results"]
        cycle = state["cycle"]
        consecutive_failures = state.get("failures", {name: 0 for name in agents})
        last_session_id = state.get("last_session_id")
        agent_sessions = state.get("agent_sessions", {})
        agent_summaries = state.get("agent_summaries", {})
        print(f"[exploration] Resuming from cycle {cycle}", flush=True)
        for name, sid in agent_sessions.items():
            print(f"[exploration]   {name} session: {sid[:8]}...", flush=True)
    else:
        results = {
            "directive": task,
            "audit_report": (
                "[No prior audit — this is the first cycle. "
                "Choose the most foundational sub-topic to start.]"
            ),
        }
        cycle = 0
        consecutive_failures = {name: 0 for name in agents}
        last_session_id = None
        agent_sessions = {}
        agent_summaries = {}
        print("[exploration] Starting fresh exploration", flush=True)

    total_failure_streak = 0

    # Banner
    print(f"[exploration] Task: {task.strip()[:120]}", flush=True)
    print(f"[exploration] Flow: {' -> '.join(flow)}", flush=True)
    print(f"[exploration] Max cycles: {max_cycles or 'unlimited'}", flush=True)
    print(f"[exploration] Compact at: {compact_at:,} tokens per agent", flush=True)
    print(f"[exploration] Cooldown: {base_cooldown}s | Ctrl+C to stop", flush=True)
    print(f"[exploration] Signals: touch {data_dir}/exploration.stop|clear", flush=True)
    print("=" * 60, flush=True)

    # --- Main loop ---
    while not _stop_requested:
        # Check for signal files at cycle boundary
        _check_signal_files(data_dir)
        if _stop_requested:
            break

        if max_cycles and cycle >= max_cycles:
            print(f"\n[exploration] Reached max cycles ({max_cycles}).", flush=True)
            break

        cycle += 1
        cycle_start = time.monotonic()
        cycle_topic = None  # set by researcher, inherited by worker/auditor
        cycle_ok = True

        print(f"\n{'='*60}", flush=True)
        print(f"[exploration] === Cycle {cycle} ===", flush=True)

        for i, agent_name in enumerate(flow):
            if _stop_requested:
                break

            # Check signals between agents
            _check_signal_files(data_dir)
            if _stop_requested:
                break

            agent_def = agents[agent_name]
            is_resume = agent_name in agent_sessions
            print(
                f"[exploration] {'Resuming' if is_resume else 'Starting'}: "
                f"{agent_name}"
                f"{' (' + agent_sessions[agent_name][:8] + '...)' if is_resume else ''}",
                flush=True,
            )

            result = _call_exploration_agent(
                agent_name=agent_name,
                agent_def=agent_def,
                task=task,
                config=config,
                results=results,
                score_inputs=score_inputs,
                agent_sessions=agent_sessions,
                agent_summaries=agent_summaries,
            )

            usage = result.get("usage", {})
            dur = result.get("duration_ms", 0) / 1000

            if result["status"] == "ok":
                results.update(result["outputs"])
                consecutive_failures[agent_name] = 0

                total_ctx = _total_context_tokens(usage)
                print(
                    f"[exploration]   {agent_name}: ok "
                    f"({dur:.1f}s, ctx:{total_ctx:,}tok, "
                    f"out:{usage.get('output_tokens', 0)}tok)",
                    flush=True,
                )

                # Store output in sessions.db
                output_text = "\n\n".join(result["outputs"].values())

                # Extract topic from researcher output; propagate to worker/auditor
                extracted = _extract_topic(output_text)
                if extracted:
                    cycle_topic = extracted
                last_session_id = _store_agent_output(
                    conn, agent_name, agent_def, output_text,
                    cycle, last_session_id,
                    current_topic=cycle_topic,
                )

                # --- Auto-compact check ---
                if total_ctx >= compact_at:
                    print(
                        f"[exploration]   {agent_name} context "
                        f"{total_ctx:,}/{context_window:,} "
                        f"({total_ctx/context_window:.0%}) — compacting...",
                        flush=True,
                    )
                    last_session_id = _compact_agent_session(
                        agent_name, agent_def, config,
                        agent_sessions, agent_summaries,
                        conn, cycle, last_session_id,
                    )
            else:
                # --- Failure handling ---
                consecutive_failures[agent_name] += 1
                cycle_ok = False
                err = result.get("error", "unknown")
                print(f"[exploration]   {agent_name}: FAILED — {err}", flush=True)
                print(
                    f"[exploration]   (consecutive: "
                    f"{consecutive_failures[agent_name]})",
                    flush=True,
                )

                if i == 0:
                    # Research failed — skip entire cycle
                    print("[exploration]   Skipping rest of cycle.", flush=True)
                    break
                elif i == len(flow) - 1:
                    # Audit failed — use fallback and store it
                    results["audit_report"] = FALLBACK_AUDIT
                    last_session_id = _store_agent_output(
                        conn, agent_name, agent_def, FALLBACK_AUDIT,
                        cycle, last_session_id,
                    )
                else:
                    # Middle agent (worker) failed — pass failure marker
                    for out_name in agent_def.get("outputs", []):
                        results[out_name] = (
                            f"[AGENT FAILED: {agent_name}] {err}\n\n"
                            f"The {agent_name} agent was unable to produce "
                            f"output this cycle."
                        )

                # Pause on 3 consecutive failures for this agent
                if consecutive_failures[agent_name] >= 3:
                    print(
                        f"\n[exploration] WARNING: {agent_name} failed "
                        f"{consecutive_failures[agent_name]}x. "
                        f"Pausing 60s (Ctrl+C to stop).",
                        flush=True,
                    )
                    _sleep_interruptible(60, data_dir)

        # --- End of cycle bookkeeping ---
        if _stop_requested:
            break

        if cycle_ok:
            total_failure_streak = 0
        else:
            total_failure_streak += 1

        # Pause on 3 consecutive all-failure cycles
        if total_failure_streak >= 3:
            print(
                f"\n[exploration] WARNING: {total_failure_streak} consecutive "
                f"cycles with failures. Pausing 60s.",
                flush=True,
            )
            _sleep_interruptible(60, data_dir)

        # Status file + state
        update_status_file(output_dir, cycle, "running", consecutive_failures)
        save_state(state_path, cycle, results, consecutive_failures,
                   last_session_id, agent_sessions, agent_summaries)

        elapsed = time.monotonic() - cycle_start
        print(f"[exploration] Cycle {cycle} done ({elapsed:.0f}s)", flush=True)

        # Cooldown
        cooldown = adaptive_cooldown(base_cooldown, total_failure_streak)
        if cooldown > 0:
            print(f"[exploration] Cooldown: {cooldown}s", flush=True)
            _sleep_interruptible(cooldown, data_dir)

    # --- Stopped or Cleared ---
    if _clear_requested:
        # Archive old state before clearing
        _archive_state(state_path)
        # Clear: save empty state (sessions.db records preserved)
        save_state(state_path, 0, {}, {name: 0 for name in agents},
                   None, {}, {})
        update_status_file(output_dir, cycle, "cleared", consecutive_failures)
        print(f"\n[exploration] Cleared after {cycle} cycles.", flush=True)
        print("[exploration] Context reset. Sessions.db history preserved.", flush=True)
    else:
        # Stop: save current state for resume
        save_state(state_path, cycle, results, consecutive_failures,
                   last_session_id, agent_sessions, agent_summaries)
        update_status_file(output_dir, cycle, "stopped", consecutive_failures)
        print(f"\n[exploration] Stopped after {cycle} cycles.", flush=True)
        print("[exploration] State preserved. Run again to resume.", flush=True)

    conn.close()
    print(f"[exploration] State: {state_path}", flush=True)


# ---------------------------------------------------------------------------
# CLI — lightweight command wrappers
# ---------------------------------------------------------------------------

DEFAULT_SCORE_PATH = str(SCRIPT_DIR / "exploration-score.yaml")


def _cmd_start(args):
    """Start exploration, optionally with a task override."""
    task_override = " ".join(args.task) if args.task else None

    # Clear existing state if starting fresh with a new task
    if task_override:
        sp = Path(args.state or DEFAULT_STATE_PATH)
        if sp.exists():
            _archive_state(sp)
            sp.unlink()

    run_exploration(
        score_path=args.score,
        config_path=args.config,
        output_dir=Path(args.output) if args.output else None,
        state_path=Path(args.state) if args.state else None,
        task_override=task_override,
    )


def _cmd_stop(args):
    """Create stop signal file."""
    data_dir = Path(args.state or DEFAULT_STATE_PATH).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "exploration.stop").write_text("")
    print("[exploration] Stop signal sent.", flush=True)


def _cmd_clear(args):
    """Create clear signal file (or clear state directly if not running)."""
    data_dir = Path(args.state or DEFAULT_STATE_PATH).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    sp = Path(args.state or DEFAULT_STATE_PATH)

    # If exploration is running, send signal file
    # If not running, archive and clear directly
    if sp.exists():
        _archive_state(sp)
        sp.unlink()
        print("[exploration] State archived and cleared.", flush=True)

    (data_dir / "exploration.clear").write_text("")
    print("[exploration] Clear signal sent.", flush=True)


def _cmd_resume(args):
    """Resume from archived state file or continue from current state."""
    if args.state_file:
        resume_path = Path(args.state_file)
        if not resume_path.exists():
            print(f"[exploration] State file not found: {resume_path}", flush=True)
            return
        active_state = Path(args.state or DEFAULT_STATE_PATH)
        active_state.parent.mkdir(parents=True, exist_ok=True)
        active_state.write_text(resume_path.read_text())
        print(f"[exploration] Restored state from: {resume_path.name}", flush=True)

    run_exploration(
        score_path=args.score,
        config_path=args.config,
        output_dir=Path(args.output) if args.output else None,
        state_path=Path(args.state) if args.state else None,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="exploration",
        description="Continuous autonomous exploration conductor",
    )
    parser.add_argument("--score", default=DEFAULT_SCORE_PATH,
                        help="Path to exploration score YAML")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--state", default=None, help="State file path")

    sub = parser.add_subparsers(dest="command", required=True)

    # /start [task description]
    p_start = sub.add_parser("start", help="Start exploration")
    p_start.add_argument("task", nargs="*", help="Task description (overrides score YAML)")

    # /stop
    sub.add_parser("stop", help="Send stop signal to running exploration")

    # /clear
    sub.add_parser("clear", help="Stop + archive state + clear context")

    # /resume [state_file]
    p_resume = sub.add_parser("resume", help="Resume exploration")
    p_resume.add_argument("state_file", nargs="?", default=None,
                          help="Path to archived state file")

    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "clear":
        _cmd_clear(args)
    elif args.command == "resume":
        _cmd_resume(args)


if __name__ == "__main__":
    main()
