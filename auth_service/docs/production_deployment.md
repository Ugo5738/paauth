# Production Deployment Guide

## Overview

This document outlines the steps required to deploy the Authentication Service to a production environment with a self-hosted Supabase instance.

## Architecture

The production deployment consists of:

1. **Authentication Service** - FastAPI application running in a Docker container
2. **PostgreSQL Database** - Managed by the self-hosted Supabase instance
3. **Self-hosted Supabase** - Providing authentication and database services

## Self-hosted Supabase Setup

### Prerequisites

- Docker and Docker Compose
- A server with at least 4GB RAM and 2 CPUs
- Domain name with SSL certificates (for production)

### Steps to Set Up Self-hosted Supabase

1. Clone the Supabase Docker repository:

```bash
git clone https://github.com/supabase/supabase-docker.git
cd supabase-docker
```

2. Configure environment variables in a `.env` file:

```bash
cp .env.example .env
```

3. Modify the `.env` file with your specific configuration:

```
# Supabase configuration
SUPABASE_DB_PASSWORD=your_secure_db_password
JWT_SECRET=your_secure_jwt_secret
ANON_KEY=your_anon_key  # Generated during setup
SERVICE_ROLE_KEY=your_service_role_key  # Generated during setup

# Domain configuration
DOMAIN_NAME=your_domain.com
EMAIL_ADDRESS=your_email@example.com  # For SSL certificate
```

4. Generate JWT keys and Supabase API keys:

```bash
cd scripts
./generate-keys.sh
```

5. Start the Supabase services:

```bash
cd ..
docker-compose up -d
```

6. Verify the installation by accessing the Supabase Studio at `https://your_domain.com/studio`

## Configuring Authentication Service for Self-hosted Supabase

### Environment Variables

Create a `.env.production` file in the root of the auth_service directory with the following variables:

```
# Self-hosted Supabase connection
SUPABASE_URL=https://your_domain.com
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Database connection (to the same Postgres database that Supabase uses)
AUTH_SERVICE_DATABASE_URL=postgresql+asyncpg://postgres:your_secure_db_password@db:5432/postgres

# JWT secrets
M2M_JWT_SECRET_KEY=your_secure_jwt_secret_for_m2m

# Admin user setup
INITIAL_ADMIN_EMAIL=admin@your_domain.com
INITIAL_ADMIN_PASSWORD=secure_admin_password

# API configuration
ROOT_PATH=/api/v1
ENVIRONMENT=production
LOGGING_LEVEL=INFO

# Rate limiting
RATE_LIMIT_LOGIN=20/minute
RATE_LIMIT_REGISTER=10/minute
RATE_LIMIT_TOKEN=30/minute
RATE_LIMIT_PASSWORD_RESET=5/minute
```

### Network Configuration

Ensure that the Authentication Service can reach the self-hosted Supabase services. If deploying with Docker Compose, add the Auth Service to the same network as Supabase:

```yaml
# In docker-compose.prod.yml
services:
  auth_service:
    # ... other configurations ...
    networks:
      - supabase_network

networks:
  supabase_network:
    external: true  # This network should be created by the Supabase Docker Compose setup
```

## Deployment Options

### Option 1: Using Docker Compose

1. Build and run the authentication service with the production Docker Compose file:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

2. Run database migrations:

```bash
docker-compose -f docker-compose.prod.yml exec auth_service alembic upgrade head
```

### Option 2: Using CI/CD Pipeline

The repository includes GitHub Actions workflows for continuous deployment:

1. Push to the main branch with a commit message containing `[deploy]` or manually trigger the workflow.
2. The workflow will build a Docker image, push it to the GitHub Container Registry, and deploy it to the specified environment.

## Database Migrations

Before deploying a new version, ensure all database migrations are applied:

```bash
docker-compose -f docker-compose.prod.yml exec auth_service alembic upgrade head
```

## Monitoring and Logging

### Health Check

The service provides a health check endpoint at `/health` that returns the status of:
- API service
- Database connection
- Supabase connection

### Structured Logging

In production, logs are output in JSON format with the following fields:
- `timestamp`: ISO 8601 formatted timestamp
- `level`: Log level (INFO, WARNING, ERROR, etc.)
- `logger`: Logger name
- `message`: Log message
- `request_id`: Unique ID for tracking requests across the system
- `environment`: Deployment environment
- Additional context-specific fields

### Log Collection

Since logs are output to stdout/stderr in Docker, you can use standard Docker log drivers or container orchestration platforms to collect and analyze logs.

## Backup and Recovery

### Database Backups

Regular backups of the PostgreSQL database should be configured. With self-hosted Supabase, this involves backing up the PostgreSQL database:

```bash
# Example backup command
docker-compose exec db pg_dump -U postgres postgres > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Procedure

1. Stop the services:

```bash
docker-compose down
```

2. Restore the database:

```bash
cat backup_file.sql | docker-compose exec -T db psql -U postgres
```

3. Restart the services:

```bash
docker-compose up -d
```

## Security Considerations

### JWT Management

- Ensure JWT secret keys are kept secure and rotated periodically
- Use environment variables or secrets management solutions to store sensitive values

### Network Security

- Use a reverse proxy (e.g., Nginx, Traefik) with SSL termination
- Implement proper firewall rules to restrict access to the services

### Rate Limiting

The service includes rate limiting for sensitive endpoints. Configure the limits based on your expected traffic patterns.

## Troubleshooting

### Common Issues

1. **Connection to Supabase fails:**
   - Verify network connectivity between containers
   - Check Supabase URL and API keys in environment variables
   - Ensure Supabase services are running

2. **Database migrations fail:**
   - Check database connection string
   - Verify database user permissions
   - Review Alembic migration logs

3. **Admin user creation fails during bootstrap:**
   - Check if the admin user already exists
   - Verify Supabase service role key permissions
   - Review service logs for detailed error messages
