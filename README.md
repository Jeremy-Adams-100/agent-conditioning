# Agent Conditioning

A configurable conditioning layer for LLM agents. It shapes **how** an agent works (philosophy), **what stages** it follows (framework), and **how it self-enforces** (operating protocol) — all driven by a single config file.

Runs on the **Claude Code Max plan** — no API key needed. Uses Claude Code CLI as the model backend via subprocess, so all usage is covered by your Max subscription.

Built on top of [auto-compact](../auto-compact/), which handles context persistence and session search via SQLite.

## Quick Start

```bash
# Prerequisites: auto-compact must be installed
cd ../auto-compact && pip install -e .

# Run with defaults (efficient philosophy, staged framework)
cd agent-conditioning/agent
python3 orchestrator.py
```

No API key required. The orchestrator calls `claude -p` under the hood, which uses your Max plan.

The agent will use the `efficient` philosophy, follow the `staged` framework (Explore -> Plan -> Execute -> Test -> Document), and compact automatically at 90% of the 1M context window.

## How It Works

The orchestrator reads `config.yaml` and assembles a system prompt from four template layers:

```
1. Philosophy     — voice, tradeoff posture, depth calibration
2. Framework      — stages, gates, transition rules
3. Protocol       — checkpoint discipline, budget tracking, anti-patterns
4. Session Summary — restored context after compaction (if resuming)
```

Each layer is a `.md` template in `agent/templates/` with `{variable}` placeholders filled from the config and preset defaults. The assembled prompt is passed to `claude -p --system-prompt "..."` via subprocess.

When token usage hits the compact threshold, the orchestrator generates a depth-aware XML summary, stores it in SQLite (via auto-compact), rebuilds the system prompt with the summary in layer 4, and continues with a fresh conversation. The agent picks up exactly where it left off.

### Claude Code Integration

The orchestrator uses the same pattern proven in the superprompt project:

```python
subprocess.run(
    ["claude", "-p", "--output-format", "json", "--model", model,
     "--no-session-persistence", "--system-prompt", system_prompt],
    input=prompt, env={...without CLAUDECODE...}, ...
)
```

Key details:
- `claude -p` runs in non-interactive print mode
- `--output-format json` returns `{"result": "...", "usage": {"input_tokens": N, "output_tokens": N}}`
- `--no-session-persistence` keeps each call stateless
- `env.pop("CLAUDECODE")` allows nested invocation from within Claude Code
- `search_sessions` is exposed via an MCP server (`--mcp-config`)

## The Config File

Edit `agent/config.yaml`. The minimal version:

```yaml
model: opus
context_window: 1000000
model_tier: opus
compact_threshold: 0.90
philosophy: efficient
framework: staged
checkpoint_format: standard
```

The `model` field accepts aliases (`sonnet`, `opus`, `haiku`) or full model names (`claude-opus-4-6`).

### Philosophy Presets

| Preset | Budget | Speed | Quality | Best For |
|--------|--------|-------|---------|----------|
| `efficient` | low | high | medium | Ship fast, stay within budget |
| `thorough` | high | low | high | Peer-review quality, careful work |
| `research` | high | low | high | Deep investigation, hypothesis-driven |
| `prompt` | minimal | high | — | Expand ambiguous prompts into clear specs |
| `audit` | high | medium | high | Multi-cycle defect finding and fixing |
| `custom` | you decide | you decide | you decide | Your own voice and tradeoffs |

### Framework Presets

| Preset | Stages | Transitions | Best For |
|--------|--------|-------------|----------|
| `staged` | Explore -> Plan -> Execute -> Test -> Document | Strict gates, one-step regression | Most tasks |
| `loop` | Build -> Measure -> Adjust (repeat) | Relaxed, iterate until convergence | Optimization, tuning |
| `freeform` | Working (single stage) | No mandatory gates | Brainstorming, Q&A |
| `prompt` | Clarify -> Write | Strict, no regression | Prompt expansion |
| `audit` | Explore -> Execute -> Test -> Document | Strict, multi-cycle | Defect-driven auditing |
| `custom` | You define | You define | Domain-specific workflows |

### Other Settings

```yaml
# Checkpoint format: standard | minimal | verbose
checkpoint_format: standard

# Force agent to open every response with a checkpoint
require_checkpoint_first: false

# Require user approval at stage transitions
user_gate_approval: false

# Include named failure modes (The Leap, The Spiral, etc.) in the prompt
anti_patterns_enabled: true

# Compaction settings
compact_db: ./data/sessions.db
max_summary_pct: 0.15          # max % of context window for summaries
depth_compression: gentle      # gentle | aggressive
```

### Permissions

Since the orchestrator runs `claude -p` (non-interactive mode), there is no way to approve tool permissions interactively. All permissions must be pre-configured in `config.yaml`.

```yaml
# Directory the agent can access (absolute path)
# File tools are automatically scoped to this path.
working_directory: /data/home/jadams2

# Tools allowed without interactive approval
allowed_tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
```

**How it works:** File tools (`Read`, `Write`, `Edit`, `Glob`, `Grep`) are automatically scoped to `working_directory` using Claude Code's path permission syntax (e.g. `Read(//data/home/jadams2/**)`). `Bash` is unrestricted by default. The MCP tool `search_sessions` is always added automatically.

**To configure for your environment**, change `working_directory` to your project root or home directory. The agent will only be able to read, write, and search files under that path.

**Restricting Bash commands:** Replace `Bash` with specific patterns to limit what the agent can run:

```yaml
allowed_tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - "Bash(python3 *)"
  - "Bash(npm test)"
  - "Bash(git *)"
```

**Skip all permission checks** (not recommended — use only in isolated environments):

```yaml
allowed_tools: dangerously_skip_all
```

**If the agent hits a permission error**, the CLI call will fail and the orchestrator will print the error. To fix it, add the needed tool to `allowed_tools` in `config.yaml` and restart.

**Other tools you may want to add:**

| Tool | Purpose | When to add |
|------|---------|-------------|
| `WebFetch` | Fetch URLs | Agent needs to read web pages or APIs |
| `WebSearch` | Web search | Agent needs to search the internet |

### Custom Philosophy

Set `philosophy: custom` and provide your own values. Missing keys fall back to the `efficient` defaults:

```yaml
philosophy: custom
custom_philosophy:
  budget: medium
  speed: high
  quality: high
  complexity: low
  voice: |
    You are a startup engineer building an MVP. Speed matters,
    but this is going to production. Move fast, don't ship bugs.
  explore_depth: |
    Quick scan. One viable approach unless the problem is novel.
```

### Custom Framework

Set `framework: custom` and define your own stages with gates:

```yaml
framework: custom
custom_framework:
  transition_rule: strict
  regression_policy: one_step
  skip_policy: never
  max_regressions: 3
  stages:
    - name: read
      purpose: "Read the code under review in full."
      gates:
        - "Have I read every file in the changeset?"
        - "Can I describe what the change does?"
      output: "Changeset summary."
    - name: analyze
      purpose: "Evaluate correctness and maintainability."
      gates:
        - "Are findings categorized (blocking / suggestion / nit)?"
      output: "Categorized findings list."
```

## Architecture

```
agent-conditioning/
├── README.md
└── agent/
    ├── config.yaml                        # Your settings
    ├── orchestrator.py                    # Interactive single-agent loop
    ├── conductor.py                       # Multi-agent score execution
    ├── exploration.py                     # Continuous exploration conductor
    ├── exploration-score.yaml             # Default exploration score
    ├── mcp_search_server.py               # MCP server for session tools
    ├── templates/
    │   ├── philosophy-template.md         # Layer 1
    │   ├── framework-template.md          # Layer 2
    │   ├── operating-protocol-template.md # Layer 3
    │   └── session-summary-template.md    # Layer 4
    ├── data/
    │   ├── sessions.db                    # Single source of truth
    │   ├── exploration_state.json         # Ephemeral exploration state
    │   └── mcp_config.json                # Generated at runtime
    └── output/
        └── exploration_status.md          # Overwritten each cycle
```

**Dependencies:**
- `auto_compact.db` — SQLite operations (init, store, search, retrieve)
- `claude` CLI — model calls via Max plan (no API key)
- `pyyaml` — config file parsing

## Relationship to auto-compact

auto-compact is a standalone tool for persistent context management. It handles:
- SQLite schema and FTS5 search
- Session storage and retrieval

Agent Conditioning adds:
- Configurable philosophy, framework, and operating protocol
- Template-driven system prompt assembly
- Depth-aware compression rules for summaries
- Conditioning metadata stored with each session
- Claude Code Max plan integration (no API billing)

Both can be used independently. auto-compact's standalone CLI still uses the Anthropic API directly. Agent Conditioning routes all model calls through `claude -p` instead.

## Continuous Exploration

A three-agent loop (researcher → worker → auditor) that explores a domain autonomously, running indefinitely until stopped. Each agent maintains persistent context across cycles via Claude Code session persistence.

### Quick Start

```bash
# Start with an inline task
cd agent-conditioning
python -m agent.exploration start "Explore foundations of microlocal analysis"

# Or edit the task in the score file and start without override
vi agent/exploration-score.yaml
python -m agent.exploration start
```

### Commands

All commands accept optional `--score`, `--config`, `--output`, `--state` flags.

| Command | Effect |
|---------|--------|
| `exploration start` | Start exploration using task from score YAML |
| `exploration start "topic description"` | Start with inline task (archives + clears any existing state) |
| `exploration stop` | Send stop signal — finishes current agent, saves state |
| `Ctrl+C` | Same as `stop`, when watching the terminal |
| `exploration clear` | Stop + archive state + clear context for new topic |
| `exploration resume` | Continue from saved state |
| `exploration resume path/to/archived_state.json` | Restore and continue a specific past exploration |

### Lifecycle

```
exploration start "topic A"     # begins cycles
  ... cycles run ...
exploration stop                # saves state, exits
exploration resume              # picks up where it left off
  ... more cycles ...
exploration clear               # archives state, clears context
exploration start "topic B"     # fresh start, new topic
  ... cycles run ...
exploration resume data/exploration_state_20260316T1400.json
                                # revisit topic A from archived state
```

### How It Works

Each cycle runs three agents sequentially:

1. **Researcher** (philosophy: research) — reads the audit report from the previous cycle, determines the next sub-topic, produces a research brief
2. **Worker** (philosophy: efficient) — reads the research brief, builds tools/models/scripts, produces concrete results
3. **Auditor** (philosophy: audit) — validates the worker's results, decides: VALIDATED (move on), CONTINUE (same topic), or PIVOT (change direction)

The audit report feeds back to the researcher on the next cycle. No orchestrator agent — the conductor is a deterministic loop.

### Context Persistence

Each agent type has its own Claude Code session UUID, persisted across cycles and stop/resume. Context accumulates naturally — the researcher remembers its prior reasoning, the worker remembers what it built, the auditor remembers what it validated.

When an agent's context exceeds the compact threshold (default 90% of 1M = 900k tokens), auto-compact triggers: the agent summarizes its context, the summary is stored in sessions.db, and a fresh session is bootstrapped with the summary.

### Data Storage

**sessions.db** is the single source of truth. Every agent output and compaction summary is stored with `record_type="exploration"` or `"compaction"`. All records are FTS-searchable.

**exploration_state.json** is ephemeral — it holds the current cycle, results, failure counters, and agent session UUIDs for resume. Overwritten each cycle.

When you **clear**, the state file is archived with a timestamp (e.g., `exploration_state_20260316T1400.json`) before being reset. Use `--resume <file>` to restore a previous exploration.

### Failure Handling

| Agent fails | Response |
|---|---|
| Researcher | Skip cycle, retry next cycle with same audit report |
| Worker | Pass failure marker to auditor, auditor decides next step |
| Auditor | Use fallback "CONTINUE", research stays on current topic |
| 3x same agent | 60s pause, then auto-retry |
| 3x any failure | 60s pause |
| 3+ total failure cycles | 10min backoff (likely outage) |

### Configuration

Edit `exploration-score.yaml`:

```yaml
task: |
  Your exploration directive here.

loop:
  max_cycles: null               # null = unlimited
  cycle_cooldown_seconds: 30     # pause between cycles
```

Each agent can override philosophy, framework, and model in the score file. See `exploration-score.yaml` for the full agent role definitions.

## Security

### Exploration Agent Permissions

Exploration agents (researcher, worker, auditor) are restricted to:

| Tool | Scope | Enforcement |
|------|-------|-------------|
| Read, Write, Edit, Glob, Grep | `working_directory` only | Claude Code path permissions — hard enforcement |
| Bash | `wolfram -script` only | Claude Code `--allowedTools` pattern — hard enforcement |
| WebSearch | Unrestricted | Read-only, no exfiltration risk |
| MCP session tools | Own sessions.db | Scoped to configured DB path |

Agents **cannot**: run Python, access git/gh, read `.env` or credentials, modify the agent-conditioning codebase, install packages, or execute arbitrary shell commands.

### Security Layers

| Layer | Protects against | Notes |
|-------|-----------------|-------|
| Claude's built-in safety | Malicious content generation | Baseline — no replication needed |
| File tool scoping | File access outside working_directory | Hard enforcement by Claude Code |
| Bash restriction (Wolfram only) | Shell commands, Python execution, data exfil | Hard enforcement by Claude Code |
| Wolfram shell functions (`Run[]`, `RunProcess[]`) | Not blocked at CLI level | Extremely low practical risk — Wolfram is a science tool, not an attack platform. Claude's conditioning resists generating shell payloads through multi-agent research pipelines |
| VM / virtual desktop isolation | Cross-user access, system compromise | Recommended for multi-user deployment. The VM is the blast radius — nothing beyond it to compromise |

### Multi-User Deployment

For multi-user, each user needs:
- Own `working_directory` (file tool isolation)
- Own `sessions.db` (session data isolation)
- Own `exploration_state.json` (state isolation)
- VM or virtual desktop (OS-level blast radius)

OS-level containerization beyond VM isolation is not required. The realistic threat is resource abuse (infinite loops, disk fill), not security exploits. Address with timeouts and disk quotas at the hosting level.

## Changing Settings

**Safe to change anytime** (takes effect at next compaction):
- `philosophy`, `framework`, `checkpoint_format`
- `compact_threshold`, `anti_patterns_enabled`
- `require_checkpoint_first`, `user_gate_approval`

**Requires restart:**
- `model`, `context_window`, `compact_db`
- `working_directory`, `allowed_tools`

Edit `config.yaml` and either wait for the next compaction or type `/compact` to force one.

## Commands

| Input | Effect |
|-------|--------|
| `/compact` | Force immediate compaction |
| `quit` or `exit` | Exit the session |
| Ctrl+C / Ctrl+D | Exit the session |
