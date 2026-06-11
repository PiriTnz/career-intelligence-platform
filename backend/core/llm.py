"""
LLM is used ONLY for:
- explaining a score in human language
- generating CV adaptations
- writing cover letters

It NEVER produces scores or makes ranking decisions.
"""
import httpx
import os
import json

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = "llama3"


async def explain_score(job: dict, profile: dict, breakdown, confidence: int) -> str:
    prompt = f"""You are a career advisor. Explain briefly why this job scored {breakdown.total}/100.

Job: {job.get('title')} at {job.get('company')} in {job.get('location')}
Contract: {job.get('contract_type')} | Remote: {job.get('remote')}
Skills required: {', '.join(job.get('required_skills', []))}

Score breakdown:
- Skill match: {breakdown.skill_match}/30
- Experience: {breakdown.experience_match}/20
- Location: {breakdown.location_score}/15
- Salary: {breakdown.salary_score}/15
- Contract: {breakdown.contract_score}/10
- Company: {breakdown.company_score}/5
- Freshness: {breakdown.freshness_score}/5

Extraction confidence: {confidence}%
{'Note: low extraction confidence — job description may be incomplete.' if confidence < 60 else ''}

Write 2-3 sentences max. Be direct and specific."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        return f"Explanation unavailable: {e}"


async def generate_cover_letter(
    job: dict,
    profile: dict,
    cv_text: str,
    doc_type: str = "cover_letter",
    language: str = "fr",
) -> str:
    type_instructions = {
        "cover_letter": "Write a professional cover letter (lettre de motivation).",
        "motivation": "Write a motivation letter focused on personal drive and fit.",
        "email_hr": "Write a short, direct email to HR (max 150 words).",
        "resume": "Write a short professional summary paragraph for a resume.",
    }
    instruction = type_instructions.get(doc_type, type_instructions["cover_letter"])
    lang_instruction = "Write in French." if language == "fr" else "Write in English."

    prompt = f"""{instruction} {lang_instruction}

Position: {job.get('title')} at {job.get('company')}
Location: {job.get('location')} | Contract: {job.get('contract_type')}
Required skills: {', '.join(job.get('required_skills', []))}
Job description excerpt: {(job.get('description') or '')[:800]}

Candidate profile:
- Skills: {', '.join(profile.get('skills', []))}
- Target roles: {', '.join(profile.get('target_roles', []))}
- Experience level: {profile.get('experience_level', 'junior')}

CV extract: {cv_text[:600]}

Be specific, avoid generic phrases. Highlight matching skills naturally."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        return f"Generation failed: {e}"
