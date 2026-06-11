"""
Seed initial user + profile for Tanaz Piriaei.
Phase 2: run after `alembic upgrade head`.

Usage:
    docker compose exec backend python scripts/seed_profile.py
"""
# Phase 2: implement using SQLAlchemy session + User + Profile models

SEED_USER = {
    "email": "tanaz.p79@gmail.com",
    "name": "Tanaz Piriaei",
}

SEED_PROFILE = {
    "target_roles": [
        "AI Engineer",
        "LLM Engineer",
        "ML Engineer",
        "MLOps Engineer",
        "DevOps Engineer",
        "Research Engineer",
        "CIFRE PhD",
    ],
    "skills": [
        "Python", "FastAPI", "Docker", "LLM", "RAG",
        "C#", "Kubernetes", "Terraform", "CI/CD",
        "Scikit-learn", "PyTorch", "Ollama", "n8n",
    ],
    "cities": ["Lyon", "Paris"],
    "countries": ["France"],
    "remote_preference": True,
    "contract_types": ["cdi", "cdd", "alternance"],
    "languages": ["fr", "en", "fa"],
    "experience_level": "mid",
}

if __name__ == "__main__":
    print("Seed script — implement in Phase 2 after models are ready.")
    print("User:", SEED_USER["email"])
    print("Target roles:", SEED_PROFILE["target_roles"])
