# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack FastAPI template application (fakturenn) with a Python backend (FastAPI, SQLModel, PostgreSQL) and a React TypeScript frontend (Vite, React Router, TanStack Query, Tailwind CSS, shadcn/ui).

The project is structured as two main applications:
- **Backend**: FastAPI REST API in `backend/`
- **Frontend**: React SPA in `frontend/`

Both run in Docker during development with live reload via `docker compose watch`.

## Commands Reference

### Backend Commands

```bash
# Install dependencies (from backend/ directory)
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run backend locally (requires uv and Python environment set up)
fastapi dev app/main.py

# Test backend
bash ./scripts/test.sh

# Test in running Docker container
docker compose exec backend bash scripts/tests-start.sh

# Pass arguments to pytest
docker compose exec backend bash scripts/tests-start.sh -x  # stop on first error

# Lint/format code
bash ./scripts/format.sh
bash ./scripts/lint.sh

# Database migrations (in running container)
docker compose exec backend bash
alembic revision --autogenerate -m "Add column X to model Y"
alembic upgrade head
```

### Frontend Commands

```bash
# Install dependencies (from frontend/ directory)
npm install

# Run frontend dev server locally
npm run dev

# Build frontend
npm build

# Lint and format code
npm run lint

# Generate client from backend OpenAPI schema
npm run generate-client

# Run Playwright end-to-end tests (requires backend running)
npx playwright test

# Run tests in UI mode
npx playwright test --ui
```

### Docker Compose

```bash
# Start full stack with live reload
docker compose watch

# Check logs
docker compose logs

# Check logs for specific service
docker compose logs backend
docker compose logs frontend

# Stop and remove all containers (keeps DB)
docker compose down

# Stop and remove everything including DB data
docker compose down -v

# Execute command in running container
docker compose exec backend bash
docker compose exec frontend bash

# Run tests in container without starting server
docker compose exec backend bash scripts/tests-start.sh
```

### Code Generation

```bash
# Generate frontend client from backend OpenAPI schema (run from root)
./scripts/generate-client.sh

# Manual generation (start Docker stack, then):
# 1. Download OpenAPI schema from http://localhost/api/v1/openapi.json
# 2. Save to frontend/openapi.json
# 3. From frontend/ run: npm run generate-client
```

### Code Quality

```bash
# Install prek (pre-commit hooks) - run from backend/
uv run prek install -f

# Run prek manually on all files
uv run prek run --all-files
```

## Architecture Overview

### Backend Architecture

**Entry Point**: `backend/app/main.py` creates the FastAPI app with:
- CORS middleware (configurable via `BACKEND_CORS_ORIGINS`)
- API router include with prefix `/api/v1`
- Optional Sentry error tracking
- OpenAPI schema generation

**Core Components** (`backend/app/core/`):
- `config.py`: Pydantic settings using `.env` file, handles all configuration
- `db.py`: SQLAlchemy engine and database initialization
- `security.py`: JWT token creation and password hashing utilities

**Data Layer**:
- `models.py`: SQLModel definitions (User, Item, and related schemas)
- `crud.py`: CRUD operations for database entities
- Alembic migrations: `app/alembic/` for schema management

**API Routes** (`backend/app/api/routes/`):
- `login.py`: JWT authentication endpoints
- `users.py`: User management endpoints
- `items.py`: Item management endpoints
- `utils.py`: Utility endpoints (health checks)
- `private.py`: Debug endpoints (local environment only)

**Database**:
- PostgreSQL connection via SQLModel ORM
- User and Item models with relationships
- UUID primary keys for all entities
- Cascade delete relationships configured

**Authentication**:
- JWT tokens with configurable expiry (default: 8 days)
- Password hashing with bcrypt
- Email validation with Pydantic validators

### Frontend Architecture

**Entry Point**: `frontend/src/main.tsx` mounts React app with TanStack Router

**Routing** (`frontend/src/routes/`):
- File-based routing via TanStack Router plugin
- Layout routes in `_layout/` (authenticated pages)
- Auth routes: `login.tsx`, `signup.tsx`, `recover-password.tsx`, `reset-password.tsx`
- Main layout in `_layout.tsx` with sidebar
- Protected routes: index (dashboard), admin, items, settings

**Components** (`frontend/src/components/`):
- `Admin/`: User management components
- `Items/`: Item CRUD components
- `Common/`: Shared components (layout, error boundary)
- `Sidebar/`: Navigation and user menu
- `UserSettings/`: Profile and account settings
- `ui/`: shadcn/ui component library (button, form, table, etc.)

**API Integration**:
- Auto-generated client in `src/client/` (from backend OpenAPI)
- `src/client/sdk.gen.ts`: Typed API client
- `src/client/schemas.gen.ts`: Type definitions
- Build happens via `npm run generate-client` after backend changes

**State Management**:
- TanStack Query: Server state management and caching
- React hooks: Local component state
- Context API: Global theme and auth state (see `useAuth.ts` hook)

**Styling**:
- Tailwind CSS 4.x with Vite integration
- shadcn/ui components (built with Radix UI)
- Dark mode via `next-themes` provider
- Responsive design patterns in components

**Testing**:
- Playwright E2E tests in `frontend/tests/`
- Test utilities: auth setup, user helpers, API utils
- MailCatcher integration for email testing

### Data Models

**User**:
- UUID primary key
- Email (unique, indexed)
- Hashed password
- Full name
- Active/superuser flags
- Relationship: `items` (one-to-many)

**Item**:
- UUID primary key
- Title and optional description
- Foreign key to User (owner_id)
- Cascade delete with owner
- Relationship: `owner` (many-to-one)

### Database & Migrations

- PostgreSQL database via Docker
- Alembic for schema versioning
- Migration files in `backend/app/alembic/versions/`
- Auto-generate migrations: `alembic revision --autogenerate -m "description"`
- Apply migrations: `alembic upgrade head`

## Development Workflow

### Local Setup

1. **Backend**:
   - Go to `backend/` directory
   - Run `uv sync` to install dependencies
   - Activate venv: `source .venv/bin/activate`
   - Run `docker compose watch` from root

2. **Frontend** (optional, if developing locally):
   - Go to `frontend/` directory
   - Run `fnm use` or `nvm use` (installs Node version from `.nvmrc`)
   - Run `npm install`
   - Run `npm run dev` (separate terminal)

### Docker Development

- `docker compose watch`: Starts all services with live reload
- Backend code mounted as volume, auto-reloads on changes
- Frontend served from Docker with live reload via Vite
- Database persists across restarts (unless using `docker compose down -v`)

### Database Changes

1. Modify `backend/app/models.py`
2. In running container: `docker compose exec backend bash`
3. Create migration: `alembic revision --autogenerate -m "description"`
4. Apply migration: `alembic upgrade head`
5. Commit migration files to git

### Testing

**Backend Tests**:
- Pytest in `backend/tests/`
- Test structure mirrors app structure
- Conftest handles fixtures and database setup
- Run: `bash ./scripts/test.sh` or `docker compose exec backend bash scripts/tests-start.sh`

**Frontend Tests**:
- Playwright in `frontend/tests/`
- Requires backend running
- Test setup includes auth handling via `auth.setup.ts`
- Run: `npx playwright test` or `npx playwright test --ui`

### API Client Generation

When backend endpoints change:
1. Update `backend/app/models.py` or routes
2. From root: `./scripts/generate-client.sh` (auto mode)
3. Or manually download OpenAPI schema and run `npm run generate-client` in frontend
4. Commit generated files: `src/client/*.ts`

## Important Files & Patterns

### Backend Patterns

**Settings/Config**:
- All config centralized in `backend/app/core/config.py`
- Uses Pydantic v2 with `BaseSettings`
- Reads from `.env` file (one level above backend/)
- Environment-aware secrets validation

**API Response Pattern**:
```python
# Models define request/response schemas
class ItemCreate(ItemBase): pass
class ItemPublic(ItemBase): id: UUID

# Routes use dependency injection for DB session
from app.api.deps import SessionDep
@router.post("/items/", response_model=ItemPublic)
def create_item(item_in: ItemCreate, session: SessionDep) -> ItemPublic:
    return crud.create_item(session=session, item_in=item_in)
```

**CRUD Pattern**:
- All database operations in `backend/app/crud.py`
- Takes session and model as parameters
- Returns SQLModel instances

**Error Handling**:
- FastAPI raises HTTPException for errors
- Email templates in `backend/app/email-templates/` (MJML source → HTML build)

### Frontend Patterns

**Route Structure**:
- TanStack Router file-based routing
- Layout routes: `_layout/` pages get sidebar + nav
- Auth pages: outside `_layout/`, no protection
- Generated `src/routeTree.gen.ts` (do not edit, auto-generated)

**Component Pattern**:
```tsx
// Use generated client for API calls
import { useMutation, useQuery } from '@tanstack/react-query'
import { useClient } from '@/hooks/useAuth'  // or similar

// Query for fetching
const { data, isLoading } = useQuery({
  queryKey: ['items'],
  queryFn: () => client.items.listItems(),
})

// Mutation for creating/updating
const mutation = useMutation({
  mutationFn: (data) => client.items.createItem({ requestBody: data }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] })
})
```

**Form Pattern** (React Hook Form + Zod):
- Define schema with Zod
- Use `useForm()` hook from react-hook-form
- shadcn/ui Form component for consistent styling
- Validation happens on change and submit

## Environment Configuration

### .env File
Located at repository root, shared by both backend and frontend:

**Database**:
- `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

**Backend**:
- `PROJECT_NAME`: Display name in API docs
- `SECRET_KEY`: JWT signing key (change for production!)
- `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`: Initial admin account
- `BACKEND_CORS_ORIGINS`: Comma-separated list of allowed origins
- `SMTP_*`: Email sending configuration
- `SENTRY_DSN`: Error tracking (optional)
- `ENVIRONMENT`: `local`, `staging`, or `production`

**Frontend**:
- `VITE_API_URL`: Backend URL (defaults to same origin)

## Code Quality

- **Linting/Formatting**: 
  - Backend: Ruff (linter/formatter) + Mypy (type checker)
  - Frontend: Biome (linter/formatter)
  - Pre-commit hooks via Prek (modern alternative to Pre-commit)
  
- **Type Checking**:
  - Backend: Strict mypy enforced
  - Frontend: TypeScript strict mode
  
- **Testing**:
  - Backend: Pytest with coverage tracking
  - Frontend: Playwright E2E tests

## Deployment

- Docker images for both backend and frontend
- Traefik reverse proxy for routing and HTTPS
- GitHub Actions workflows for CI/CD
- Staging and production environments
- See `deployment.md` for full deployment instructions

## Common Tasks

**Add a new API endpoint**:
1. Add route to `backend/app/api/routes/`
2. Use existing models or create new ones in `models.py`
3. Use `SessionDep` for database access
4. Run tests and regenerate client: `./scripts/generate-client.sh`
5. Create frontend components to consume endpoint

**Add a new database model**:
1. Add to `backend/app/models.py`
2. Create CRUD functions in `backend/app/crud.py`
3. Create route in `backend/app/api/routes/`
4. Run: `docker compose exec backend alembic revision --autogenerate -m "Add X model"`
5. Apply migration: `docker compose exec backend alembic upgrade head`
6. Regenerate client: `./scripts/generate-client.sh`

**Add a new page**:
1. Create route file in `frontend/src/routes/` (TanStack Router convention)
2. Create component in `frontend/src/components/`
3. Use generated client and TanStack Query for data
4. Add navigation link in `frontend/src/components/Sidebar/AppSidebar.tsx`

**Debug backend locally**:
1. Stop Docker frontend: `docker compose stop frontend`
2. From `backend/`: `fastapi dev app/main.py`
3. Or use VS Code debugger (config exists in `.vscode/launch.json`)

**Debug database**:
- Adminer available at `http://localhost:8080`
- Default credentials from `.env` file

**Test email functionality**:
- MailCatcher UI at `http://localhost:1080`
- Captures all outgoing emails in development
- Configured via SMTP settings in `config.py`

## Project-Specific Notes

- Using `uv` for Python package management (faster than pip/venv)
- Email templates use MJML format (in `backend/app/email-templates/src/`)
- OpenAPI/Swagger docs auto-generated from FastAPI routes
- Frontend client auto-generated from OpenAPI schema
- Both environments can run separately or together via Docker Compose
