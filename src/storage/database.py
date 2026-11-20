"""
Multi-Model Storage Architecture Specification.
Defines production relational DDL (PostgreSQL + TimescaleDB), Vector Search (pgvector/Qdrant),
and Knowledge Graph Schemas (Neo4j Cypher) for FrontierAtlas Intelligence Graph.
"""

from typing import Dict, Any

# ==============================================================================
# 1. Relational & Time-Series Storage (PostgreSQL 16 + TimescaleDB)
# ==============================================================================
POSTGRESQL_DDL = """
-- 1. Enable UUID, pgvector, and pg_trgm extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Canonical Organizations (Startups & Companies)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(255) NOT NULL UNIQUE,
    primary_domain VARCHAR(255),
    employee_count INTEGER,
    batch VARCHAR(50),
    headquarters VARCHAR(255),
    description TEXT,
    embedding vector(1536), -- Ada-002 / text-embedding-3-small
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast trigram index for fuzzy string search
CREATE INDEX idx_orgs_name_trgm ON organizations USING gin (canonical_name gin_trgm_ops);
CREATE INDEX idx_orgs_domain ON organizations (primary_domain);

-- 3. Canonical Products
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    pricing_model VARCHAR(50) NOT NULL CHECK (pricing_model IN ('FREE', 'FREEMIUM', 'PAID', 'ENTERPRISE')),
    description TEXT,
    source_url TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_org_product UNIQUE (organization_id, product_name)
);

-- 4. Research Papers & Artifacts
CREATE TABLE IF NOT EXISTS research_papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    paper_url TEXT NOT NULL UNIQUE,
    authors TEXT[] NOT NULL,
    published_date TIMESTAMPTZ NOT NULL,
    github_url TEXT,
    github_stars INTEGER DEFAULT 0,
    embedding vector(1536),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_papers_published ON research_papers (published_date DESC);
CREATE INDEX idx_papers_stars ON research_papers (github_stars DESC);

-- 5. Time-Series Signals: Job Postings & News (TimescaleDB Hypertable)
CREATE TABLE IF NOT EXISTS job_postings (
    id UUID DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES organizations(id),
    title VARCHAR(255) NOT NULL,
    role_family VARCHAR(100) NOT NULL,
    is_remote BOOLEAN NOT NULL DEFAULT TRUE,
    url TEXT,
    published_date TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, published_date)
);

-- Convert to TimescaleDB hypertable partitioned by published_date
-- SELECT create_hypertable('job_postings', 'published_date', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS news_signals (
    id UUID DEFAULT uuid_generate_v4(),
    source_name VARCHAR(100) NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author VARCHAR(255),
    summary TEXT,
    published_date TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, published_date)
);

-- 6. Entity Resolution Audit Trail
CREATE TABLE IF NOT EXISTS entity_resolution_audit (
    id BIGSERIAL PRIMARY KEY,
    raw_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    resolution_method VARCHAR(50) NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# ==============================================================================
# 2. Neo4j Knowledge Graph Schema (Cypher Queries)
# ==============================================================================
NEO4J_SCHEMA_CYPHER = """
// 1. Constraints for Unique Entity Resolution
CREATE CONSTRAINT org_canonical IF NOT EXISTS FOR (o:Organization) REQUIRE o.canonical_name IS UNIQUE;
CREATE CONSTRAINT prod_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT paper_url IF NOT EXISTS FOR (r:ResearchPaper) REQUIRE r.paper_url IS UNIQUE;
CREATE CONSTRAINT repo_url IF NOT EXISTS FOR (g:GitHubRepo) REQUIRE g.url IS UNIQUE;

// 2. Core Graph Relationship Traversal Patterns
// (Organization)-[:PRODUCES]->(Product)
// (ResearchPaper)-[:USES_REPO]->(GitHubRepo)
// (JobPosting)-[:POSTED_BY]->(Organization)
// (NewsArticle)-[:MENTIONS]->(Organization)
// (NewsArticle)-[:MENTIONS]->(Product)

// Example Ingestion Upsert:
MERGE (o:Organization {canonical_name: $canonical_org})
ON CREATE SET o.domain = $domain, o.employee_count = $emp_count
MERGE (p:Product {name: $product_name, org_id: o.id})
ON CREATE SET p.pricing_model = $pricing_model
MERGE (o)-[:PRODUCES]->(p);

// Correlate Research Papers with GitHub Repositories
MERGE (r:ResearchPaper {paper_url: $paper_url})
ON CREATE SET r.title = $title, r.published_date = $published_date
WITH r
WHERE $github_url IS NOT NULL
MERGE (g:GitHubRepo {url: $github_url})
ON CREATE SET g.stars = $stars
MERGE (r)-[:USES_REPO]->(g);
"""
