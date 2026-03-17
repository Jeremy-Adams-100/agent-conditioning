# Stage 6: Polish & Hardening

## Scope

Four items, in priority order:

### 1. Cloudflare Turnstile CAPTCHA on Signup
- Add Turnstile widget to signup page (one `<script>` tag + component)
- Verify token server-side in `/api/auth/signup` (one HTTP call)
- Env vars: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`
- Free tier, no cost

### 2. Email Verification
- On signup, set `email_verified = false` in users table
- Send verification email with signed token link
- `/api/auth/verify?token=...` endpoint marks email verified
- Block exploration (not login) until verified
- Env vars: SMTP config (host, port, user, password)
- For MVP: use a simple SMTP relay (Gmail app password or Resend.com free tier)

### 3. Mobile Responsive Layout
- Landing/auth/onboard pages: minor padding tweaks
- Explorer page: stacked layout on mobile
  - Full-width content viewer
  - Bottom tab bar (Sessions / Files / Controls)
  - Status bar condensed
- ~50 lines of Tailwind class changes, no new components

### 4. Logging
- Add Python `logging` module to backend
- Log: provisioning events, tier detection, idle suspension, errors
- Structured JSON output for production (easy to parse)
- Replace silent `except: pass` with `logger.exception()`
