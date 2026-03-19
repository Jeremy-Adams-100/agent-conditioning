# Interact Agent: --allowedTools Path Scoping Investigation

Date: 2026-03-19

## Problem

The interact agent needs workspace isolation: write access to its own
workspace (`INTERACT_WORKSPACE`) but read-only access to the explorer
workspace (`WORKING_DIR`). The initial implementation used path-scoped
`--allowedTools` flags to enforce this:

```
--allowedTools "Write(//data/home/jadams2/wolfram-bridge/interact/**)"
--allowedTools "Read(//data/home/jadams2/wolfram-bridge/**)"
```

## Test Results

### Test 1: Path-scoped Write — DENIED

```bash
cd /data/home/jadams2/wolfram-bridge/interact
echo "Write 'hello' to /data/home/jadams2/wolfram-bridge/interact/test.txt" | \
  claude -p --output-format json --model opus --no-session-persistence \
  --allowedTools "Write(//data/home/jadams2/wolfram-bridge/interact/**)"
```

**Result**: Write tool call was DENIED. The `permission_denials` array in
the JSON response contained the Write call. The agent reported the write
was blocked.

### Test 2: Unscoped Write — APPROVED

```bash
cd /data/home/jadams2/wolfram-bridge/interact
echo "Write 'hello' to /data/home/jadams2/wolfram-bridge/interact/test.txt" | \
  claude -p --output-format json --model opus --no-session-persistence \
  --allowedTools "Write"
```

**Result**: Write succeeded. File created at the expected path. Zero
permission denials.

### Test 3: Unscoped Write to path outside CWD — DENIED

```bash
cd /data/home/jadams2/wolfram-bridge/interact
echo "Write 'test' to /data/home/jadams2/wolfram-bridge/workspace/rogue.txt" | \
  claude -p --output-format json --model opus --no-session-persistence \
  --allowedTools "Write" --allowedTools "Read"
```

**Result**: Write DENIED. Claude Code enforced the CWD boundary:
"That path is outside the allowed working directory for this session."
The `permission_denials` array contained 1 denial. No file was created.

## Findings

1. **Path-scoped `--allowedTools` does NOT auto-approve in `-p` mode.**
   The `Tool(//path/**)` syntax appears to filter which tools are
   *available*, but does not grant *permission* to use them in
   non-interactive mode. In `-p` mode, only unscoped tool names (e.g.,
   `Write`, `Read`, `Edit`) auto-approve.

2. **Unscoped `--allowedTools` DOES auto-approve in `-p` mode.**
   Specifying `--allowedTools "Write"` grants the tool and auto-approves
   all invocations.

3. **CWD enforcement is the effective isolation mechanism.**
   Claude Code's working directory boundary (set via `cwd` in
   `subprocess.run`) prevents writes to paths outside the CWD, even
   when the Write tool is unscoped. This is robust — the agent itself
   reports the boundary and refuses to write.

4. **The exploration agents use the same pattern.** The orchestrator's
   `build_allowed_tools_flags()` generates path-scoped flags like
   `Write(//data/home/jadams2/wolfram-bridge/**)`, but these work on
   the VM because the VM's Claude Code settings pre-grant broader
   permissions. In local dev, the CWD enforcement is the backstop.

## Solution Applied

The interact agent uses:
- **Unscoped** `Write`, `Edit`, `Read`, `Glob`, `Grep` in `--allowedTools`
  (auto-approved in `-p` mode)
- **CWD** set to `INTERACT_WORKSPACE` (prevents writes outside it)
- **System prompt** explicitly states the explorer workspace is read-only
- **Bash** restricted to `wolfram` and `pandoc` only (no shell access to
  bypass workspace boundaries)

This provides:
- **Hard enforcement**: CWD boundary blocks writes outside interact workspace
- **Hard enforcement**: Bash restricted to two specific binaries
- **Soft enforcement**: System prompt instructs agent not to modify explorer files
- **Read access**: Unscoped Read/Glob/Grep can access both workspaces (the
  CWD boundary only restricts *writes*, not reads — Claude Code allows reading
  outside CWD)

## Remaining Risk

The agent could theoretically read explorer workspace files and copy their
content into new files in the interact workspace via Write. This is
acceptable — the interact agent's purpose is to work with explorer data.
The risk is that it cannot *modify* the explorer's original files.

## Code Change

`platform/vm_agent/agent.py` — `_build_interact_tools()` updated to use
unscoped tool names instead of path-scoped ones.
