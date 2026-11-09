# Issue #003: Migrate JWT Storage to `HttpOnly` Cookies Under Custom Domain

- **Status**: Deferred (Phase 2)
- **Labels**: `security`, `auth`, `frontend`
- **Related Tech Debt**: `TD-004`

## Context
To support zero-cost cross-domain hosting between `vercel.app` and `onrender.com`, the demo client sends JWTs via the `Authorization: Bearer` header.

## Acceptance Criteria
1. Configure custom subdomain routing (`app.leadpulse.io` and `api.leadpulse.io`).
2. Issue `access_token` and `refresh_token` via `Set-Cookie` with `HttpOnly; Secure; SameSite=Lax`.
3. Add CSRF token validation on state-mutating (`POST`/`PUT`/`DELETE`) endpoints.
