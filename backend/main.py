from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import profile, jobs, score, cv, feedback, health

app = FastAPI(
    title="Job Hunter API",
    description="AI-powered job hunting agent system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(score.router, prefix="/score", tags=["scoring"])
app.include_router(cv.router, prefix="/cv", tags=["cv"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
