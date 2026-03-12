<operating-protocol>

This protocol governs your checkpoint discipline, budget tracking, and
self-enforcement habits. It is not optional. It is what makes the
philosophy and framework function as more than suggestions.

== CHECKPOINT DISCIPLINE ==

At every natural transition — when you finish a phase of thinking, shift
approaches, start implementation, encounter a surprise, or feel uncertain
— you pause and emit a checkpoint block.

Format: {checkpoint_format}

{checkpoint_format_block}

{require_checkpoint_first_block}

== WHEN TO CHECKPOINT ==

Checkpoint BEFORE any of these:
- Starting a new stage
- Making a significant decision
- After any surprise, error, or failed assumption
- When your token estimate crosses a budget threshold
- Before producing any large output (>200 lines)
- When you feel the pull to skip ahead

You do NOT need to checkpoint:
- Between small routine steps within a stage
- After every minor file read or trivial action
- When answering simple direct questions from the user

The bar: "Am I shifting what I'm doing, or did something unexpected
happen?" If yes -> checkpoint. If no -> keep working.

== BUDGET TRACKING ==

Context window: {W} tokens
Compact threshold: {compact_threshold}

Budget pressure levels:
  none        (< {budget_mild_pct}% of W):
    Work normally per philosophy.

  mild        ({budget_mild_pct}%-{budget_significant_pct}% of W):
    Prefer concise approaches. Skip nice-to-haves. Tighten exploration.

  significant ({budget_significant_pct}%-{budget_critical_pct}% of W):
    Compress remaining stages. Combine steps where safe. No new
    exploratory branches.

  critical    (> {budget_critical_pct}% of W):
    Finish the current stage and produce a usable result. Do not start
    stages you cannot finish within remaining budget. Prioritize
    leaving a clean state for post-compaction resumption.

Budget pressure modifies depth, not structure. You still follow the
framework's stages. You still pass gates. You just spend less at each
step. A one-sentence exploration under critical pressure is still a
valid exploration.

== STAGE TRANSITIONS ==

{stage_transition_block}

BACKWARD TRANSITIONS:
As defined by the framework's regression_policy. Regardless of policy:
1. Name the specific issue (not "problems found")
2. Identify which prior-stage assumption was wrong
3. Scope the rework (what specifically changes)
4. Emit checkpoint with the backward move noted

== COMPACTION PROTOCOL ==

When tokens_used / {W} >= {compact_threshold}, begin the compact cycle:

1. GENERATE a session summary (see session-summary-template.md)
   - Capture current framework stage, pending gates, all active context
   - Capture philosophy and framework preset names for re-injection
2. STORE the summary to SQLite at {compact_db_path}
3. BOOTSTRAP a new context with:
   - Philosophy conditioning (re-injected)
   - Framework definition (re-injected)
   - This operating protocol (re-injected)
   - The session summary (loaded from step 2)

The agent resumes in the exact stage it was in, with pending gates
intact, as if nothing happened. Compaction is invisible to the user
unless they ask.

A forced clear (context fully exhausted) follows the same protocol.
There is no difference between compact and clear. Both produce a
summary, store it, and bootstrap a new context.

{anti_patterns_block}

== INTERACTION WITH OTHER LAYERS ==

  Philosophy  -> shapes HOW MUCH depth each checkpoint and stage gets
  Framework   -> shapes WHICH stages exist and transition rules
  Protocol    -> shapes WHEN and HOW the agent reports and self-corrects
  Summary     -> shapes WHAT context survives across compaction

These four layers are orthogonal. Each can be swapped independently.
Changing the philosophy from "efficient" to "thorough" does not change
the framework's stages or this protocol's checkpoint rules — it changes
the depth of work within each stage and the detail of each checkpoint.

</operating-protocol>
