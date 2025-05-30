# TODO List for Auth Service - For AI Agent (Cursor)

This TODO list breaks down the development of the Auth Service into manageable tasks, with testing integrated into each development step. The goal is an incremental build process with high test coverage.

## Phase 0: Project Setup & Core Configuration

- [x] **0.1: Initialize Python Project with Poetry**
  - [x] 0.1.a: Run `poetry new auth_service && cd auth_service`.
  - [x] 0.1.b: Initialize git repository (`git init && git add . && git commit -m "Initial project structure from poetry"`).
  - [x] **0.1.c: Create/Verify .gitignore File**
    - [x] 0.1.c.i: Ensure standard Python, Poetry, OS, and IDE specific files/directories are ignored (e.g., .env, **pycache**/, \*.pyc, .pytest_cache/, .mypy_cache/, .venv/, venv/, .vscode/, .idea/).
- [x] **0.2: Install Core Dependencies using Poetry**
  - [x] 0.2.a: Add `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings` (for env management), `sqlalchemy` (or `sqlmodel`), `asyncpg`, `psycopg2-binary` (for Alembic sync operations if needed, or Supabase direct connections), `python-jose[cryptography]` (for M2M JWTs), `passlib[bcrypt]` (for hashing client secrets), `supabase-py`, `alembic`, `slowapi`, `httpx` (for testing FastAPI).
  - [x] 0.2.b: Add development dependencies for testing, linting, and formatting: poetry add --group dev pytest pytest-asyncio pytest-cov black ruff mypy pre-commit httpx.
  - [x] 0.2.c: Configure Linters, Formatters, and Pre-commit Hooks
    - [x] 0.2.c.i: Configure pyproject.toml with settings for Black (e.g., line length) and Ruff (select rules, target Python version).
    - [x] 0.2.c.ii: Configure pyproject.toml for MyPy (e.g., strict mode options).
    - [x] 0.2.c.iii: Initialize pre-commit: pre-commit install
    - [x] 0.2.c.iv: Create a pre-commit-config.yaml file with hooks for Black, Ruff, and MyPy.
    - [x] 0.2.c.v: Test pre-commit hooks by trying to commit a non-compliant file.
  - [x] 0.2.d: Write initial GitHub Actions workflow for linting/testing on push/PR. (This provides early CI).
- [x] **0.3: Configure Environment Variable Management**
  - [x] 0.3.a: Create a `config.py` using `pydantic-settings` to load variables from a `.env` file.
    - [x] 0.3.a.i: Ensure `config.py` imports `BaseSettings` from `pydantic_settings` (not `pydantic` for Pydantic v2+).
    - [x] 0.3.a.ii: Define all environment variables present in `.env` (e.g., `RATE_LIMIT_...`, `INITIAL_ADMIN_...`, `LOGGING_LEVEL`) as fields in the `Settings` class in `config.py` to avoid `ValidationError` for extra fields.
  - [x] 0.3.b: Define initial required environment variables in `.env.example` and `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `M2M_JWT_SECRET_KEY`, `AUTH_SERVICE_DATABASE_URL`, `ROOT_PATH`.
    - [x] 0.3.b.i: For `AUTH_SERVICE_DATABASE_URL`, when using Supabase locally and Docker for `auth_service`:
      - The format should be `postgresql://<user>:<password>@<supabase_db_container_name>:<internal_port>/<db_name>`.
      - Example: `postgresql://postgres:postgres@supabase_db_projectname:5432/postgres`.
      - Find `<supabase_db_container_name>` (e.g., `supabase_db_projectname`) using `docker ps` after running `supabase start` in the project root (e.g., `projectname/`).
    - [x] 0.3.b.ii: Ensure `.env.example` lists all fields defined in the `Settings` class in `config.py`.
- [x] **0.4: Establish Asynchronous Database Connection (for Auth Service specific tables)**
  - [x] 0.4.a: Create database utility functions (`db.py`) for SQLAlchemy/SQLModel async engine setup, session management, and a base model.
  - [x] 0.4.b: Write a simple test to verify database connectivity, using the `AUTH_SERVICE_DATABASE_URL`, to the PostgreSQL instance where the `auth_service_data` schema will reside (this will typically be the Supabase-managed PostgreSQL instance). The test should run from within the `auth_service` container.
- [x] **0.5: Initialize Supabase Async Client**
  - [x] 0.5.a: Create a Supabase utility module (`supabase_client.py`) to initialize and provide the `supabase-py` AsyncClient as a FastAPI dependency.
  - [x] 0.5.b: Write a test to verify Supabase client initialization (can mock actual connection for this unit test).
- [x] **0.6: Define Core Pydantic Models**
  - [x] 0.6.a: Define initial Pydantic models in `auth_service/src/auth_service/schemas/common_schemas.py` (e.g., `MessageResponse`).
  - [x] 0.6.b: Define Pydantic models for JWT payloads in `auth_service/src/auth_service/schemas/user_schemas.py` (e.g., `UserTokenData`) and `auth_service/src/auth_service/schemas/app_client_schemas.py` (e.g., `AppClientTokenData`).
  - [x] 0.6.c: Organize Pydantic models into a dedicated `auth_service/src/auth_service/schemas/` directory with submodules (e.g., `user_schemas.py`, `app_client_schemas.py`, `common_schemas.py`) and an `__init__.py` for exports. Consolidate FastAPI dependencies into `auth_service/src/auth_service/dependencies/` (e.g., `user_deps.py`).
- [x] **0.7: Setup Alembic for Database Migrations (Auth Service Specific Schema)**
  - [x] 0.7.a: Initialize Alembic (`alembic init alembic`).
  - [x] 0.7.b: Configure `alembic/env.py` for asynchronous environment and to use `AUTH_SERVICE_DATABASE_URL`. Point `script.py.mako` to use the correct metadata object from `db.py`.
    - [x] 0.7.b.i: Ensure `alembic.ini` has `prepend_sys_path = .` to help resolve module paths when running alembic commands from the service root.
  - [x] 0.7.c: Specify the target schema (e.g., `auth_service_data`) in `env.py` if not using `public`.
- [x] **0.8: Basic FastAPI Application Structure**
  - [x] 0.8.a: Create `main.py` with a basic FastAPI app instance.
    - [x] 0.8.a.i: Ensure `FastAPI` instance in `main.py` is initialized with `root_path=settings.root_path` from your `config.py`.
  - [x] 0.8.b: Implement a health check endpoint (e.g., `GET /health`) and write a test for it.
- [x] **0.9: Logging and Error Handling Setup**
  - [x] 0.9.a: Configure basic structured logging (e.g., JSON format) for the application. Define key auditable events to be logged.
  - [x] 0.9.b: Implement custom exception handlers for common HTTP errors and validation errors to ensure consistent JSON error responses. Write tests for these handlers.
- [x] **0.10: CORS Configuration**
  - [x] 0.10.a: Add `CORSMiddleware` to the FastAPI app, configuring allowed origins, methods, and headers (initially permissive for local dev, configurable for prod).
- [x] **0.11: Create Initial Dockerfile for Development**
  - [x] 0.11.a: Create a basic Dockerfile that:
    - Uses an official Python base image (e.g., python:3.12-slim).
    - Sets appropriate environment variables (e.g., PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE).
    - Adds `ENV PYTHONPATH="${PYTHONPATH}:/app/src"` to ensure Python's import system can find modules in the `src` directory for `src`-layouts.
    - Sets up Poetry (installs it if not in base image, or ensures correct version).
    - Sets a WORKDIR (e.g., /app).
    - Copies `pyproject.toml` and `poetry.lock` first (to leverage Docker layer caching).
    - Installs dependencies using `poetry install --no-root --no-interaction --no-ansi` (and `poetry config virtualenvs.create false`). `--no-root` is important as the project source is copied separately.
    - Copies the entire application source code into the WORKDIR (`COPY . /app`).
    - EXPOSE the application port (e.g., 8000).
    - Specifies a CMD to run the FastAPI app with Uvicorn (enabling hot reloading e.g., `CMD ["poetry", "run", "uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`).
  - [x] 0.11.b: Build the Docker image using `docker build -t auth_service_dev .` (or via `docker-compose build`) and ensure it builds and runs successfully.
- [x] **0.12: Create Initial docker-compose.yml for Development**

  - [x] 0.12.a: Define a service for your auth_service using the Dockerfile.
  - [x] 0.12.b: Database Service for Local Development:

    - [x] 0.12.b.i: If using Supabase locally (via Supabase CLI `supabase start` or its own `docker-compose.yml`), ensure your `auth_service` container can connect to the PostgreSQL service provided by the local Supabase stack. The `AUTH_SERVICE_DATABASE_URL` will point to this Supabase PostgreSQL.
      - The `auth_service/docker-compose.yml` should **not** define its own `db` service for PostgreSQL.
        - Configure the `networks` section in `auth_service/docker-compose.yml` to connect to the external network created by the Supabase CLI.
          - Example:
            ```yaml
            networks:
              supabase_project_network: # Logical name for this service
                name: projectname_default_network # ACTUAL name of Supabase network
                external: true
            ```
          - Find the `ACTUAL name of Supabase network` (e.g., `projectname_default_network`) by running `docker network ls` after `supabase start` (run from project root, e.g., `projectname/`).

  - [x] 0.12.c: Configure volume mounts to map your local source code into the container for live reloading.
  - [x] 0.12.d: Set up port mappings.
  - [x] 0.12.e: Configure environment variables for the auth_service, ideally using `env_file: ./.env` in the `docker-compose.yml` for the service.

- [x] **0.13: Develop Inside the Container**
  - [x] 0.13.a: Document how to run the application using docker-compose up.
  - [x] 0.13.b: Document and establish the workflow for running all development commands (e.g., `pytest`, `alembic`, `poetry add/remove/update`) inside the service container using `docker-compose exec auth_service <command>` or an interactive shell via `docker-compose exec auth_service bash`.
  - [x] 0.13.c: Configure your IDE (e.g., VS Code with Docker extension) to work with the containerized environment (for debugging, terminal access).

## Phase 1: Database Schema & Models (Auth Service Specific Data)

- [x] **1.1: `profiles` Table (for user data extending Supabase users)**
  - [x] 1.1.a: Define SQLAlchemy/SQLModel model for `profiles` (`user_id` (PK, FK to `supabase.auth.users.id`), `username` (unique, nullable), `first_name` (nullable), `last_name` (nullable), `is_active` (default true), `created_at`, `updated_at`).
  - [x] 1.1.b: Generate Alembic migration script for `profiles` table.
  - [x] 1.1.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.2: `app_clients` Table (for M2M authentication)**
  - [x] 1.2.a: Define SQLAlchemy/SQLModel model for `app_clients` (`id` (PK, UUID), `client_name` (unique), `client_secret_hash`, `is_active` (default true), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.2.b: Generate Alembic migration script for `app_clients` table.
  - [x] 1.2.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.3: `roles` Table**
  - [x] 1.3.a: Define SQLAlchemy/SQLModel model for `roles` (`id` (PK, auto-increment or UUID), `name` (unique), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.3.b: Generate Alembic migration script for `roles` table.
  - [x] 1.3.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.4: `permissions` Table**
  - [x] 1.4.a: Define SQLAlchemy/SQLModel model for `permissions` (`id` (PK, auto-increment or UUID), `name` (unique, e.g., `resource:action`), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.4.b: Generate Alembic migration script for `permissions` table.
  - [x] 1.4.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.5: `user_roles` Junction Table**
  - [x] 1.5.a: Define SQLAlchemy/SQLModel model for `user_roles` (`user_id` (FK to `supabase.auth.users.id`), `role_id` (FK to `roles.id`), `assigned_at`; composite PK on `user_id`, `role_id`).
  - [x] 1.5.b: Generate Alembic migration script for `user_roles` table.
  - [x] 1.5.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.6: `app_client_roles` Junction Table**
  - [x] 1.6.a: Define SQLAlchemy/SQLModel model for `app_client_roles` (`app_client_id` (FK to `app_clients.id`), `role_id` (FK to `roles.id`), `assigned_at`; composite PK on `app_client_id`, `role_id`).
  - [x] 1.6.b: Generate Alembic migration script for `app_client_roles` table.
  - [x] 1.6.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.7: `role_permissions` Junction Table**
  - [x] 1.7.a: Define SQLAlchemy/SQLModel model for `role_permissions` (`role_id` (FK to `roles.id`), `permission_id` (FK to `permissions.id`), `assigned_at`; composite PK on `role_id`, `permission_id`).
  - [x] 1.7.b: Generate Alembic migration script for `role_permissions` table.
  - [x] 1.7.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.8: (Optional) `refresh_tokens` Table for `app_clients`**
  - [x] 1.8.a: If implementing: Define model, generate Alembic migration script, and apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.

## Phase 2: Human User Authentication (Proxying Supabase)

- [x] **2.1: User Registration (`POST /auth/users/register`)**
  - [x] 2.1.a: Define Pydantic models in `auth_service/src/auth_service/schemas/user_schemas.py`: `UserCreateRequest` (for request) and `UserResponse` (for response, including profile info), `SupabaseSession` (for session data).
  - [x] 2.1.b: Write unit tests for any pre/post Supabase call logic (e.g., profile data preparation). (Implicitly covered by successful integration tests for profile creation path)
  - [x] 2.1.c: Write integration tests for the endpoint:
    - [x] Successful registration and profile creation.
    - [x] Email already exists (Supabase error).
    - [x] Invalid password/email format.
    - [x] Supabase service unavailable (mocked).
  - [x] 2.1.d: Implement endpoint logic: call `supabase.auth.sign_up()`, then on success, create a local `profiles` entry. Handle Supabase errors.
  - [x] 2.1.e: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.2: User Login (Email/Password) (`POST /auth/users/login`)**
  - [x] 2.2.a: Define Pydantic models in `auth_service/src/auth_service/schemas/user_schemas.py`: `UserLoginRequest` (for request) and `SupabaseSession` (for response).
  - [x] 2.2.b: Write integration tests:
    - Successful login.
    - Invalid credentials.
    - User not found (Supabase might return generic invalid creds).
  - [x] 2.2.c: Implement endpoint logic: call supabase.auth.sign_in_with_password(). Handle Supabase errors and return session/user data.
  - [x] 2.2.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.3: User Login (Magic Link) (`POST /auth/users/login/magiclink`)**
  - [x] 2.3.a: Define Pydantic model `MagicLinkLoginRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.3.b: Write integration tests: successful request, invalid email.
  - [x] 2.3.c: Implement endpoint: call `supabase.auth.sign_in_with_otp()` (or equivalent for magic link).
  - [x] 2.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.4: User Logout (`POST /auth/users/logout`)**
  - [x] 2.4.a: Implement FastAPI dependency `get_current_supabase_user` in `auth_service/src/auth_service/dependencies/user_deps.py` to get current authenticated Supabase user from JWT.
  - [x] 2.4.b: Write integration tests: successful logout, invalid/expired token.
  - [x] 2.4.c: Implement endpoint: require Supabase JWT, call `supabase.auth.sign_out()`.
  - [x] 2.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.5: Password Reset Request (`POST /auth/users/password/reset`)**
  - [x] 2.5.a: Define Pydantic model `PasswordResetRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.5.b: Write integration tests: successful request, email not found, invalid email, Supabase API errors.
  - [x] 2.5.c: Implement the endpoint in `user_auth_routes.py`..
  - [x] 2.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.6: Password Update (`POST /auth/users/password/update`)**
  - [x] 2.6.a: Define Pydantic model `PasswordUpdateRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.6.b: Write integration tests: successful update, weak new password (if Supabase enforces), invalid current token.
  - [x] 2.6.c: Implement endpoint: require Supabase JWT, call `supabase.auth.update_user()` with new password.
  - [x] 2.6.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
    <!-- - [ ] **2.7: (If supporting) Social Logins (`GET /auth/users/login/{provider}`, `POST /auth/users/login/{provider}/callback`)** -->
      <!-- - [x] 2.7.a: Define Pydantic models for callback if needed. -->
      <!-- - [ ] 2.7.b: Write integration tests for initiation and callback (may require more complex mocking or test setup). -->
      <!-- - [ ] 2.7.c: Implement endpoints: call `supabase.auth.sign_in_with_oauth()`, handle callback. -->
      <!-- - [ ] 2.7.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'. -->
    <!-- - [ ] **2.8: (If supporting) MFA Proxy Endpoints** -->
      <!-- - [ ] 2.8.a: Research Supabase MFA flow (enroll, challenge, verify). Define Pydantic models. -->
      <!-- - [ ] 2.8.b: Write integration tests for each MFA step. -->
      <!-- - [ ] 2.8.c: Implement proxy endpoints to Supabase MFA functions. -->
      <!-- - [ ] 2.8.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'. -->

## Phase 3: User Profile Management (Auth Service Specific Data)

- [ ] **3.1: Get User Profile (`GET /auth/users/me`)**
  - [x] 3.1.a: Define Pydantic response model `ProfileResponse` in `auth_service/src/auth_service/schemas/user_schemas.py` (based on `profiles` table fields).
  - [x] 3.1.b: Write integration tests:
    - Successful retrieval for authenticated user.
    - User profile not found (edge case, should exist if registered via this service).
    - Unauthenticated access.
  - [x] 3.1.c: Implement endpoint: require Supabase JWT, extract `user_id`, fetch from local `profiles` table.
  - [x] 3.1.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **3.2: Update User Profile (`PUT /auth/users/me`)**
  - [x] 3.2.a: Define Pydantic request model `ProfileUpdate` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 3.2.b: Write integration tests: (Covered: successful full/partial updates, username conflict, unauthenticated access, basic Pydantic validation for request model)
    - Successful update.
    - Validation errors (e.g., invalid username format if rules apply).
    - Unauthenticated access.
  - [x] 3.2.c: Implement endpoint: require Supabase JWT, extract `user_id`, update local `profiles` table.
  - [x] 3.2.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 4: `app_client` (M2M) Authentication & Management

- [x] **4.1: Client Secret Hashing Utilities**
  - [x] 4.1.a: Implement helper functions (`security.py`) to hash secrets (`passlib.hash.bcrypt.hash`) and verify secrets (`passlib.hash.bcrypt.verify`).
  - [x] 4.1.b: Write unit tests for these helper functions.
- [x] **4.2: M2M JWT Generation & Decoding Utilities**
  - [x] 4.2.a: Implement `create_m2m_access_token` in `security.py` to generate JWTs with `sub` (client_id), `roles`, `permissions`, `exp`, `iss`, `aud` claims.
  - [x] 4.2.b: Implement `decode_m2m_access_token` in `security.py` to validate and decode these JWTs, checking signature, expiry, issuer, and audience.
  - [x] 4.2.c: Write unit tests for JWT creation and decoding (success, expiry, invalid signature, wrong issuer/audience).
  - [x] 4.2.d: Ensure M2M JWT settings (secret, algorithm, issuer, audience, expiry) are in `config.py` and loaded from `.env`.
- [x] **4.3: Define Admin Auth Dependency**
  - [x] 4.3.a: Create a FastAPI dependency that verifies if the current user (from Supabase JWT) has an 'admin' role (this role will be manually assigned initially or via a seeding script). This is a placeholder; full RBAC for admins comes later but basic protection is needed now.
  - [x] 4.3.b: Write unit tests for this dependency (mocking user roles).
- [x] **4.4: Create `app_client` (`POST /auth/admin/clients`) (Admin Protected)**
  - [x] 4.4.a: Define Pydantic models for request (`AppClientCreateRequest`) and response (`AppClientCreatedResponse` - including plain secret once).
  - [x] 4.4.b: Write integration tests:
    - Successful creation, secret is returned.
    - Duplicate client name.
    - Unauthorized access (not admin).
  - [x] 4.4.c: Implement endpoint: Use admin dependency. Generate `client_id` (UUID), generate secure `client_secret`, hash it, store hash. Return plain secret once.
  - [x] 4.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.5: List/Get `app_clients` (Admin Protected)**
  - [x] 4.5.a: Define Pydantic response models (`AppClientResponse` - no secret, `AppClientListResponse`).
  - [x] 4.5.b: Write integration tests for `GET /auth/admin/clients` and `GET /auth/admin/clients/{client_id}`:
    - Successful retrieval.
    - Client not found.
    - Unauthorized access.
  - [x] 4.5.c: Implement endpoints using admin dependency.
  - [x] 4.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.6: Update `app_client` (`PUT /auth/admin/clients/{client_id}`) (Admin Protected)**
  - [x] 4.6.a: Define Pydantic request model (`AppClientUpdateRequest`).
  - [x] 4.6.b: Write integration tests: successful update, client not found, unauthorized.
  - [x] 4.6.c: Implement endpoint using admin dependency.
  - [x] 4.6.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.7: Delete `app_client` (`DELETE /auth/admin/clients/{client_id}`) (Admin Protected)**
  - [x] 4.7.a: Write integration tests: successful deletion, client not found, unauthorized.
  - [x] 4.7.b: Implement endpoint using admin dependency.
  - [x] 4.7.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.8: `app_client` Token Acquisition (`POST /auth/token`)**
  - [x] 4.8.a: Define Pydantic request (`AppClientTokenRequest` - `grant_type`, `client_id`, `client_secret`) and response (`AccessTokenResponse`).
  - [x] 4.8.b: Write integration tests:
    - Successful token grant for active client with correct credentials.
    - Invalid `client_id` or `client_secret`.
    - Inactive client.
    - Missing parameters.
    - Incorrect `grant_type`.
    - Verify JWT claims (`sub`, `roles`, `permissions` - roles/perms will be empty initially).
  - [x] 4.8.c: Implement endpoint: Validate `grant_type=client_credentials`. Verify `client_id` and `client_secret` (using hashed secret). Fetch client's roles/permissions (will be empty for now). Generate M2M JWT.
  - [x] 4.8.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 5: RBAC Implementation & Admin Endpoints

Define `RoleCreate`, `RoleUpdate`, `RoleResponse`, `PermissionCreate`, `PermissionUpdate`, `PermissionResponse` Pydantic models.

- [x] **5.1: CRUD for `roles` (`/auth/admin/roles`) (Admin Protected)**
  - [x] 5.1.a: Write integration tests for `POST`, `GET` (list & single), `PUT`, `DELETE` for roles.
  - [x] 5.1.b: Implement CRUD endpoints for `roles` using admin dependency.
  - [x] 5.1.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.2: CRUD for `permissions` (`/auth/admin/permissions`) (Admin Protected)**
  - [x] 5.2.a: Write integration tests for `POST`, `GET` (list & single), `PUT`, `DELETE` for permissions.
  - [x] 5.2.b: Implement CRUD endpoints for `permissions` using admin dependency.
  - [x] 5.2.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [ ] **5.3: Assign/Remove Permissions from Roles (`/auth/admin/roles/{role_id}/permissions`) (Admin Protected)**
  - [ ] 5.3.a: Define Pydantic request for assigning permission ID.
  - [ ] 5.3.b: Write integration tests for `POST /auth/admin/roles/{role_id}/permissions/{permission_id}` (or with request body) and `DELETE /auth/admin/roles/{role_id}/permissions/{permission_id}`. Test for role/permission not found, already assigned/not assigned.
  - [ ] 5.3.c: Implement endpoints using admin dependency. Manage entries in `role_permissions` table.
  - [ ] 5.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [ ] **5.4: Assign/Remove Roles for Human Users (`/auth/admin/users/{user_id}/roles`) (Admin Protected)**
  - [ ] 5.4.a: Define Pydantic request for assigning role ID.
  - [ ] 5.4.b: Write integration tests for `POST /auth/admin/users/{user_id}/roles/{role_id}` and `DELETE /auth/admin/users/{user_id}/roles/{role_id}`. Test for user/role not found, already assigned/not assigned. (Note: `user_id` is Supabase `auth.users.id`).
  - [ ] 5.4.c: Implement endpoints using admin dependency. Manage entries in `user_roles` table.
  - [ ] 5.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [ ] **5.5: Assign/Remove Roles for `app_clients` (`/auth/admin/clients/{client_id}/roles`) (Admin Protected)**
  - [ ] 5.5.a: Define Pydantic request for assigning role ID.
  - [ ] 5.5.b: Write integration tests for `POST /auth/admin/clients/{client_id}/roles/{role_id}` and `DELETE /auth/admin/clients/{client_id}/roles/{role_id}`. Test for client/role not found, already assigned/not assigned.
  - [ ] 5.5.c: Implement endpoints using admin dependency. Manage entries in `app_client_roles` table.
  - [ ] 5.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [ ] **5.6: Refine Admin Auth Dependency**
  - [ ] 5.6.a: Update the admin auth dependency created in 4.3.a to check for specific admin roles/permissions (e.g., `role:admin_manage` permission) once RBAC is in place.
  - [ ] 5.6.b: Write/update unit tests for this refined dependency.

## Phase 6: JWT Customization & Claims

- [ ] **6.1: PostgreSQL Function for Supabase JWT Custom Claims `get_user_rbac_claims(user_id UUID)`**
  - [ ] 6.1.a: Design the SQL function to query `user_roles`, `role_permissions`, `roles`, `permissions` tables (in `auth_service_data` schema) to aggregate roles and permissions for a given `user_id`.
  - [ ] 6.1.b: Write the SQL function. It should return JSON like `{"roles": ["role_name_1"], "permissions": ["perm_slug_1"]}`.
  - [ ] 6.1.c: Test the SQL function directly in PostgreSQL with sample data.
- [ ] **6.2: Apply and Configure Supabase Custom Claims**
  - [ ] 6.2.a: Apply the `get_user_rbac_claims` function to the Supabase PostgreSQL database.
  - [ ] 6.2.b: Research and implement the Supabase configuration (e.g., Auth Hooks, `config.toml`, or triggers) to call this function and add its output to JWTs during user login/token refresh. Document this setup clearly.
  - [ ] 6.2.c: Manually test the human user login flow and inspect the Supabase JWT to ensure custom claims are present.
- [ ] **6.3: Update `app_client` Token Generation to Include RBAC Claims**
  - [ ] 6.3.a: Modify the `POST /auth/token` endpoint (Task 4.8.c) to fetch the `app_client`'s assigned roles and their associated permissions.
  - [ ] 6.3.b: Update the M2M JWT generation utility (Task 4.2.a) to include these roles and permissions in the `app_client` JWT.
  - [ ] 6.3.c: Update integration tests for `POST /auth/token` (Task 4.8.b) to verify the presence and correctness of roles and permissions claims in the M2M JWT.
  - [ ] 6.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 7: Security, Middleware & Final Touches

- [ ] **7.1: Rate Limiting Implementation (`slowapi`)**
  - [ ] 7.1.a: Apply `slowapi` rate limiting to sensitive endpoints (login, token, registration, password reset).
  - [ ] 7.1.b: Define sensible default limits (e.g., 5 requests per minute per IP) and ensure they are configurable via environment variables.
  - [ ] 7.1.c: Write tests to verify rate limiting is active and responds with 429 when limits are exceeded.
- [ ] **7.2: Final Security Review of Endpoints and Dependencies**
  - [ ] 7.2.a: Ensure all admin-only endpoints properly use the admin auth dependency.
  - [ ] 7.2.b: Ensure all user-authenticated endpoints properly validate the Supabase JWT.
  - [ ] 7.2.c: Review input validation (Pydantic models) for all endpoints.
- [ ] **7.3: Ensure HTTPS is Enforced (Deployment Concern)**
  - [ ] 7.3.a: Document that production deployment must be behind a reverse proxy (e.g., Nginx, Traefik) that handles TLS termination and enforces HTTPS.
  - [ ] 7.3.b: If using Uvicorn with `--ssl-keyfile` and `--ssl-certfile` for local HTTPS testing, document this.

## Phase 8: Documentation

- [ ] **8.1: Generate/Update OpenAPI Documentation**
  - [ ] 8.1.a: Ensure FastAPI's OpenAPI docs (`/docs`, `/redoc`) are comprehensive.
  - [ ] 8.1.b: Add detailed descriptions, examples for request/response bodies, and auth requirements to endpoint docstrings.
- [ ] **8.2: Document JWT Claims Structure**
  - [ ] 8.2.a: Create documentation (e.g., in `README.md` or a `docs/` folder) detailing the claims structure for human user (Supabase) JWTs and `app_client` (M2M) JWTs.
- [ ] **8.3: Document Supabase Custom Claims Setup**
  - [ ] 8.3.a: Document the SQL function and the Supabase configuration steps for custom claims.
- [ ] **8.4: Document Environment Variables**
  - [ ] 8.4.a: Ensure `.env.example` is complete and `README.md` lists all required environment variables and their purpose.
- [ ] **8.5: Document Admin Bootstrapping / Seeding**
  - [ ] 8.5.a: Document the process for creating the first admin user or assigning admin roles (developed in Phase 9).

## Phase 9: Deployment Preparation & Finalization

- [ ] **9.1: Create Dockerfile for the Auth Service**
  - [ ] 9.1.a: Write a multi-stage Dockerfile for a lean, secure production image, using Poetry to install dependencies.
  - [ ] 9.1.b: Test building the Docker image locally.
- [ ] **9.2: Create `docker-compose.yml` for Local Development/Testing**
  - [ ] 9.2.a: Include the auth service, a PostgreSQL instance (for `auth_service_data`), and potentially a local Supabase stack (if not using a hosted dev instance).
  - [ ] 9.2.b: Ensure environment variables are passed correctly.
- [ ] **9.3: Implement Initial Data Seeding (Admin User/Roles/Permissions)**
  - [ ] 9.3.a: Develop a strategy for initial data seeding (e.g., an Alembic data migration, a CLI command `docker-compose exec auth_service poetry run python -m auth_service.seed`). This should create default roles (e.g., 'admin', 'user'), core permissions, and allow bootstrapping an initial admin user (either by assigning a role to a pre-registered Supabase user or creating a special app client).
  - [ ] 9.3.b: Test the seeding process.
- [ ] **9.4: Configure Production Logging**
  - [ ] 9.4.a: Ensure logging levels and formats are configurable for production and capture necessary audit/debug info.
- [ ] **9.5: Production Secret Management Strategy**
  - [ ] 9.5.a: Document the strategy for managing production secrets (e.g., injected environment variables by PaaS/ orchestrator, Vault). Reiterate that `.env` files are not for production.
- [ ] **9.6: Comprehensive Test Suite Execution**
  - [ ] Run all unit and integration tests comprehensively using `docker-compose exec auth_service poetry run pytest --cov` and ensure high coverage.
- [ ] **9.7: Final Code Review and Cleanup**
      {{ ... }}
