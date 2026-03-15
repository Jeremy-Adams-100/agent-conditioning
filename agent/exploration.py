#!/usr/bin/env python3
"""Continuous Autonomous Exploration Conductor.

Runs a sequential three-agent loop (research → worker → audit) until
stopped via Ctrl+C or max_cycles reached. Each agent is a single-turn
call_claude() invocation via the existing conductor.run_agent().

Usage:
    python -m agent.exploration exploration-score.yaml
    python -m agent.exploration exploration-score.yaml --reset
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agent.conductor import run_agent
from agent.orchestrator import load_config

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_STATE_PATH = SCRIPT_DIR / "data" / "exploration_state.json"

# ---------------------------------------------------------------------------
# Graceful shutdown via SIGINT / SIGTERM
# ---------------------------------------------------------------------------

_stop_requested = False


def _on_signal(signum, frame):
    global _stop_requested
    _stop_requested = True
    print("\n[exploration] Stop requested. Finishing current agent...", flush=True)


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


# ---------------------------------------------------------------------------
# Score loading (simpler than conductor's — no strict input validation
# because inputs cycle across iterations)
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


def save_state(path: Path, cycle: int, results: dict, failures: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "cycle": cycle,
        "results": results,
        "failures": failures,
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


# ---------------------------------------------------------------------------
# Cycle reports
# ---------------------------------------------------------------------------


def write_agent_report(output_dir: Path, cycle: int, agent_name: str, content: str) -> None:
    report_dir = output_dir / "cycle_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"cycle_{cycle:03d}_{agent_name}.md").write_text(content or "")


def write_cycle_summary(output_dir: Path, cycle: int, results: dict) -> None:
    report_dir = output_dir / "cycle_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    decision = _extract_decision(results.get("audit_report", ""))
    ts = datetime.now(timezone.utc).isoformat()[:19] + "Z"

    summary = (
        f"# Cycle {cycle} Summary\n\n"
        f"**Audit Decision:** {decision}\n"
        f"**Timestamp:** {ts}\n\n"
        f"## Research Brief (excerpt)\n{_excerpt(results.get('research_brief', ''))}\n\n"
        f"## Work Output (excerpt)\n{_excerpt(results.get('work_output', ''))}\n\n"
        f"## Audit Report (excerpt)\n{_excerpt(results.get('audit_report', ''))}\n"
    )
    (report_dir / f"cycle_{cycle:03d}_summary.md").write_text(summary)


def update_status_file(output_dir: Path, cycle: int, results: dict,
                       status: str, failures: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = _extract_decision(results.get("audit_report", ""))
    fail_lines = "\n".join(
        f"- {k}: {v} consecutive" for k, v in failures.items() if v > 0
    ) or "None"

    md = (
        f"# Exploration Status\n\n"
        f"**Cycles Completed:** {cycle}\n"
        f"**Last Audit Decision:** {decision}\n"
        f"**Status:** {status}\n"
        f"**Updated:** {datetime.now(timezone.utc).isoformat()[:19]}Z\n\n"
        f"## Directive\n{results.get('directive', 'N/A')}\n\n"
        f"## Recent Failures\n{fail_lines}\n"
    )
    (output_dir / "exploration_status.md").write_text(md)


def _extract_decision(audit_text: str) -> str:
    """Extract VALIDATED/CONTINUE/PIVOT from audit report text."""
    if not audit_text:
        return "N/A"
    for line in audit_text.split("\n"):
        stripped = line.strip()
        if stripped in ("VALIDATED", "CONTINUE", "PIVOT"):
            return stripped
    return "UNKNOWN"


def _excerpt(text: str, max_chars: int = 500) -> str:
    if not text:
        return "(empty)"
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(truncated)"


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


def _sleep_interruptible(seconds: int) -> None:
    """Sleep in 1-second increments, checking for stop signal."""
    for _ in range(max(0, int(seconds))):
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
) -> None:
    global _stop_requested

    score = load_exploration_score(score_path)
    config = load_config(config_path)
    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    state_path = Path(state_path or DEFAULT_STATE_PATH)

    loop_cfg = score.get("loop", {})
    max_cycles = loop_cfg.get("max_cycles")
    base_cooldown = loop_cfg.get("cycle_cooldown_seconds", 0)
    report_every = loop_cfg.get("report_every_cycle", True)

    flow = score["flow"]  # list of agent name strings
    agents = score["agents"]
    task = score["task"]
    score_inputs = {"directive": task}

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
        print(f"[exploration] Resuming from cycle {cycle}", flush=True)
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
        print("[exploration] Starting fresh exploration", flush=True)

    total_failure_streak = 0

    # Banner
    print(f"[exploration] Task: {task.strip()[:120]}", flush=True)
    print(f"[exploration] Flow: {' -> '.join(flow)}", flush=True)
    print(f"[exploration] Max cycles: {max_cycles or 'unlimited'}", flush=True)
    print(f"[exploration] Cooldown: {base_cooldown}s | Ctrl+C to stop", flush=True)
    print("=" * 60, flush=True)

    # --- Main loop ---
    while not _stop_requested:
        if max_cycles and cycle >= max_cycles:
            print(f"\n[exploration] Reached max cycles ({max_cycles}).", flush=True)
            break

        cycle += 1
        cycle_start = time.monotonic()
        cycle_ok = True

        print(f"\n{'='*60}", flush=True)
        print(f"[exploration] === Cycle {cycle} ===", flush=True)

        for i, agent_name in enumerate(flow):
            if _stop_requested:
                break

            agent_def = agents[agent_name]
            print(f"[exploration] Running: {agent_name}", flush=True)

            result = run_agent(
                agent_name=agent_name,
                agent_def=agent_def,
                score_task=task,
                base_config=config,
                results=results,
                score_inputs=score_inputs,
            )

            usage = result.get("usage", {})
            dur = result.get("duration_ms", 0) / 1000

            if result["status"] == "ok":
                results.update(result["outputs"])
                consecutive_failures[agent_name] = 0
                print(
                    f"[exploration]   {agent_name}: ok "
                    f"({dur:.1f}s, {usage.get('input_tokens',0)}in/"
                    f"{usage.get('output_tokens',0)}out)",
                    flush=True,
                )
                if report_every:
                    for content in result["outputs"].values():
                        write_agent_report(output_dir, cycle, agent_name, content)
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
                    # Audit failed — use fallback
                    results["audit_report"] = FALLBACK_AUDIT
                    if report_every:
                        write_agent_report(output_dir, cycle, agent_name, FALLBACK_AUDIT)
                else:
                    # Middle agent (worker) failed — pass failure marker
                    for out_name in agent_def.get("outputs", []):
                        results[out_name] = (
                            f"[AGENT FAILED: {agent_name}] {err}\n\n"
                            f"The {agent_name} agent was unable to produce "
                            f"output this cycle."
                        )
                    if report_every:
                        for out_name in agent_def.get("outputs", []):
                            write_agent_report(
                                output_dir, cycle, agent_name, results[out_name]
                            )

                # Pause on 3 consecutive failures for this agent
                if consecutive_failures[agent_name] >= 3:
                    print(
                        f"\n[exploration] WARNING: {agent_name} failed "
                        f"{consecutive_failures[agent_name]}x. "
                        f"Pausing 60s (Ctrl+C to stop).",
                        flush=True,
                    )
                    _sleep_interruptible(60)

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
            _sleep_interruptible(60)

        # Write reports
        if report_every:
            write_cycle_summary(output_dir, cycle, results)
            update_status_file(
                output_dir, cycle, results, "running", consecutive_failures
            )

        # Save state
        save_state(state_path, cycle, results, consecutive_failures)

        elapsed = time.monotonic() - cycle_start
        print(f"[exploration] Cycle {cycle} done ({elapsed:.0f}s)", flush=True)

        # Cooldown
        cooldown = adaptive_cooldown(base_cooldown, total_failure_streak)
        if cooldown > 0:
            print(f"[exploration] Cooldown: {cooldown}s", flush=True)
            _sleep_interruptible(cooldown)

    # --- Stopped ---
    save_state(state_path, cycle, results, consecutive_failures)
    update_status_file(output_dir, cycle, results, "stopped", consecutive_failures)
    print(f"\n[exploration] Stopped after {cycle} cycles.", flush=True)
    print(f"[exploration] State: {state_path}", flush=True)
    print(f"[exploration] Reports: {output_dir}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="exploration",
        description="Continuous autonomous exploration conductor",
    )
    parser.add_argument("score", help="Path to exploration score YAML")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--state", default=None, help="State file path")
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignore saved state and start fresh",
    )

    args = parser.parse_args()

    if args.reset:
        sp = Path(args.state or DEFAULT_STATE_PATH)
        if sp.exists():
            sp.unlink()
            print(f"[exploration] Reset: removed {sp}", flush=True)

    run_exploration(
        score_path=args.score,
        config_path=args.config,
        output_dir=Path(args.output) if args.output else None,
        state_path=Path(args.state) if args.state else None,
    )


if __name__ == "__main__":
    main()
