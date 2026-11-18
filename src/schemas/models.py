"""
Data schemas and validation models for data intelligence pipelines.
"""

from datetime import datetime, timezone
from enum import Enum
import json
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class PricingModelEnum(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class SourceMeta(BaseModel):
    name: str = Field(..., description="Source directory or platform name")
    url: str = Field(..., description="Canonical source URL")


# --- Startup Entity ---

class StartupData(BaseModel):
    employeeCount: Optional[int] = Field(None, description="Reported team or employee size")
    location: Optional[str] = Field(None, description="Headquarters location")
    batch: Optional[str] = Field(None, description="Accelerator cohort if applicable")
    website: Optional[str] = Field(None, description="Company homepage URL")


class StartupContent(BaseModel):
    entityName: str = Field(..., description="Canonical company name")
    description: Optional[str] = Field(None, description="Company overview")
    data: StartupData = Field(default_factory=StartupData)


class StartupEntity(BaseModel):
    schemaVersion: str = Field(default="1.0")
    recordType: Literal["STARTUP"] = Field(default="STARTUP")
    source: SourceMeta
    content: StartupContent
    collectedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "recordType": self.recordType,
            "source.name": self.source.name,
            "source.url": self.source.url,
            "content.entityName": self.content.entityName,
            "content.data.employeeCount": self.content.data.employeeCount if self.content.data.employeeCount is not None else "",
            "collectedAt": self.collectedAt,
        }


# --- Product Entity ---

class ProductContent(BaseModel):
    productName: Optional[str] = Field(None, description="Product or offering name")
    startupName: str = Field(..., description="Canonical parent startup name")
    pricingModel: PricingModelEnum = Field(..., description="Commercial pricing tier")
    description: Optional[str] = Field(None, description="Product overview")


class ProductEntity(BaseModel):
    schemaVersion: str = Field(default="1.0")
    recordType: Literal["PRODUCT"] = Field(default="PRODUCT")
    source: SourceMeta
    content: ProductContent
    collectedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "recordType": self.recordType,
            "source.name": self.source.name,
            "source.url": self.source.url,
            "content.productName": self.content.productName or "",
            "content.startupName": self.content.startupName,
            "content.pricingModel": self.content.pricingModel.value,
            "collectedAt": self.collectedAt,
        }


# --- Research Paper Entity ---

class ResearchPaperContent(BaseModel):
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(..., description="Authors list")
    paper_url: str = Field(..., description="arXiv or landing page URL")
    github_url: Optional[str] = Field(None, description="Associated code repository URL")
    github_stars: Optional[int] = Field(None, description="Stargazers count")
    published_date: str = Field(..., description="Publication date in ISO-8601")


class ResearchPaperEntity(BaseModel):
    schemaVersion: str = Field(default="1.0")
    recordType: Literal["RESEARCH_PAPER"] = Field(default="RESEARCH_PAPER")
    content: ResearchPaperContent
    collectedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "recordType": self.recordType,
            "content.title": self.content.title,
            "content.authors": json.dumps(self.content.authors) if isinstance(self.content.authors, list) else str(self.content.authors),
            "content.paper_url": self.content.paper_url,
            "content.github_url": self.content.github_url or "",
            "content.github_stars": self.content.github_stars if self.content.github_stars is not None else 0,
            "content.published_date": self.content.published_date,
        }


# --- Job Entity ---

class JobContent(BaseModel):
    title: Optional[str] = Field(None, description="Position title")
    company: str = Field(..., description="Hiring organization")
    date: str = Field(..., description="Posting date in ISO-8601")
    is_remote: bool = Field(..., description="Remote eligibility flag")
    role_family: str = Field(..., description="Functional group: Engineering, Product, Research, etc.")
    url: Optional[str] = Field(None, description="Application link")


class JobEntity(BaseModel):
    schemaVersion: str = Field(default="1.0")
    recordType: Literal["JOB"] = Field(default="JOB")
    content: JobContent
    collectedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "recordType": self.recordType,
            "content.title": self.content.title or "",
            "content.company": self.content.company,
            "content.date": self.content.date,
            "content.is_remote": self.content.is_remote,
            "content.role_family": self.content.role_family,
        }


# --- News Entity ---

class NewsContent(BaseModel):
    title: str = Field(..., description="Article headline")
    published_date: str = Field(..., description="Publication date in ISO-8601")
    author: Optional[str] = Field(None, description="Author / byline")
    summary: Optional[str] = Field(None, description="Article summary")
    full_text: Optional[str] = Field(None, description="Extracted body text")


class NewsEntity(BaseModel):
    schemaVersion: str = Field(default="1.0")
    recordType: Literal["NEWS"] = Field(default="NEWS")
    source: SourceMeta
    content: NewsContent
    collectedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "recordType": self.recordType,
            "source.name": self.source.name,
            "source.url": self.source.url,
            "content.title": self.content.title,
            "content.published_date": self.content.published_date,
            "content.author": self.content.author or "",
            "content.summary": (self.content.summary or "")[:400],
            "collectedAt": self.collectedAt,
        }


# --- Entity Mapping Log ---

class EntityMappingLog(BaseModel):
    raw_name: str = Field(..., description="Unprocessed string extracted from source")
    canonical_name: str = Field(..., description="Normalized canonical identifier")
    entity_type: str = Field(..., description="STARTUP, PRODUCT, or COMPANY")
    resolution_method: str = Field(
        ...,
        description="EXACT_SEED, DOMAIN_MATCH, FUZZY_TOKEN_SORT, or RULE_NORMALIZATION"
    )
    confidence_score: float = Field(..., description="Confidence score (0.0 to 1.0)")
    resolved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_flat_dict(self) -> dict:
        return {
            "raw_name": self.raw_name,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "resolution_method": self.resolution_method,
            "confidence_score": round(self.confidence_score, 4),
            "resolved_at": self.resolved_at,
        }
