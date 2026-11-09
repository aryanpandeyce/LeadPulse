# Contributing to LeadPulse (`CONTRIBUTING.md` — Concept 10)

Welcome to the LeadPulse repository! This guide outlines our code organization, quality gates, and workflow conventions so every teammate can ship confidently.

---

## 1. Local Development Quickstart

```bash
# 1. Start PostgreSQL, Redis, Backend, and Frontend via Docker Compose
docker compose up --build -d

# 2. Run Alembic database migrations
make migrate

# 3. Seed 10,000 customers, 200,000 leads, and 500,000 activities
make seed
```

---

## 2. Architectural Guardrails (Must Follow in Every PR)

1. **Keep Route Handlers Thin**: Route handlers in `backend/app/api/routes/` must only declare Pydantic request/response models and delegate immediately to a service in `backend/app/services/`.
2. **Raise `AppError` Subclasses**: Never raise bare `HTTPException` in services or repositories. Raise `NotFoundError`, `ValidationError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `RateLimitError`, or `ExternalServiceError` from `app.core.errors`.
3. **Never Concatenate SQL Strings**: Always use parameterized SQLAlchemy 2.0 constructs and explicit column whitelists (`ALLOWED_SORT_COLUMNS`).
4. **Strict Typing (Zero `any`)**:
   - Backend functions must have complete Python type annotations (`mypy app` must pass with 0 errors).
   - Frontend TypeScript files must compile cleanly under `"strict": true, "noImplicitAny": true` with zero `any` types.
5. **Concept Discoverability**: When touching code related to one of the 10 core engineering concepts, preserve or add the `# CONCEPT: <name>` marker comment.

---

## 3. Running Quality Checks Before Opening a PR

```bash
# Backend lint, type-check, and unit/integration tests
cd backend
ruff check app tests
mypy app
pytest -v

# Frontend type-check and unit tests
cd ../frontend
npm run typecheck
npm run test -- --run
```

---

## 4. Commit Message Convention
We follow **Conventional Commits**:
- `feat(scope): short description`
- `fix(scope): short description`
- `docs(scope): short description`
- `test(scope): short description`
- `perf(scope): short description`

