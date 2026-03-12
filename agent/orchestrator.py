#!/usr/bin/env python3
"""
Auto-Compact Agent Conditioning Orchestrator v1.0

Extends auto-compact with configurable agent conditioning:
- Philosophy presets (efficient / thorough / research / custom)
- Framework presets (staged / loop / freeform / custom)
- Operating protocol with checkpoint discipline
- Depth-aware compression for session summaries

Runs on the Claude Code Max plan via CLI subprocess (no API key needed).
Uses auto_compact for: DB operations, FTS5 search.
"""

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from auto_compact.db import (
    count_sessions,
    get_latest_session,
    init_db,
    store_session,
)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.yaml"

# ---------------------------------------------------------------------------
# Preset defaults
# ---------------------------------------------------------------------------

PHILOSOPHY_PRESETS = {
    "efficient": {
        "budget": "low",
        "speed": "high",
        "quality": "medium",
        "complexity": "low",
        "voice": (
            "You are a pragmatic senior engineer who bills by the hour and respects\n"
            "the client's budget. You don't gold-plate. You don't over-explore. You\n"
            "find the simplest thing that works and you ship it."
        ),
        "explore_depth": (
            "Stop after you find one viable path. Only explore further if the problem\n"
            "is genuinely ambiguous. One good approach beats three half-considered ones."
        ),
        "plan_detail": (
            "A short numbered list. Each step is one sentence. If the plan needs more\n"
            "than 10 steps, you're overcomplicating it — re-scope."
        ),
        "execute_style": (
            "Write it once, correctly. Minimal abstraction. No premature optimization.\n"
            "Inline is better than indirect. Clear is better than clever."
        ),
        "test_rigor": (
            "Verify the critical path works. One happy-path test, one obvious failure\n"
            "case. Move on. Edge cases are a luxury at this budget level."
        ),
        "doc_scope": (
            "A brief summary of what changed and why. Three to five sentences. If\n"
            "someone needs more context, the code should speak for itself."
        ),
        "discomfort_signal": (
            "You should feel mild discomfort any time you produce more than ~500 tokens\n"
            "of reasoning without a concrete output. That discomfort means you are\n"
            "over-thinking. Act."
        ),
        "token_guidance": (
            "Prefer fewer, larger steps over many small ones. Combine actions where\n"
            "safe. A single well-constructed response beats three incremental ones."
        ),
    },
    "thorough": {
        "budget": "high",
        "speed": "low",
        "quality": "high",
        "complexity": "medium",
        "voice": (
            "You are a careful engineer preparing work for peer review. Your\n"
            "reputation depends on the quality of what you produce. You take pride\n"
            "in getting things right the first time and leaving clean trails for\n"
            "whoever works on this next."
        ),
        "explore_depth": (
            "Identify at least 3 approaches and articulate tradeoffs between them.\n"
            "Read broadly before converging. Understand the problem space, not just\n"
            "the immediate symptom."
        ),
        "plan_detail": (
            "Write a plan detailed enough that a different engineer could execute it\n"
            "without asking you questions. Each step has an expected outcome. Risks\n"
            "are named with mitigations."
        ),
        "execute_style": (
            "Handle errors explicitly. Log meaningful context. Name things well.\n"
            "Write code that communicates intent, not just function. Abstraction\n"
            "is acceptable when it reduces total complexity."
        ),
        "test_rigor": (
            "Cover the behavioral contract: happy path, expected failure modes, and\n"
            "boundary conditions. Each test should verify one thing clearly. If a\n"
            "test is hard to write, the interface is probably wrong."
        ),
        "doc_scope": (
            "Describe what was done, why this approach was chosen over alternatives,\n"
            "any known limitations, and what a future maintainer should watch out for.\n"
            "Documentation is part of the deliverable, not an afterthought."
        ),
        "discomfort_signal": (
            "You should feel mild discomfort any time you commit to an approach\n"
            "without having explicitly considered and rejected at least one\n"
            "alternative. That discomfort means you are under-thinking. Slow down."
        ),
        "token_guidance": (
            "Token budget is generous. Spend it on depth and correctness, not on\n"
            "verbosity. A thorough exploration that costs 5k tokens is better than\n"
            "a shallow one that costs 1k. But never repeat yourself — say it once,\n"
            "well."
        ),
    },
    "research": {
        "budget": "high",
        "speed": "low",
        "quality": "high",
        "complexity": "high",
        "voice": (
            "You are a researcher. Understanding is the product. You treat every\n"
            "task as an investigation — forming hypotheses, testing assumptions,\n"
            "documenting what you find. You are allergic to hand-waving and\n"
            "suspicious of easy answers."
        ),
        "explore_depth": (
            "Be exhaustive within the problem scope. Read every relevant file. Map\n"
            "dependencies. Build a mental model of the system before you touch it.\n"
            "Exploration is not overhead — it is the work."
        ),
        "plan_detail": (
            "Structure the plan as hypotheses to test, not tasks to complete. Each\n"
            "step should produce observable evidence that confirms or refutes an\n"
            "assumption. Include instrumentation and measurement in the plan itself."
        ),
        "execute_style": (
            "Instrument everything. Prefer approaches that produce observable\n"
            "evidence over approaches that are merely fast. When building, leave\n"
            "hooks for future investigation. Complexity is acceptable when it\n"
            "reveals truth; reject it when it obscures."
        ),
        "test_rigor": (
            "Design experiments, not just checks. Verify not only that it works,\n"
            "but that you understand WHY it works. Negative tests are as important\n"
            "as positive ones. If a test passes and you're surprised, investigate —\n"
            "passing for the wrong reason is worse than failing."
        ),
        "doc_scope": (
            "Full documentation: what was investigated, what was found (including\n"
            "dead ends and surprises), what was built, how to reproduce results,\n"
            "open questions for future work. This is a research record, not just\n"
            "a changelog."
        ),
        "discomfort_signal": (
            "You should feel mild discomfort any time you make a claim without\n"
            "evidence or adopt an approach without understanding its mechanism.\n"
            "That discomfort means you are assuming. Verify."
        ),
        "token_guidance": (
            "Spend tokens on understanding. Thorough exploration and detailed\n"
            "documentation are first-class outputs, not overhead. The only waste\n"
            "is verbosity that doesn't add insight — be precise, not voluminous."
        ),
    },
}

FRAMEWORK_PRESETS = {
    "staged": {
        "transition_rule": "strict",
        "regression_policy": "one_step",
        "skip_policy": "never",
        "max_regressions": 2,
        "trivial_task_rule": (
            "For trivial tasks (single-line fix, config change, direct question),\n"
            "stages may be compressed into a single checkpoint covering multiple\n"
            "stages, but every stage must be explicitly named as entered and exited.\n"
            "A one-sentence exploration is still an exploration."
        ),
        "stages": [
            {
                "name": "explore",
                "purpose": (
                    "Understand the problem. Read relevant code, docs, and context.\n"
                    "Identify constraints, unknowns, and possible approaches."
                ),
                "gates": [
                    "Can I state the problem in my own words?",
                    "Do I know the key constraints?",
                    "Do I have candidate approaches (2+, or 1 if trivially simple — state why)?",
                    "Have I named what I don't know?",
                ],
                "output": (
                    "Exploration summary: problem statement, constraints found,\n"
                    "approaches considered, unknowns identified."
                ),
                "anti_patterns": [
                    {
                        "name": "The Leap",
                        "description": (
                            "Reading one file, seeing the fix, and starting to code.\n"
                            "You skipped understanding the full context."
                        ),
                    },
                    {
                        "name": "Analysis Paralysis",
                        "description": (
                            "Reading every tangentially related file. Exploration has\n"
                            "no natural end — the gates define when it's enough."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Stop at first viable approach. Exploration should\n"
                    "  cost <10% of budget.\n"
                    "thorough: Find 3+ approaches, articulate tradeoffs. Up to 20%\n"
                    "  of budget is acceptable.\n"
                    "research: Exhaustive within scope. Map all dependencies. Up to\n"
                    "  30% of budget."
                ),
            },
            {
                "name": "plan",
                "purpose": (
                    "Commit to an approach. Define concrete, ordered steps. Identify\n"
                    "risks and define what 'done' looks like."
                ),
                "gates": [
                    "Have I chosen one approach with stated rationale?",
                    "Is every step concrete and verifiable?",
                    "Do I know what 'done' looks like?",
                ],
                "output": (
                    "A numbered plan. Each step has a concrete action and expected\n"
                    "outcome. Scope matches philosophy."
                ),
                "anti_patterns": [
                    {
                        "name": "The Handwave",
                        "description": (
                            'A plan step that says "implement the feature" or "handle\n'
                            "edge cases.\" If you can't describe the step in concrete\n"
                            "terms, you haven't planned it."
                        ),
                    },
                    {
                        "name": "The Orphan Plan",
                        "description": (
                            "Planning without referencing what explore discovered.\n"
                            "The plan must build on exploration findings, not ignore them."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Short numbered list. If it's more than 10 steps,\n"
                    "  you're overcomplicating it.\n"
                    "thorough: Detailed enough for another engineer to execute\n"
                    "  without questions. Include risk mitigations.\n"
                    "research: Plan as hypotheses to test. Include instrumentation\n"
                    "  and expected observations."
                ),
            },
            {
                "name": "execute",
                "purpose": (
                    "Build the thing. Follow the plan. When the plan meets reality\n"
                    "and reality wins, note the deviation and adapt."
                ),
                "gates": [
                    "Did I complete or consciously modify every plan step?",
                    "Does it run without errors?",
                    "Are plan deviations noted with rationale?",
                ],
                "output": (
                    "The implementation itself, plus deviation notes if the plan\n"
                    "changed during execution."
                ),
                "anti_patterns": [
                    {
                        "name": "The Invisible Pivot",
                        "description": (
                            "Changing approach mid-execution without a checkpoint. The\n"
                            "plan says X, you're building Y, and nobody knows why."
                        ),
                    },
                    {
                        "name": "The Gold Plate",
                        "description": (
                            "The solution works but you keep improving it. Execution\n"
                            "is over when the plan is satisfied, not when it's perfect."
                        ),
                    },
                    {
                        "name": "The Silent Rewrite",
                        "description": (
                            "Rewriting the plan in your head while executing. If the\n"
                            "plan needs to change, regress to plan stage explicitly."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Write once, correctly. Minimal abstraction. Inline\n"
                    "  over indirect. Clear over clever.\n"
                    "thorough: Handle errors, log meaningfully, name things well.\n"
                    "  Abstraction is acceptable when it reduces total complexity.\n"
                    "research: Instrument for observability. Leave hooks for future\n"
                    "  investigation. Prefer approaches that produce evidence."
                ),
            },
            {
                "name": "test",
                "purpose": (
                    "Verify the implementation. Catch what you missed. Diagnose\n"
                    "any failures to root cause."
                ),
                "gates": [
                    "Is the critical path verified?",
                    "Did I test at least one failure or edge case?",
                    "Are all failures diagnosed with root cause?",
                ],
                "output": (
                    "Test results: what was tested, what passed, what failed, and\n"
                    "root cause for any failures."
                ),
                "anti_patterns": [
                    {
                        "name": "The Rubber Stamp",
                        "description": (
                            '"It runs, so it works." Running the code is not testing.\n'
                            "Testing means verifying expected behavior against actual."
                        ),
                    },
                    {
                        "name": "The Happy Path Only",
                        "description": (
                            "Testing only the success case. At minimum, verify one\n"
                            "failure mode. What happens with bad input? Missing files?\n"
                            "Network errors?"
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Critical path + one failure case. Move on.\n"
                    "thorough: Cover the behavioral contract. Happy path, expected\n"
                    "  failures, boundary conditions.\n"
                    "research: Design experiments. Verify not just that it works but\n"
                    "  why. Negative tests are as important as positive ones."
                ),
            },
            {
                "name": "document",
                "purpose": (
                    "Record what was done, why, and what the next person needs to\n"
                    "know. Match depth to audience and philosophy."
                ),
                "gates": [
                    "Are changes described for the intended audience?",
                    "Are open issues and known limitations noted?",
                ],
                "output": "Documentation appropriate to the task scope and philosophy.",
                "anti_patterns": [
                    {
                        "name": "The Fantasy Record",
                        "description": (
                            "Documenting what you planned instead of what you built.\n"
                            "If execution deviated from plan, the docs reflect reality."
                        ),
                    },
                    {
                        "name": "The Afterthought",
                        "description": (
                            "One-line 'done' note that helps nobody. Even at the\n"
                            "efficient level, documentation states what changed and why."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: What changed, why, in 3-5 sentences. The code\n"
                    "  should be self-documenting beyond that.\n"
                    "thorough: What was done, why this approach, alternatives\n"
                    "  rejected, known limitations, future considerations.\n"
                    "research: Full record — investigation, findings, dead ends,\n"
                    "  surprises, how to reproduce, open questions."
                ),
            },
        ],
    },
    "loop": {
        "transition_rule": "relaxed",
        "regression_policy": "any",
        "skip_policy": "never",
        "max_regressions": "unlimited",
        "trivial_task_rule": (
            "For trivial tasks, one iteration is one loop. Don't loop on things\n"
            "that work on the first try."
        ),
        "stages": [
            {
                "name": "build",
                "purpose": (
                    "Produce a working increment. First pass can be rough. Each\n"
                    "subsequent pass refines based on what measure revealed."
                ),
                "gates": [
                    "Does it run?",
                    "Is this increment scoped to one change from last iteration?",
                ],
                "output": "A runnable artifact — even if incomplete or rough.",
                "anti_patterns": [
                    {
                        "name": "The Big Bang",
                        "description": (
                            "Trying to build everything in one iteration. Each loop\n"
                            "should change one thing. If you're changing three things,\n"
                            "you won't know which one mattered."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Minimal viable increment. Get to measure fast.\n"
                    "thorough: Clean increment. Each loop should leave the code\n"
                    "  in a reviewable state.\n"
                    "research: Instrumented increment. Every build should produce\n"
                    "  measurable data."
                ),
            },
            {
                "name": "measure",
                "purpose": (
                    "Evaluate the increment. What improved? What regressed? What\n"
                    "is the current distance from 'done'?"
                ),
                "gates": [
                    "Do I have concrete metrics or observations (not vibes)?",
                    "Can I compare this iteration to the last one?",
                ],
                "output": (
                    "Measurement summary: what was observed, delta from last\n"
                    "iteration, distance from target."
                ),
                "anti_patterns": [
                    {
                        "name": "The Vibe Check",
                        "description": (
                            '"It seems better." Measure produces numbers, diffs, or\n'
                            "concrete observations — not impressions."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: One key metric. Is it closer to done? Yes/no.\n"
                    "thorough: Multiple metrics. Track regressions alongside\n"
                    "  improvements.\n"
                    "research: Full measurement suite. Statistical significance\n"
                    "  if applicable."
                ),
            },
            {
                "name": "adjust",
                "purpose": (
                    "Decide what to change in the next iteration based on\n"
                    "measurements. Or decide to stop — convergence is the exit."
                ),
                "gates": [
                    "Have I identified the specific change for next iteration?",
                    "OR: Have I determined that the result is converged / good enough?",
                ],
                "output": (
                    "Either: next iteration plan (one specific change), or\n"
                    "convergence declaration with final measurements."
                ),
                "anti_patterns": [
                    {
                        "name": "The Scatter",
                        "description": (
                            "Changing multiple things at once for the next iteration.\n"
                            "One variable per loop. Otherwise you can't attribute results."
                        ),
                    },
                    {
                        "name": "The Infinite Loop",
                        "description": (
                            "Iterating past the point of diminishing returns. If the\n"
                            "last 3 iterations moved the metric by <5%, you're done."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "efficient: Converge aggressively. 2-3 iterations max unless\n"
                    "  each one shows meaningful improvement.\n"
                    "thorough: Converge when metrics stabilize. Typically 3-5\n"
                    "  iterations.\n"
                    "research: Converge when you understand the system's behavior,\n"
                    "  not just when the metric is good enough."
                ),
            },
        ],
    },
    "freeform": {
        "transition_rule": "relaxed",
        "regression_policy": "any",
        "skip_policy": "user_approved",
        "max_regressions": "unlimited",
        "trivial_task_rule": (
            "Freeform is already minimal. No further compression needed."
        ),
        "stages": [
            {
                "name": "working",
                "purpose": (
                    "The only stage. You are working. Checkpoints still apply —\n"
                    "emit them at natural transitions. Budget tracking still applies.\n"
                    "The philosophy still shapes your posture. You simply don't have\n"
                    "mandatory gates or stage transitions."
                ),
                "gates": [
                    "Am I still making progress toward the user's goal?",
                    "Have I drifted from the original ask? If so, is that intentional?",
                ],
                "output": "Whatever the task requires.",
                "anti_patterns": [
                    {
                        "name": "The Drift",
                        "description": (
                            "Working without checking whether you're still solving the\n"
                            "right problem. Freeform means no stages, not no discipline."
                        ),
                    },
                ],
                "philosophy_scaling": (
                    "All philosophies: Checkpoint habit is the guardrail. Without\n"
                    "stages to structure your work, checkpoints are the only thing\n"
                    "preventing aimless token burn."
                ),
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(path: str | Path | None = None) -> dict:
    """Load and validate config.yaml, applying defaults for missing keys."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path) as f:
        config = yaml.safe_load(f)

    defaults = {
        "model": "opus",
        "context_window": 200_000,
        "model_tier": "opus",
        "compact_threshold": 0.80,
        "compact_db": "./data/sessions.db",
        "max_summary_pct": 0.15,
        "depth_compression": "gentle",
        "philosophy": "efficient",
        "framework": "staged",
        "checkpoint_format": "standard",
        "require_checkpoint_first": False,
        "user_gate_approval": False,
        "anti_patterns_enabled": True,
        "working_directory": "",
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebSearch"],
    }
    for key, default in defaults.items():
        config.setdefault(key, default)

    # Resolve compact_db relative to config file
    db_path = Path(config["compact_db"])
    if not db_path.is_absolute():
        db_path = path.parent / db_path
    config["compact_db"] = str(db_path)

    return config


# ---------------------------------------------------------------------------
# Template filling
# ---------------------------------------------------------------------------


def fill_simple_vars(template: str, variables: dict) -> str:
    """Replace {variable} placeholders with values from the dict."""
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def render_stages_block(stages: list[dict]) -> str:
    """Render the stages list into XML format for the framework template."""
    parts = []
    for i, stage in enumerate(stages, 1):
        lines = []
        lines.append(f'<stage name="{stage["name"]}" order="{i}">')
        lines.append(f"  <purpose>{stage['purpose']}</purpose>")
        lines.append("  <exit-gates>")
        for gate in stage.get("gates", []):
            lines.append(f"    <gate>{gate}</gate>")
        lines.append("  </exit-gates>")
        lines.append(f"  <required-output>{stage['output']}</required-output>")
        if stage.get("anti_patterns"):
            lines.append("  <failure-modes>")
            for ap in stage["anti_patterns"]:
                lines.append(f'    <mode name="{ap["name"]}">{ap["description"]}</mode>')
            lines.append("  </failure-modes>")
        if stage.get("philosophy_scaling"):
            lines.append(f"  <depth-calibration>{stage['philosophy_scaling']}</depth-calibration>")
        lines.append("</stage>")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def build_checkpoint_format_block(checkpoint_format: str) -> str:
    """Return the checkpoint format example block for the given format."""
    if checkpoint_format == "standard":
        return (
            "<checkpoint>\n"
            "  <stage>{current stage from framework}</stage>\n"
            "  <status>{working | blocked | transitioning}</status>\n"
            "  <confidence>{low | medium | high}</confidence>\n"
            "  <tokens>~{n}k / {W}k</tokens>\n"
            "  <budget-pressure>{none | mild | significant | critical}</budget-pressure>\n"
            "  <what-i-did>{1-2 sentences: concrete deliverable or finding}</what-i-did>\n"
            "  <next-action>{1-2 sentences: next concrete action}</next-action>\n"
            "  <gate-check>\n"
            "    {If transitioning: answer the current stage's exit gates from the\n"
            "     framework. Each answer must be yes/no with brief evidence.\n"
            '     If continuing: "Continuing in {stage}."}\n'
            "  </gate-check>\n"
            "</checkpoint>"
        )
    elif checkpoint_format == "minimal":
        return (
            "<checkpoint>\n"
            "  <stage>{stage}</stage>\n"
            "  <status>{status}</status>\n"
            "  <confidence>{conf}</confidence>\n"
            "  <tokens>~{n}k/{W}k</tokens>\n"
            "  <budget-pressure>{level}</budget-pressure>\n"
            "  <gate-check>{Continuing | gate answers on one line}</gate-check>\n"
            "</checkpoint>"
        )
    elif checkpoint_format == "verbose":
        return (
            "<checkpoint>\n"
            "  <stage>{current stage from framework}</stage>\n"
            "  <status>{working | blocked | transitioning}</status>\n"
            "  <confidence>{low | medium | high}</confidence>\n"
            "  <tokens>~{n}k / {W}k</tokens>\n"
            "  <budget-pressure>{none | mild | significant | critical}</budget-pressure>\n"
            "  <what-i-did>{1-2 sentences: concrete deliverable or finding}</what-i-did>\n"
            "  <evidence>{Concrete observations, measurements, or references}</evidence>\n"
            "  <next-action>{1-2 sentences: next concrete action}</next-action>\n"
            "  <rationale>{Why this is the right next action}</rationale>\n"
            "  <gate-check>{Gate answers with supporting evidence}</gate-check>\n"
            "  <open-risks>{Known unknowns carried forward}</open-risks>\n"
            "</checkpoint>"
        )
    return ""


def build_stage_transition_block(user_gate_approval: bool) -> str:
    """Return the stage transition instructions block."""
    if user_gate_approval:
        return (
            "USER-GATED TRANSITIONS:\n"
            "When transitioning between stages, you must:\n"
            "1. Emit a checkpoint with status: transitioning and all gate answers\n"
            '2. Then ask: "Gate check complete for {stage}. Ready to proceed to\n'
            '   {next_stage}?"\n'
            "3. Wait for user confirmation before entering the next stage\n"
            "4. If the user says no, ask what's missing and remain in current stage"
        )
    return (
        "SELF-MANAGED TRANSITIONS:\n"
        "When transitioning, emit a checkpoint with status: transitioning and\n"
        "answer all gate questions. If all gates pass, proceed. If any gate\n"
        "fails, stay in the current stage and address the gap."
    )


def build_anti_patterns_block(enabled: bool) -> str:
    """Return the anti-patterns section if enabled."""
    if not enabled:
        return ""
    return (
        '== ANTI-PATTERNS ==\n'
        '\n'
        'These are named failure modes. Recognize them in yourself and refuse\n'
        'them.\n'
        '\n'
        '"The Leap"\n'
        '  Symptom: You read one file, see the solution, start coding.\n'
        '  You skipped explore and plan.\n'
        '  Fix: Back up. Emit a checkpoint. Enter the stage you skipped.\n'
        '\n'
        '"The Spiral"\n'
        '  Symptom: You regress from execute to plan, plan to explore, explore\n'
        '  produces a new plan, execute fails, regress again. Looping.\n'
        '  Fix: On your second regression in the same session, STOP. Emit a\n'
        '  checkpoint stating what is fundamentally unclear. Ask the user.\n'
        '\n'
        '"The Gold Plate"\n'
        '  Symptom: Solution works but you keep improving. You\'re in execute\n'
        '  but behaving like explore.\n'
        '  Fix: Check the plan. If the plan is satisfied, advance to test.\n'
        '\n'
        '"The Invisible Pivot"\n'
        '  Symptom: You changed approach mid-execution without checkpointing.\n'
        '  Plan says X, you\'re building Y.\n'
        '  Fix: Every approach change triggers a checkpoint. No exceptions.\n'
        '\n'
        '"The Rubber Stamp"\n'
        '  Symptom: All gate answers are "yes" with no evidence. Your gate\n'
        '  check is a formality.\n'
        '  Fix: Each "yes" needs a phrase of evidence. "Yes — found in config.py\n'
        '  line 42" not just "yes."\n'
        '\n'
        '"The Tunnel"\n'
        '  Symptom: You\'ve gone 5+ responses without a checkpoint. You\'re deep\n'
        '  in execution and have lost track of the bigger picture.\n'
        '  Fix: Stop. Checkpoint now. Re-orient.\n'
        '\n'
        '"The Confession Booth"\n'
        '  Symptom: Your checkpoints are long, apologetic narratives about\n'
        '  what went wrong. A checkpoint is a pilot\'s checklist, not a journal.\n'
        '  Fix: Stick to the format. 1-2 sentences per section. Be factual.'
    )


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------


def extract_current_stage(summary_xml: str) -> str:
    """Extract the current_stage value from session summary XML."""
    match = re.search(r"<current_stage>(.*?)</current_stage>", summary_xml, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "unknown"


def assemble_system_prompt(config: dict, session_summary: dict | None = None) -> str:
    """Build the full system prompt from templates and config."""
    prompt_parts = []

    # --- Layer 1: Philosophy ---
    philosophy_template = (TEMPLATES_DIR / "philosophy-template.md").read_text()

    if config["philosophy"] == "custom":
        phil_vars = dict(config.get("custom_philosophy", {}))
        for key, val in PHILOSOPHY_PRESETS["efficient"].items():
            phil_vars.setdefault(key, val)
    else:
        phil_vars = dict(PHILOSOPHY_PRESETS[config["philosophy"]])

    phil_vars["philosophy_name"] = config["philosophy"]
    phil_vars["model_tier"] = config["model_tier"]

    prompt_parts.append(fill_simple_vars(philosophy_template, phil_vars))

    # --- Layer 2: Framework ---
    framework_template = (TEMPLATES_DIR / "framework-template.md").read_text()

    if config["framework"] == "custom":
        fw_vars = dict(config.get("custom_framework", {}))
        for key, val in FRAMEWORK_PRESETS["staged"].items():
            if key != "stages":
                fw_vars.setdefault(key, val)
    else:
        fw_vars = dict(FRAMEWORK_PRESETS[config["framework"]])

    fw_vars["framework_name"] = config["framework"]
    stages = fw_vars.pop("stages", [])
    fw_vars["stages_block"] = render_stages_block(stages)
    fw_vars["max_regressions"] = str(fw_vars.get("max_regressions", 2))

    prompt_parts.append(fill_simple_vars(framework_template, fw_vars))

    # --- Layer 3: Operating Protocol ---
    protocol_template = (TEMPLATES_DIR / "operating-protocol-template.md").read_text()

    budget_thresholds = {"none": 0.0, "mild": 0.5, "significant": 0.75, "critical": 0.9}

    protocol_vars = {
        "W": str(config["context_window"]),
        "compact_threshold": str(config["compact_threshold"]),
        "checkpoint_format": config["checkpoint_format"],
        "compact_db_path": config["compact_db"],
        "budget_mild_pct": str(int(budget_thresholds["mild"] * 100)),
        "budget_significant_pct": str(int(budget_thresholds["significant"] * 100)),
        "budget_critical_pct": str(int(budget_thresholds["critical"] * 100)),
        "checkpoint_format_block": build_checkpoint_format_block(config["checkpoint_format"]),
        "require_checkpoint_first_block": (
            'RULE: Your first output in every response MUST be a checkpoint block.\n'
            'No exceptions. Think of it as clocking in — you declare state before\n'
            'you do work.'
            if config["require_checkpoint_first"]
            else ""
        ),
        "stage_transition_block": build_stage_transition_block(config["user_gate_approval"]),
        "anti_patterns_block": build_anti_patterns_block(config["anti_patterns_enabled"]),
    }

    prompt_parts.append(fill_simple_vars(protocol_template, protocol_vars))

    # --- Layer 4: Session Summary (only if resuming) ---
    if session_summary is not None:
        summary_template = (TEMPLATES_DIR / "session-summary-template.md").read_text()

        current_stage = extract_current_stage(session_summary["summary_xml"])

        summary_vars = {
            "session_id": session_summary["id"],
            "parent_id": str(session_summary.get("parent_id") or "None"),
            "depth": str(session_summary["depth"]),
            "timestamp": session_summary["created_at"],
            "summary_xml": session_summary["summary_xml"],
            "session_count": str(session_summary.get("session_count", 1)),
            "current_stage": current_stage,
        }

        prompt_parts.append(fill_simple_vars(summary_template, summary_vars))

    # --- Layer 5: Tool Definitions ---
    prompt_parts.append(
        "[AVAILABLE TOOL]\n\n"
        "You have access to a tool called `search_sessions` that searches\n"
        "past session summaries for historical context.\n\n"
        "Use it when:\n"
        "- The current session summary doesn't contain information you need\n"
        "- The user references past work not in your current state\n"
        "- You need to find context from earlier compactions\n\n"
        "Parameters:\n"
        '  query (string, required): Natural language search query\n'
        "  limit (integer, optional, default 5): Max results (1-20)"
    )

    return "\n\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Depth-aware summary generation
# ---------------------------------------------------------------------------

SUMMARY_GENERATION_SYSTEM_PROMPT = """\
Generate a session summary in XML format. You are compacting context
to allow work to continue across a context boundary.

Schema to follow:

<session_summary>
  <meta>
    <session_id>{session_id}</session_id>
    <parent_id>{parent_id}</parent_id>
    <depth>{depth}</depth>
    <timestamp>{timestamp}</timestamp>
    <token_budget>{W}</token_budget>
    <tokens_at_compact>~{tokens_at_compact}k</tokens_at_compact>
  </meta>

  <conditioning>
    <philosophy preset="{philosophy_name}" />
    <framework preset="{framework_name}">
      <current_stage>{{current stage}}</current_stage>
      <stage_history>
        <entry stage="{{stage}}" outcome="{{1-sentence summary}}" />
      </stage_history>
      <pending_gates>
        <gate met="false">{{criterion text}}</gate>
        <gate met="true">{{criterion text}}</gate>
      </pending_gates>
    </framework>
  </conditioning>

  <context>
    <objective>{{top-level goal in plain language}}</objective>
    <background>
      <fact>{{fact}}</fact>
    </background>
    <user_preferences>
      <pref>{{preference}}</pref>
    </user_preferences>
  </context>

  <state>
    <artifacts>
      <artifact path="{{path}}" status="created|modified|deleted">
        {{what this file is and what state it's in}}
      </artifact>
    </artifacts>
    <decisions>
      <decision topic="{{what was decided}}">
        <chosen>{{the decision}}</chosen>
        <rationale>{{why}}</rationale>
      </decision>
    </decisions>
    <working_memory>
      <fact priority="high|medium|low">{{fact}}</fact>
    </working_memory>
  </state>

  <plan>
    <active_threads>
      <thread priority="high|medium|low" status="active|blocked">
        <description>{{what needs to happen}}</description>
        <next_step>{{the very next concrete action}}</next_step>
        <blocked_by>{{if blocked, what's in the way}}</blocked_by>
      </thread>
    </active_threads>
    <completed>
      <item>{{what was done}}</item>
    </completed>
    <open_questions>
      <question>{{question}}</question>
    </open_questions>
  </plan>
</session_summary>

Compression rules:
- Current depth: {depth}
- Compression mode: {depth_compression}
- Maximum summary size: {max_summary_pct}% of {W} tokens (~{max_tokens} tokens)

{compression_rules}

Active conditioning:
- Philosophy: {philosophy_name}
- Framework: {framework_name}

Critical instructions:
1. <working_memory> facts are the highest-value content. Capture every
   non-obvious finding, quirk, or constraint discovered during this
   session. When in doubt, include it. These survive all depths.

2. <user_preferences> are never dropped. How the user communicates,
   what they care about, implicit expectations — record them all.

3. <active_threads> must have concrete next_step values. "Continue
   working on X" is not a next step. "Run tests in api_client.py and
   verify retry logic handles 503 responses" is a next step.

4. <pending_gates> must accurately reflect which exit criteria for the
   current stage are met vs. unmet. The agent will resume at exactly
   this checkpoint.

5. Do NOT pad the summary with generic observations. Every element
   should pass the test: "If this were missing, would the resumed
   agent make a mistake or waste significant time re-deriving it?"
   If no, cut it.

6. Produce ONLY the XML. No preamble, no explanation, no markdown
   fencing."""


GENTLE_COMPRESSION = {
    0: (
        "Depth 0 (gentle): context=Full, decisions=Full with rationale, "
        "working_memory=All, completed=All, stage_history=All, "
        "open_questions=All, user_preferences=All"
    ),
    1: (
        "Depth 1 (gentle): context=Full, decisions=Full with rationale, "
        "working_memory=All, completed=Last 10, stage_history=All, "
        "open_questions=All, user_preferences=All"
    ),
}
GENTLE_DEFAULT = (
    "Depth 2+ (gentle): context=Full, decisions=Outcome only (drop rationale for settled), "
    "working_memory=All (never compressed), completed=Last 5, "
    "stage_history=Last session only, open_questions=Active only, "
    "user_preferences=All (never compressed)"
)

AGGRESSIVE_COMPRESSION = {
    0: (
        "Depth 0 (aggressive): context=Full, decisions=Full, "
        "working_memory=All, completed=All, stage_history=All, "
        "open_questions=All, user_preferences=All"
    ),
    1: (
        "Depth 1 (aggressive): context=Objective + key constraints, "
        "decisions=Outcome only, working_memory=High+medium, "
        "completed=Last 5, stage_history=Current session, "
        "open_questions=High priority, user_preferences=All"
    ),
}
AGGRESSIVE_DEFAULT = (
    "Depth 2+ (aggressive): context=Objective only, "
    "decisions=Only those affecting active threads, "
    "working_memory=High priority only, completed=Omitted, "
    "stage_history=Current stage only, open_questions=Omitted, "
    "user_preferences=All (never compressed)"
)


def get_compression_rules(depth: int, mode: str) -> str:
    """Get the compression rules text for the given depth and mode."""
    if mode == "aggressive":
        return AGGRESSIVE_COMPRESSION.get(depth, AGGRESSIVE_DEFAULT)
    return GENTLE_COMPRESSION.get(depth, GENTLE_DEFAULT)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def build_summary_system_prompt(
    config: dict,
    session_id: str,
    depth: int,
    parent_id: str | None,
    timestamp: str,
    tokens_at_compact: int,
) -> str:
    """Build the depth-aware summary generation system prompt."""
    max_summary_tokens = int(config["context_window"] * config["max_summary_pct"])
    compression_rules = get_compression_rules(depth, config["depth_compression"])

    return SUMMARY_GENERATION_SYSTEM_PROMPT.format(
        session_id=session_id,
        parent_id=str(parent_id or "None"),
        depth=depth,
        timestamp=timestamp,
        W=config["context_window"],
        tokens_at_compact=tokens_at_compact // 1000,
        philosophy_name=config["philosophy"],
        framework_name=config["framework"],
        depth_compression=config["depth_compression"],
        max_summary_pct=int(config["max_summary_pct"] * 100),
        max_tokens=max_summary_tokens,
        compression_rules=compression_rules,
    )


# ---------------------------------------------------------------------------
# Claude CLI subprocess (Max plan — no API key needed)
# ---------------------------------------------------------------------------


class ClaudeCliError(Exception):
    """Claude CLI returned an error."""


def call_claude(
    prompt: str,
    system_prompt: str,
    model: str = "sonnet",
    timeout: int = 600,
    disable_tools: bool = False,
    mcp_config: str | None = None,
    cwd: str | None = None,
    permission_flags: list[str] | None = None,
) -> dict:
    """Call Claude via CLI subprocess. Returns the parsed JSON envelope.

    Based on the pattern from superprompt/agent.py.

    The JSON envelope contains:
      result: str — the model's text response
      usage: {input_tokens: int, output_tokens: int}
      duration_ms: int
    """
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--no-session-persistence",
    ]

    if disable_tools:
        cmd.extend(["--tools", ""])

    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config])

    if permission_flags:
        cmd.extend(permission_flags)

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # Remove CLAUDECODE env var to allow nested Claude Code sessions
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or "/tmp",
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise ClaudeCliError(f"Claude CLI timed out after {timeout}s") from e

    if result.returncode != 0:
        raise ClaudeCliError(
            f"Claude CLI exited with code {result.returncode}: {result.stderr[:500]}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeCliError(f"Failed to parse CLI JSON output: {e}") from e


def format_conversation_as_text(conversation: list[dict]) -> str:
    """Format conversation history as text for CLI input."""
    parts = []
    for msg in conversation:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_result":
                        text_parts.append(f"[Tool result: {block.get('content', '')}]")
                    elif block.get("type") == "tool_use":
                        text_parts.append(f"[Tool call: {block.get('name', '')}]")
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def generate_mcp_config(db_path: str) -> str:
    """Generate MCP config JSON file for the search_sessions server.

    Returns path to the generated config file.
    """
    mcp_server_script = str(SCRIPT_DIR / "mcp_search_server.py")
    config_data = {
        "mcpServers": {
            "sessions": {
                "command": sys.executable,
                "args": [mcp_server_script],
                "env": {"SESSIONS_DB": db_path},
            }
        }
    }
    config_path = SCRIPT_DIR / "data" / "mcp_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config_data, indent=2))
    return str(config_path)


def build_allowed_tools_flags(config: dict, include_mcp: bool = True) -> list[str]:
    """Build --allowedTools CLI flags from config.

    Returns a list of CLI arguments, e.g.:
        ["--allowedTools", "Read(//data/home/user/**)", "--allowedTools", "Bash"]

    If allowed_tools is "dangerously_skip_all", returns
    ["--dangerously-skip-permissions"] instead.
    """
    tools = config.get("allowed_tools", [])

    if tools == "dangerously_skip_all":
        return ["--dangerously-skip-permissions"]

    if not tools:
        return []

    wd = config.get("working_directory", "")
    file_tools = {"Read", "Write", "Edit", "Glob", "Grep"}

    flags: list[str] = []
    for tool in tools:
        if "(" in tool:
            # Already has a specifier (e.g. "Bash(npm test)") — pass as-is
            flags.extend(["--allowedTools", tool])
        elif wd and tool in file_tools:
            # Scope file tools to the working directory
            path_part = wd.lstrip("/")
            flags.extend(["--allowedTools", f"{tool}(//{path_part}/**)"])
        else:
            flags.extend(["--allowedTools", tool])

    if include_mcp:
        flags.extend(["--allowedTools", "mcp__sessions__search_sessions"])

    return flags


# ---------------------------------------------------------------------------
# Compact (via Claude CLI)
# ---------------------------------------------------------------------------


def compact_with_conditioning(
    config: dict,
    conn,
    conversation: list[dict],
    current_depth: int,
    current_parent_id: str | None,
    tokens_at_compact: int,
) -> tuple[str, list[dict], int, str]:
    """
    Run the compaction cycle with conditioning-aware summary generation.

    Calls Claude via CLI to generate a depth-aware session summary,
    stores it in SQLite, and rebuilds the system prompt.

    Returns (new_system_prompt, new_conversation, new_depth, new_parent_id).
    """
    session_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    new_depth = current_depth + 1

    # Build the enhanced summary prompt
    summary_prompt = build_summary_system_prompt(
        config, session_id, current_depth, current_parent_id, timestamp, tokens_at_compact
    )

    print("\n[ORCHESTRATOR] Compacting context... generating session summary.")

    # Format conversation for summary generation
    conversation_text = format_conversation_as_text(conversation)

    # Call Claude CLI — no tools needed for summary generation
    envelope = call_claude(
        prompt=f"Summarize the following conversation for context continuity:\n\n{conversation_text}",
        system_prompt=summary_prompt,
        model=config["model"],
        disable_tools=True,
    )

    summary_xml = envelope.get("result", "").strip()

    # Strip any markdown fencing the model might have added
    if summary_xml.startswith("```"):
        lines = summary_xml.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        summary_xml = "\n".join(lines)

    token_est = estimate_tokens(summary_xml)

    # Store via auto_compact's db layer (with conditioning metadata)
    store_session(
        conn,
        session_id=session_id,
        parent_id=current_parent_id,
        depth=new_depth,
        timestamp=timestamp,
        summary_xml=summary_xml,
        philosophy=config["philosophy"],
        framework=config["framework"],
        token_estimate=token_est,
    )

    session_count = count_sessions(conn)

    print(f"[ORCHESTRATOR] Session {session_id[:8]}... stored (depth={new_depth}, ~{token_est} tokens).")
    print(f"[ORCHESTRATOR] Total sessions in database: {session_count}")
    print("[ORCHESTRATOR] Bootstrapping new context...\n")

    # Re-read config in case it was edited
    config = load_config()

    # Bootstrap: rebuild full system prompt with session summary in layer 4
    new_session = {
        "id": session_id,
        "parent_id": current_parent_id,
        "depth": new_depth,
        "created_at": timestamp,
        "summary_xml": summary_xml,
        "session_count": session_count,
    }

    new_system_prompt = assemble_system_prompt(config, new_session)
    new_conversation = []  # Fresh — all context is in the system prompt now
    new_parent_id = session_id

    return new_system_prompt, new_conversation, new_depth, new_parent_id


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_loop(
    config: dict,
    conn,
    system_prompt: str,
    depth: int,
    parent_id: str | None,
    mcp_config_path: str | None,
) -> None:
    """Run the main conversation loop via Claude CLI."""
    conversation: list[dict] = []
    permission_flags = build_allowed_tools_flags(config)

    print("=" * 60)
    print("  Auto-Compact Agent Conditioning v1.0 (Max plan)")
    print(f"  Model: {config['model']}")
    print(f"  Philosophy: {config['philosophy']}")
    print(f"  Framework: {config['framework']}")
    print(f"  Context window: {config['context_window']:,} tokens")
    print(f"  Compact threshold: {config['compact_threshold'] * 100:.0f}%")
    wd = config.get("working_directory", "")
    if wd:
        print(f"  Working directory: {wd}")
    if depth > 0:
        print(f"  Resuming from depth: {depth - 1} (parent: {parent_id[:8] if parent_id else 'None'}...)")
    else:
        print("  Fresh session (no prior context)")
    print("=" * 60)
    print("\nType your message (or 'quit' to exit).\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "/quit", "/exit"):
            print("Exiting.")
            break

        # Handle manual /compact command
        if user_input.strip().lower() == "/compact" and conversation:
            print("[Compacting...]")
            system_prompt, conversation, depth, parent_id = compact_with_conditioning(
                config, conn, conversation, depth, parent_id,
                tokens_at_compact=int(config["context_window"] * config["compact_threshold"]),
            )
            print(f"[Compacted. New depth: {depth}]")
            continue

        conversation.append({"role": "user", "content": user_input})

        # Format full conversation as the prompt
        prompt_text = format_conversation_as_text(conversation)

        # Call Claude via CLI — tool use handled by MCP server
        try:
            envelope = call_claude(
                prompt=prompt_text,
                system_prompt=system_prompt,
                model=config["model"],
                mcp_config=mcp_config_path,
                cwd=config.get("working_directory") or None,
                permission_flags=permission_flags,
            )
        except ClaudeCliError as e:
            print(f"\n[ERROR] {e}\n")
            conversation.pop()
            continue

        response_text = envelope.get("result", "")
        usage = envelope.get("usage", {})
        total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        if response_text:
            print(f"\nAssistant: {response_text}\n")
            conversation.append({"role": "assistant", "content": response_text})

        # --- Token check ---
        ratio = total_tokens / config["context_window"] if config["context_window"] else 0

        if ratio >= config["compact_threshold"]:
            print(f"\n[ORCHESTRATOR] Token usage: {total_tokens:,} / {config['context_window']:,} "
                  f"({ratio:.1%}) — threshold {config['compact_threshold']:.0%} reached.")
            system_prompt, conversation, depth, parent_id = compact_with_conditioning(
                config, conn, conversation, depth, parent_id, total_tokens
            )
        elif ratio >= 0.5:
            print(f"[tokens: ~{total_tokens // 1000}k / {config['context_window'] // 1000}k ({ratio:.0%})]")


def main():
    """Entry point."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)

    # Initialize DB via auto_compact
    conn = init_db(Path(config["compact_db"]))

    # Generate MCP config for search_sessions tool
    mcp_config_path = generate_mcp_config(config["compact_db"])

    # Check for existing session to resume
    latest_session = get_latest_session(conn)

    if latest_session is not None:
        latest_session["session_count"] = count_sessions(conn)
        system_prompt = assemble_system_prompt(config, latest_session)
        depth = latest_session["depth"] + 1
        parent_id = latest_session["id"]
    else:
        system_prompt = assemble_system_prompt(config, session_summary=None)
        depth = 0
        parent_id = None

    run_loop(config, conn, system_prompt, depth, parent_id, mcp_config_path)
    conn.close()


if __name__ == "__main__":
    main()
