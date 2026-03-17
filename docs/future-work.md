# Future Work

Issues identified during Stage 1-3 audit that are not MVP-blocking.
Address these during Stage 6 (Polish & Hardening) or as needed.

## Backend

- **Add logging throughout** — provision.py, idle.py, and app.py
  silently swallow exceptions. Add Python `logging` module with
  structured output for production debugging.

- **Race condition in provisioning** — Two concurrent requests could
  both trigger VM provisioning for the same user. Low probability
  since BackgroundTasks run sequentially per-request, but could
  happen with concurrent browser tabs. Fix: check `vm_status`
  atomically before proceeding, or use a DB-level lock.

- **Topic length validation** — `POST /api/explore/start` accepts
  arbitrary-length topics. Add `max_length=500` to the Pydantic model.

- **File size limit on VM agent** — `GET /files/{path}` reads entire
  file into memory. Add a size check (e.g., max 1MB) before reading.

- **VM agent shutdown handler** — Add `@app.on_event("shutdown")` to
  terminate the exploration subprocess if it's running when the agent
  exits. Prevents orphaned processes.

- **Use shlex.split for EXPLORATION_CMD** — The VM agent uses
  `EXPLORATION_CMD.split()` which breaks on paths with spaces.
  Use `shlex.split()` instead.

- **Idle check null safety** — `idle.py` should skip VMs where
  `vm_zone` or `vm_id` is None before attempting suspend.

- **CORS production config** — Replace `allow_methods=["*"]` and
  `allow_headers=["*"]` with explicit lists in production.

- **Proxy error detail** — Include VM agent response body in 502
  errors so the frontend can show meaningful messages.

## Frontend

- **Error display in Controls** — Actions (start/stop/clear) silently
  catch errors. Show a toast or inline error message on failure.

- **Hardcoded API proxy URL** — `next.config.ts` proxies to
  `localhost:8000`. Make configurable via environment variable for
  production deployment.

- **Polling backoff** — Status polling runs every 5s indefinitely.
  Add exponential backoff when exploration is not running, or stop
  polling entirely when idle.

- **Session ID encoding** — URL-encode session IDs in
  `getSession(id)` to handle IDs with special characters.

- **Math/LaTeX rendering** — Add KaTeX or MathJax for rendering
  mathematical notation in session content and files.

- **Mobile responsive layout** — Current layout is desktop-only.
  Add responsive breakpoints for tablet/mobile.

- **Dark mode** — Add a theme toggle. Tailwind supports dark mode
  natively via `dark:` prefix classes.

- **User settings page** — Allow changing password, re-linking
  Claude/Wolfram tokens, viewing plan tier.

## Infrastructure

- **Email verification** — Send verification email on signup.
  Block exploration until verified.

- **Password reset** — Forgot-password flow with email link.

- **Rate limiting** — Add per-user rate limits on API endpoints
  to prevent abuse.

- **Admin panel** — Simple dashboard for viewing user count, VM
  status, and provisioning failures.

- **Automated base image CI/CD** — Currently rebuilt manually.
  Automate with Packer + Cloud Build on code push.

- **Multi-region support** — Currently us-central1 only. Add
  region selection based on user location.
