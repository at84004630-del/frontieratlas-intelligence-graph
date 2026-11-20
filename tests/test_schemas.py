import pytest
from src.schemas import (
    StartupEntity,
    StartupContent,
    StartupData,
    ProductEntity,
    ProductContent,
    PricingModelEnum,
    ResearchPaperEntity,
    ResearchPaperContent,
    JobEntity,
    JobContent,
    NewsEntity,
    NewsContent,
    EntityMappingLog,
    SourceMeta,
)


def test_startup_entity_schema():
    entity = StartupEntity(
        schemaVersion="1.0",
        recordType="STARTUP",
        source=SourceMeta(name="Y Combinator", url="https://www.ycombinator.com/companies/openai"),
        content=StartupContent(
            entityName="OpenAI",
            description="Frontier AI research and deployment company",
            data=StartupData(employeeCount=1200, website="https://openai.com")
        )
    )
    flat = entity.to_flat_dict()
    assert flat["schemaVersion"] == "1.0"
    assert flat["recordType"] == "STARTUP"
    assert flat["content.entityName"] == "OpenAI"
    assert flat["content.data.employeeCount"] == 1200


def test_product_entity_schema():
    entity = ProductEntity(
        schemaVersion="1.0",
        recordType="PRODUCT",
        source=SourceMeta(name="Anthropic Web", url="https://claude.ai"),
        content=ProductContent(
            productName="Claude",
            startupName="Anthropic",
            pricingModel=PricingModelEnum.FREEMIUM,
            description="Next-generation AI assistant"
        )
    )
    flat = entity.to_flat_dict()
    assert flat["recordType"] == "PRODUCT"
    assert flat["content.startupName"] == "Anthropic"
    assert flat["content.pricingModel"] == "FREEMIUM"


def test_research_paper_entity_schema():
    entity = ResearchPaperEntity(
        schemaVersion="1.0",
        recordType="RESEARCH_PAPER",
        content=ResearchPaperContent(
            title="Attention Is All You Need",
            authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            paper_url="https://arxiv.org/abs/1706.03762",
            github_url="https://github.com/tensorflow/tensor2tensor",
            github_stars=12500,
            published_date="2017-06-12T00:00:00Z"
        )
    )
    flat = entity.to_flat_dict()
    assert flat["recordType"] == "RESEARCH_PAPER"
    assert flat["content.github_stars"] == 12500
    assert "Ashish Vaswani" in flat["content.authors"]


def test_job_entity_schema():
    entity = JobEntity(
        schemaVersion="1.0",
        recordType="JOB",
        content=JobContent(
            title="Senior Machine Learning Engineer",
            company="Mistral AI",
            date="2026-11-20T10:00:00Z",
            is_remote=True,
            role_family="Engineering",
            url="https://mistral.ai/careers"
        )
    )
    flat = entity.to_flat_dict()
    assert flat["recordType"] == "JOB"
    assert flat["content.company"] == "Mistral AI"
    assert flat["content.is_remote"] is True
    assert flat["content.role_family"] == "Engineering"


def test_news_entity_schema():
    entity = NewsEntity(
        schemaVersion="1.0",
        recordType="NEWS",
        source=SourceMeta(name="TechCrunch AI", url="https://techcrunch.com/article"),
        content=NewsContent(
            title="Frontier Foundation Models Reach New Reasoning Milestone",
            published_date="2026-11-20T14:30:00Z",
            author="Sarah Perez",
            summary="New architectures demonstrate enhanced symbolic synthesis.",
            full_text="Full article text content."
        )
    )
    flat = entity.to_flat_dict()
    assert flat["recordType"] == "NEWS"
    assert flat["source.name"] == "TechCrunch AI"


def test_entity_mapping_log_schema():
    log = EntityMappingLog(
        raw_name="OpenAI, Inc.",
        canonical_name="OpenAI",
        entity_type="STARTUP",
        resolution_method="EXACT_SEED",
        confidence_score=1.00
    )
    flat = log.to_flat_dict()
    assert flat["raw_name"] == "OpenAI, Inc."
    assert flat["canonical_name"] == "OpenAI"
    assert flat["confidence_score"] == 1.0
