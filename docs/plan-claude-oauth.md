# Claude OAuth Auto-Connection Plan

## Goal

Users click "Connect Claude" on the Q.E.D. website and authenticate
via their browser — no CLI installation, no token pasting. The VM's
Claude Code CLI is authenticated automatically.

## How Claude Code Auth Works

Claude Code CLI uses OAuth 2.0 with Anthropic as the provider:

1. `claude auth` generates an authorization URL + device code
2. User visits the URL in their browser, logs in, approves
3. Claude CLI polls for the token exchange to complete
4. Credentials saved to `~/.claude/.credentials.json`

The `setup-token` command is a shortcut that accepts an existing
OAuth token directly, skipping the browser flow.

## Proposed Flow

```
User clicks "Connect Claude" on Q.E.D.
    ↓
Backend tells VM agent to start auth flow
    ↓
VM agent runs: claude auth (captures the auth URL from output)
    ↓
Backend returns the URL to the frontend
    ↓
Frontend opens the URL in a new tab
    ↓
User logs into Claude in the browser, clicks "Approve"
    ↓
Claude CLI on the VM receives the token (polling completes)
    ↓
VM agent confirms auth success
    ↓
Frontend shows "Claude connected" + detected tier
```

## Implementation

### VM Agent: POST /auth-claude

```python
@app.post("/auth-claude")
def start_claude_auth(_=Depends(_auth)):
    """Start Claude CLI auth and return the browser URL."""
    proc = subprocess.Popen(
        ["claude", "auth"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Read output until we find the URL
    url = None
    for line in proc.stdout:
        if "http" in line:
            url = line.strip()
            break
    if not url:
        return {"status": "error", "detail": "Could not get auth URL"}
    return {"status": "pending", "auth_url": url, "pid": proc.pid}
```

### VM Agent: GET /auth-claude-status

```python
@app.get("/auth-claude-status")
def check_claude_auth(_=Depends(_auth)):
    """Check if Claude CLI is authenticated."""
    creds = Path.home() / ".claude" / ".credentials.json"
    if creds.exists():
        data = json.loads(creds.read_text())
        oauth = data.get("claudeAiOauth", {})
        if oauth.get("accessToken"):
            return {
                "status": "authenticated",
                "subscription": oauth.get("subscriptionType", "unknown"),
            }
    return {"status": "not_authenticated"}
```

### Backend: POST /api/onboard/claude-auth

```python
@router.post("/claude-auth")
async def start_claude_auth(user=Depends(get_current_user)):
    client = get_vm_client(user)
    result = await client._client.post("/auth-claude")
    return result.json()  # {auth_url: "https://...", status: "pending"}
```

### Frontend: Onboard Step 1

```
Instead of token paste:
1. User clicks "Connect Claude Account"
2. Frontend calls POST /api/onboard/claude-auth
3. Backend returns {auth_url: "https://console.anthropic.com/..."}
4. Frontend opens auth_url in new tab
5. Frontend polls GET /api/onboard/claude-status every 3s
6. When status = "authenticated" → show success, advance to step 2
```

## Prerequisites

- VM must be provisioned BEFORE Claude auth (the CLI runs on the VM)
- This means onboarding order changes:
  1. Sign up
  2. Link Wolfram key (triggers VM provisioning)
  3. VM ready → Connect Claude (OAuth flow on VM)
- Or: provision a temporary VM for auth, then assign it to the user

## Complexity Assessment

| Component | Effort | Risk |
|-----------|--------|------|
| VM agent endpoints | Low (~20 lines) | Low |
| Backend proxy | Low (~10 lines) | Low |
| Frontend changes | Medium (~40 lines) | Medium (polling, tab management) |
| Auth URL parsing | Medium | `claude auth` output format may change |
| Onboarding reorder | Low | Minor UX change |

**Total:** ~70 lines of code. Main risk is parsing `claude auth` output —
it's not a documented API, so the output format could change between
versions. Mitigation: pin Claude Code CLI version in the base image.

## When to Implement

After MVP launch if token-paste friction is a significant drop-off
point in the signup funnel. The current token-paste flow works —
it's just less polished. Monitor signup completion rates to decide.

## Alternative: Setup-Token Link

A simpler alternative that avoids parsing CLI output:

1. Frontend shows: "Log in to Claude, then click this link to
   generate a setup token"
2. Link goes to a Claude page where users can generate tokens
3. User pastes the token

This requires Anthropic to provide a web UI for generating
setup tokens, which they may or may not offer.
