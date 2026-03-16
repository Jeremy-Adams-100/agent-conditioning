# Stage 1: User Onboarding

## Goal

A new user goes from zero to running their first exploration in
under 5 minutes. Three steps: create account, connect Claude,
connect Wolfram.

## Signup Flow

```
┌─────────────────────────────────────────────┐
│  Step 1: Create Account                     │
│                                             │
│  Email: [________________________]          │
│  Password: [____________________]           │
│                                             │
│  [Create Account]                           │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Step 2: Connect Claude                     │
│                                             │
│  Do you have a Claude account?              │
│                                             │
│  [Yes, connect existing]  [No, create free] │
│                                             │
│  "Yes" → paste Claude session token         │
│  "No"  → link to claude.ai/signup, then     │
│           return and paste token             │
│                                             │
│  Detected plan: Free / Max                  │
│  [Continue]                                 │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Step 3: Connect Wolfram Engine             │
│                                             │
│  1. Click: [Get Free Wolfram Engine]        │
│     (links to wolfram.com/engine)           │
│  2. Create account, get license key         │
│  3. Paste license key here:                 │
│     [________________________]              │
│                                             │
│  ☑ I confirm this is for personal,          │
│    non-commercial research purposes.        │
│                                             │
│  [Complete Setup]                           │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Ready!                                     │
│                                             │
│  explore [_________________________] [Go]   │
│                                             │
│  Your plan: Free (upgrade to Max for        │
│  faster cycles and deeper context)          │
└─────────────────────────────────────────────┘
```

## Claude Authentication

The user needs to authenticate `claude` CLI on their VM. Two
approaches, from simplest to most robust:

### Option A: Session Token (simplest)

User runs `claude auth` interactively on first login, or the
platform provides a guided OAuth-style flow:

1. User clicks "Connect Claude" on the website
2. Website opens Claude's login page in a new tab
3. User logs in to Claude
4. User copies a session token from their Claude account settings
5. User pastes it into the platform
6. Backend passes the token to the VM via `claude setup-token`

**Pros:** Simple, no OAuth integration needed.
**Cons:** Token may expire, user has to re-paste periodically.

### Option B: Guided CLI Auth (more robust)

1. Backend provisions the VM
2. Backend runs `claude auth` on the VM
3. Claude CLI generates a URL + code
4. Website shows the URL + code to the user
5. User opens the URL, logs in, enters the code
6. Claude CLI on the VM is now authenticated

**Pros:** Standard auth flow, long-lived session.
**Cons:** Requires the VM to be provisioned before auth completes.

### Recommendation

Start with **Option A** (token paste). It's the simplest and gets
users running fastest. The `claude setup-token` command exists
specifically for this use case. If tokens expire frequently, upgrade
to Option B later.

## Wolfram Engine Authentication

1. User creates a Wolfram account at wolfram.com/engine
2. User receives a license key (free for personal use)
3. User pastes the key into the platform
4. Backend runs `wolframscript -activate <key>` on the user's VM
5. Verification: backend runs `wolfram -run "Print[1+1]"` and
   checks for output "2"

This can be fully automated from the website — the user just
pastes their key. Activation takes seconds.

## Data Model

```sql
CREATE TABLE users (
    id          TEXT PRIMARY KEY,    -- UUID
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,       -- bcrypt hash
    created_at  TEXT NOT NULL,
    tier        TEXT DEFAULT 'free', -- 'free' or 'max'
    claude_token TEXT,               -- encrypted
    wolfram_key TEXT,                -- encrypted
    vm_id       TEXT,                -- reference to provisioned VM
    vm_status   TEXT DEFAULT 'none'  -- none/provisioning/ready/stopped
);
```

## What's NOT in Stage 1

- OAuth with Claude (use token paste instead)
- Commercial Wolfram license linking (deferred)
- Email verification (add in Stage 6)
- Password reset flow (add in Stage 6)
