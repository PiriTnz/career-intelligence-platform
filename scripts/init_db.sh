#!/usr/bin/env bash
# Initialize database: wait for Postgres, run Alembic migrations, seed profile.
# Phase 2: run inside Docker or locally.

set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-localhost}" -U "${POSTGRES_USER:-jh}"; do
  sleep 1
done

echo "Running Alembic migrations..."
cd backend && alembic upgrade head

echo "Seeding initial profile..."
python scripts/seed_profile.py

echo "Done."
