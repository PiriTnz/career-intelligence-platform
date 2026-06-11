"""
One-shot seed: creates a user for Tanaz Piriaei and her AI/ML profile.

Run inside the backend container:
    docker compose exec backend python scripts/seed_profile.py

Or locally (with DATABASE_URL env set):
    python scripts/seed_profile.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.db.models import User, Profile


TANAZ = {
    "email": "tanaz.p79@gmail.com",
    "name": "Tanaz Piriaei",
    "password": "ChangeMe2024!",
}

PROFILE = {
    "target_roles": [
        "AI Engineer",
        "LLM Engineer",
        "ML Engineer",
        "MLOps Engineer",
        "DevOps Engineer",
        "Research Engineer",
        "CIFRE PhD",
    ],
    "avoid_roles": ["Data Entry", "Manual QA", "Support Engineer"],
    "skills": [
        "Python", "FastAPI", "Docker", "Kubernetes", "Terraform",
        "LLM", "RAG", "LangChain", "Ollama", "OpenAI API",
        "Scikit-learn", "PyTorch", "Hugging Face",
        "CI/CD", "GitHub Actions", "MLflow",
        "PostgreSQL", "Redis", "C#", ".NET",
        "Prometheus", "Grafana",
    ],
    "experience_level": "mid",
    "salary_min": 40000,
    "salary_target": 55000,
    "remote_preference": True,
    "countries": ["France"],
    "cities": ["Lyon", "Paris"],
    "contract_types": ["CDI", "CDD", "freelance", "alternance"],
    "languages": ["fr", "en", "fa"],
    "version": 1,
    "is_active": True,
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Check existing user
        existing = await db.execute(select(User).where(User.email == TANAZ["email"]))
        user = existing.scalar_one_or_none()

        if user is None:
            user = User(
                email=TANAZ["email"],
                name=TANAZ["name"],
                hashed_password=hash_password(TANAZ["password"]),
                is_active=True,
            )
            db.add(user)
            await db.flush()
            print(f"Created user: {user.email} (id={user.id})")
        else:
            print(f"User already exists: {user.email} (id={user.id})")

        # Check existing active profile
        existing_profile = await db.execute(
            select(Profile).where(
                Profile.user_id == user.id,
                Profile.is_active.is_(True),
            )
        )
        if existing_profile.scalar_one_or_none():
            print("Active profile already exists — skipping.")
        else:
            profile = Profile(user_id=user.id, **PROFILE)
            db.add(profile)
            await db.flush()
            print(f"Created profile v{profile.version} with {len(PROFILE['skills'])} skills")

        await db.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
