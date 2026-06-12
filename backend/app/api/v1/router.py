from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    applications,
    auth,
    cover_letters,
    cv_versions,
    health,
    jobs,
    opportunities,
    profiles,
    scores,
    sources,
    users,
)

router = APIRouter()

# Existing routers already carry prefix in their APIRouter() constructor
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(jobs.router)
router.include_router(scores.router)

# New Phase 6 routers — prefix defined here (no prefix inside the router file)
router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
router.include_router(applications.router, prefix="/applications", tags=["applications"])
router.include_router(cv_versions.router, prefix="/cv-versions", tags=["cv-versions"])
router.include_router(cover_letters.router, prefix="/cover-letters", tags=["cover-letters"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(sources.router, prefix="/sources", tags=["sources"])

# Opportunity Discovery Agent — prefix carried in router definition
router.include_router(opportunities.router)
