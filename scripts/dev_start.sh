#!/usr/bin/env bash
# Start all services for local development.

set -e

echo "Starting Docker services..."
docker compose up -d postgres ollama n8n

echo "Waiting for Postgres to be healthy..."
until docker compose exec postgres pg_isready -U "${POSTGRES_USER:-jh}"; do
  sleep 1
done

echo "Starting backend (hot reload)..."
cd backend
source .venv/bin/activate 2>/dev/null || python -m venv .venv && source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

echo "Starting frontend (hot reload)..."
cd ../frontend
npm run dev &

echo ""
echo "Services running:"
echo "  Backend : http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo "  n8n     : http://localhost:5678"
echo ""
echo "Press Ctrl+C to stop."
wait
