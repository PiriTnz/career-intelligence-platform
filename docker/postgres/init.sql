-- Initial PostgreSQL schema — run once on first container start.
-- Phase 2: Alembic will manage all migrations after this.
-- This file only creates the n8n schema so n8n can start alongside the app.

CREATE SCHEMA IF NOT EXISTS n8n;
