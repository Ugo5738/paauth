# Auth Service

## Development

**Prerequisites**

- Docker & Docker Compose installed
- `.env` file configured with required variables

**Running the Application**

```bash
# from auth_service root
docker-compose up -d
```

**Viewing Logs**

```bash
docker-compose logs -f auth_service
```

**Stopping Services**

```bash
docker-compose down
```

## Inside the Container (Development Workflow)

- **Run tests**

  ```bash
docker-compose exec auth_service pytest
```

- **Apply migrations**

  ```bash
docker-compose exec auth_service alembic upgrade head
```

- **Open shell**

  ```bash
docker-compose exec auth_service bash
```

- **Manage dependencies**

  ```bash
docker-compose exec auth_service poetry add <package>
```

## IDE Integration (VS Code)

1. Install the **Docker** & **Remote Development** extensions.
2. Start containers (`docker-compose up -d`).
3. Open Command Palette → **Remote-Containers: Attach to Running Container...**
4. Select the `auth_service` container.
5. Use VS Code debugger & terminal inside the container.