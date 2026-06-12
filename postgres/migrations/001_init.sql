-- Job Hunter — initial schema
-- Run automatically on first postgres startup

CREATE SCHEMA IF NOT EXISTS n8n;

-- ── Users ──────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── User profiles ──────────────────────────────────────────────────────────
CREATE TABLE user_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version             INTEGER NOT NULL DEFAULT 1,
    target_roles        TEXT[]  NOT NULL DEFAULT '{}',
    avoid_roles         TEXT[]  NOT NULL DEFAULT '{}',
    skills              TEXT[]  NOT NULL DEFAULT '{}',
    salary_min          INTEGER,
    salary_target       INTEGER,
    remote_preference   BOOLEAN DEFAULT false,
    countries           TEXT[]  NOT NULL DEFAULT '{}',
    cities              TEXT[]  NOT NULL DEFAULT '{}',
    contract_types      TEXT[]  NOT NULL DEFAULT '{}',  -- alternance, cdi, cdd, stage
    languages           TEXT[]  NOT NULL DEFAULT ARRAY['fr','en'],
    raw_json            JSONB,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- ── Companies ──────────────────────────────────────────────────────────────
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    domain          TEXT,
    size            TEXT,   -- startup, sme, large, enterprise
    quality_score   SMALLINT DEFAULT 50,  -- 0-100, manually or auto updated
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(name)
);

-- ── Jobs (normalised schema) ────────────────────────────────────────────────
CREATE TABLE jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,   -- indeed, wttj, hellowork, ...
    source_id           TEXT,            -- original id from source
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    company_id          UUID REFERENCES companies(id),
    company_name        TEXT NOT NULL,
    location            TEXT,
    remote              TEXT,            -- none, hybrid, full
    contract_type       TEXT,            -- alternance, cdi, cdd, stage, freelance
    salary_min          INTEGER,
    salary_max          INTEGER,
    salary_currency     TEXT DEFAULT 'EUR',
    required_skills     TEXT[] DEFAULT '{}',
    experience_level    TEXT,            -- junior, mid, senior
    language            TEXT DEFAULT 'fr',
    description         TEXT,
    raw_json            JSONB,
    scraped_at          TIMESTAMPTZ DEFAULT now(),
    published_at        TIMESTAMPTZ,
    UNIQUE(url),
    UNIQUE(company_name, title, location)
);

CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_scraped_at ON jobs(scraped_at DESC);
CREATE INDEX idx_jobs_contract_type ON jobs(contract_type);

-- ── Scores ─────────────────────────────────────────────────────────────────
CREATE TABLE scores (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                  UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_version         INTEGER NOT NULL,
    -- breakdown
    skill_match             SMALLINT DEFAULT 0,   -- max 30
    experience_match        SMALLINT DEFAULT 0,   -- max 20
    location_score          SMALLINT DEFAULT 0,   -- max 15
    salary_score            SMALLINT DEFAULT 0,   -- max 15
    contract_score          SMALLINT DEFAULT 0,   -- max 10
    company_score           SMALLINT DEFAULT 0,   -- max 5
    freshness_score         SMALLINT DEFAULT 0,   -- max 5
    total                   SMALLINT GENERATED ALWAYS AS (
                                skill_match + experience_match + location_score +
                                salary_score + contract_score + company_score + freshness_score
                            ) STORED,
    -- confidence
    extraction_confidence   SMALLINT DEFAULT 100, -- 0-100, how well we parsed the job
    needs_review            BOOLEAN DEFAULT false,
    llm_explanation         TEXT,
    created_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE(job_id, user_id)
);

-- ── Applications ───────────────────────────────────────────────────────────
CREATE TABLE applications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'found',
    -- found → shortlisted → cv_generated → approved → applied
    -- → viewed → replied → interview / rejected / archived
    applied_at      TIMESTAMPTZ,
    approved_at     TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    interview_at    TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, job_id)
);

CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_user ON applications(user_id);

-- ── CV versions ────────────────────────────────────────────────────────────
CREATE TABLE cv_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id  UUID REFERENCES applications(id),
    job_id          UUID REFERENCES jobs(id),
    file_path       TEXT NOT NULL,
    language        TEXT DEFAULT 'fr',
    ats_score       SMALLINT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Cover letters ──────────────────────────────────────────────────────────
CREATE TABLE cover_letters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id  UUID REFERENCES applications(id),
    job_id          UUID REFERENCES jobs(id),
    type            TEXT DEFAULT 'cover_letter',  -- cover_letter, motivation, email_hr, resume
    language        TEXT DEFAULT 'fr',
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Feedback memory ────────────────────────────────────────────────────────
CREATE TABLE feedback_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal          TEXT NOT NULL,  -- rejected_job, liked_job, interview, salary_too_low
    job_id          UUID REFERENCES jobs(id),
    context         JSONB,          -- what the user said / pattern detected
    applied_rule    TEXT,           -- rule derived from this feedback
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Event logs ─────────────────────────────────────────────────────────────
CREATE TABLE event_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    agent       TEXT NOT NULL,   -- scraper, scorer, cv_builder, orchestrator
    action      TEXT NOT NULL,
    payload     JSONB,
    status      TEXT DEFAULT 'ok',  -- ok, error, retry
    error_msg   TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_event_logs_agent ON event_logs(agent);
CREATE INDEX idx_event_logs_created ON event_logs(created_at DESC);

-- ── Helper: auto-update updated_at ────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_applications_updated
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
