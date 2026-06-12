"""
API tests for Interview Optimization Workspace endpoints.

POST /api/v1/interview/prepare/{job_id}
GET  /api/v1/interview/workspace/{job_id}
POST /api/v1/interview/confirm-evidence
POST /api/v1/interview/reject-evidence
GET  /api/v1/interview/knowledge-base
GET  /api/v1/interview/application-pipeline
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

JOB_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PENDING_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
EV_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


# ── Mock workspace ────────────────────────────────────────────────────────────

def _make_workspace(job_id=JOB_ID, label="strong", score=68):
    ws = MagicMock()
    ws.id = uuid.uuid4()
    ws.job_id = job_id
    ws.verified_matches = ["python", "docker"]
    ws.transferable_matches = [{"skill": "tensorflow", "via": "pytorch", "family": "ml_frameworks", "rationale": "Adjacent"}]
    ws.learning_skills = ["azure"]
    ws.real_gaps = ["kubernetes"]
    ws.recruiter_concerns = [{"skill": "kubernetes", "concern": "Missing"}]
    ws.mitigation_strategies = [{"skill": "kubernetes", "strategy": "Highlight docker"}]
    ws.cv_draft = "# CV Draft"
    ws.cover_letter_draft = "Dear HM"
    ws.readiness_label = label
    ws.readiness_score = score
    ws.readiness_explanation = "You match 2/4 required skills."
    ws.warnings = ["Moderate gap: 1 missing skill."]
    return ws


def _make_skill_evidence(skill="azure", status="learning"):
    ev = MagicMock()
    ev.id = EV_ID
    ev.skill = skill
    ev.status = status
    ev.source = "user_confirmed"
    ev.confidence = 0.95
    ev.evidence_notes = None
    from datetime import datetime, timezone
    ev.created_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
    ev.updated_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
    return ev


def _make_pending(skill="kubernetes"):
    p = MagicMock()
    p.id = PENDING_ID
    p.skill = skill
    p.suggested_status = "learning"
    p.agent_question = f"Have you used {skill}?"
    p.agent_reasoning = "Relevant to the role"
    p.source_context = "ML Engineer at AIStartup"
    from datetime import datetime, timezone
    p.created_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
    return p


# ── TestPrepareWorkspaceEndpoint ──────────────────────────────────────────────

class TestPrepareWorkspaceEndpoint:
    def test_returns_200_on_success(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        data = resp.json()
        for field in ["job_id", "verified_matches", "transferable_matches", "learning_skills",
                      "real_gaps", "recruiter_concerns", "mitigation_strategies",
                      "cv_draft", "cover_letter_draft", "readiness", "warnings"]:
            assert field in data, f"Missing field: {field}"

    def test_readiness_has_label_score_explanation(self, client: TestClient):
        ws = _make_workspace(label="strong", score=68)
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        readiness = resp.json()["readiness"]
        assert readiness["label"] == "strong"
        assert readiness["score"] == 68
        assert "explanation" in readiness

    def test_transferable_matches_have_skill_via_family(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        tm = resp.json()["transferable_matches"]
        assert len(tm) == 1
        assert tm[0]["skill"] == "tensorflow"
        assert tm[0]["via"] == "pytorch"
        assert "family" in tm[0]

    def test_404_when_job_not_found(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, side_effect=ValueError(f"Job {JOB_ID} not found.")), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert resp.status_code == 404

    def test_400_when_no_profile(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, side_effect=ValueError("No active profile found.")), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert resp.status_code == 400

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert resp.status_code == 401

    def test_learning_skills_in_response(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert resp.json()["learning_skills"] == ["azure"]

    def test_real_gaps_in_response(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        assert "kubernetes" in resp.json()["real_gaps"]

    def test_recruiter_concerns_structure(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        concerns = resp.json()["recruiter_concerns"]
        assert len(concerns) == 1
        assert "skill" in concerns[0]
        assert "concern" in concerns[0]

    def test_mitigation_strategies_structure(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.prepare_workspace",
                   new_callable=AsyncMock, return_value=ws), \
             patch("app.api.v1.endpoints.interview.get_provider"):
            resp = client.post(f"/api/v1/interview/prepare/{JOB_ID}")
        strategies = resp.json()["mitigation_strategies"]
        assert len(strategies) == 1
        assert "strategy" in strategies[0]


# ── TestGetWorkspaceEndpoint ──────────────────────────────────────────────────

class TestGetWorkspaceEndpoint:
    def test_returns_200_when_exists(self, client: TestClient):
        ws = _make_workspace()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_workspace",
                   new_callable=AsyncMock, return_value=ws):
            resp = client.get(f"/api/v1/interview/workspace/{JOB_ID}")
        assert resp.status_code == 200

    def test_404_when_not_found(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_workspace",
                   new_callable=AsyncMock, return_value=None):
            resp = client.get(f"/api/v1/interview/workspace/{JOB_ID}")
        assert resp.status_code == 404
        assert "prepare" in resp.json()["detail"].lower()

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.get(f"/api/v1/interview/workspace/{JOB_ID}")
        assert resp.status_code == 401

    def test_returns_same_schema_as_prepare(self, client: TestClient):
        ws = _make_workspace(label="excellent", score=88)
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_workspace",
                   new_callable=AsyncMock, return_value=ws):
            resp = client.get(f"/api/v1/interview/workspace/{JOB_ID}")
        data = resp.json()
        assert data["readiness"]["label"] == "excellent"
        assert data["readiness"]["score"] == 88


# ── TestConfirmEvidenceEndpoint ───────────────────────────────────────────────

class TestConfirmEvidenceEndpoint:
    def test_returns_200_on_success(self, client: TestClient):
        ev = _make_skill_evidence()
        with patch("app.api.v1.endpoints.interview.career_interview_service.confirm_evidence",
                   new_callable=AsyncMock, return_value=ev):
            resp = client.post("/api/v1/interview/confirm-evidence",
                               json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 200

    def test_response_has_skill_and_status(self, client: TestClient):
        ev = _make_skill_evidence(skill="azure", status="learning")
        with patch("app.api.v1.endpoints.interview.career_interview_service.confirm_evidence",
                   new_callable=AsyncMock, return_value=ev):
            resp = client.post("/api/v1/interview/confirm-evidence",
                               json={"pending_id": str(PENDING_ID)})
        data = resp.json()
        assert data["skill"] == "azure"
        assert data["status"] == "learning"

    def test_404_when_pending_not_found(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.career_interview_service.confirm_evidence",
                   new_callable=AsyncMock, return_value=None):
            resp = client.post("/api/v1/interview/confirm-evidence",
                               json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 404

    def test_override_status_accepted(self, client: TestClient):
        ev = _make_skill_evidence(status="verified")
        with patch("app.api.v1.endpoints.interview.career_interview_service.confirm_evidence",
                   new_callable=AsyncMock, return_value=ev):
            resp = client.post("/api/v1/interview/confirm-evidence",
                               json={"pending_id": str(PENDING_ID), "override_status": "verified"})
        assert resp.status_code == 200

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.post("/api/v1/interview/confirm-evidence",
                                json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 401


# ── TestRejectEvidenceEndpoint ────────────────────────────────────────────────

class TestRejectEvidenceEndpoint:
    def test_returns_204_on_success(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.career_interview_service.reject_evidence",
                   new_callable=AsyncMock, return_value=True):
            resp = client.post("/api/v1/interview/reject-evidence",
                               json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 204

    def test_404_when_not_found(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.career_interview_service.reject_evidence",
                   new_callable=AsyncMock, return_value=False):
            resp = client.post("/api/v1/interview/reject-evidence",
                               json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 404

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.post("/api/v1/interview/reject-evidence",
                                json={"pending_id": str(PENDING_ID)})
        assert resp.status_code == 401


# ── TestKnowledgeBaseEndpoint ─────────────────────────────────────────────────

class TestKnowledgeBaseEndpoint:
    def _mock_kb_and_pending(self):
        verified = [_make_skill_evidence("python", "verified"), _make_skill_evidence("docker", "verified")]
        transferable = [_make_skill_evidence("machine learning", "transferable")]
        learning = [_make_skill_evidence("azure", "learning")]
        all_kb = verified + transferable + learning
        pending = [_make_pending("kubernetes")]
        return all_kb, pending

    def test_returns_200(self, client: TestClient):
        kb, pending = self._mock_kb_and_pending()
        with patch("app.api.v1.endpoints.interview.career_interview_service.get_knowledge_base",
                   new_callable=AsyncMock, return_value=kb), \
             patch("app.api.v1.endpoints.interview.career_interview_service.get_pending_evidence",
                   new_callable=AsyncMock, return_value=pending):
            resp = client.get("/api/v1/interview/knowledge-base")
        assert resp.status_code == 200

    def test_response_grouped_by_status(self, client: TestClient):
        kb, pending = self._mock_kb_and_pending()
        with patch("app.api.v1.endpoints.interview.career_interview_service.get_knowledge_base",
                   new_callable=AsyncMock, return_value=kb), \
             patch("app.api.v1.endpoints.interview.career_interview_service.get_pending_evidence",
                   new_callable=AsyncMock, return_value=pending):
            resp = client.get("/api/v1/interview/knowledge-base")
        data = resp.json()
        assert "verified" in data
        assert "transferable" in data
        assert "learning" in data
        assert "pending" in data
        assert "total_skills" in data

    def test_total_skills_count(self, client: TestClient):
        kb, pending = self._mock_kb_and_pending()
        with patch("app.api.v1.endpoints.interview.career_interview_service.get_knowledge_base",
                   new_callable=AsyncMock, return_value=kb), \
             patch("app.api.v1.endpoints.interview.career_interview_service.get_pending_evidence",
                   new_callable=AsyncMock, return_value=pending):
            resp = client.get("/api/v1/interview/knowledge-base")
        assert resp.json()["total_skills"] == 4  # 2 verified + 1 transferable + 1 learning

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.get("/api/v1/interview/knowledge-base")
        assert resp.status_code == 401

    def test_empty_kb_returns_valid_response(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.career_interview_service.get_knowledge_base",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.api.v1.endpoints.interview.career_interview_service.get_pending_evidence",
                   new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/v1/interview/knowledge-base")
        data = resp.json()
        assert data["total_skills"] == 0
        assert data["verified"] == []
        assert data["pending"] == []


# ── TestApplicationPipelineEndpoint ──────────────────────────────────────────

class TestApplicationPipelineEndpoint:
    def _make_pipeline_items(self):
        return [
            {
                "job_id": str(JOB_ID),
                "job_title": "ML Engineer",
                "company_name": "AIStartup",
                "stage": "ready_to_apply",
                "readiness_label": "strong",
                "readiness_score": 72,
                "has_workspace": True,
                "has_application": True,
                "application_id": str(uuid.uuid4()),
                "application_status": "cv_generated",
            },
            {
                "job_id": str(uuid.uuid4()),
                "job_title": "Backend Engineer",
                "company_name": "TechCo",
                "stage": "recommended",
                "readiness_label": "moderate",
                "readiness_score": 55,
                "has_workspace": True,
                "has_application": False,
                "application_id": None,
                "application_status": None,
            },
        ]

    def test_returns_200(self, client: TestClient):
        items = self._make_pipeline_items()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_application_pipeline",
                   new_callable=AsyncMock, return_value=items):
            resp = client.get("/api/v1/interview/application-pipeline")
        assert resp.status_code == 200

    def test_returns_list_of_pipeline_items(self, client: TestClient):
        items = self._make_pipeline_items()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_application_pipeline",
                   new_callable=AsyncMock, return_value=items):
            resp = client.get("/api/v1/interview/application-pipeline")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_pipeline_item_fields(self, client: TestClient):
        items = self._make_pipeline_items()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_application_pipeline",
                   new_callable=AsyncMock, return_value=items):
            resp = client.get("/api/v1/interview/application-pipeline")
        item = resp.json()[0]
        for field in ["job_id", "job_title", "company_name", "stage",
                      "readiness_label", "readiness_score",
                      "has_workspace", "has_application"]:
            assert field in item

    def test_empty_pipeline_returns_empty_list(self, client: TestClient):
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_application_pipeline",
                   new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/v1/interview/application-pipeline")
        assert resp.json() == []

    def test_401_unauthenticated(self, anon_client: TestClient):
        resp = anon_client.get("/api/v1/interview/application-pipeline")
        assert resp.status_code == 401

    def test_stage_values_are_valid(self, client: TestClient):
        valid_stages = {
            "recommended", "ready_to_apply", "applied",
            "follow_up", "interview", "rejected", "offer",
        }
        items = self._make_pipeline_items()
        with patch("app.api.v1.endpoints.interview.interview_optimization_service.get_application_pipeline",
                   new_callable=AsyncMock, return_value=items):
            resp = client.get("/api/v1/interview/application-pipeline")
        for item in resp.json():
            assert item["stage"] in valid_stages, f"Invalid stage: {item['stage']}"
