"""
Deterministic Multi-Pass Entity Resolution Engine for GraphOne / FrontierAtlas.
Canonicalizes raw startup, product, and company names against ground-truth seed registries.
"""

from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime, timezone
import re

from .seed_database import CANONICAL_SEED_DATABASE
from .normalizer import EntityNormalizer, SimilarityMetrics
from ..schemas.models import EntityMappingLog


class EntityResolver:
    """Production-grade deterministic entity resolver with comprehensive audit logging."""

    def __init__(self, seed_db: Optional[Dict] = None):
        self.seed_db = seed_db or CANONICAL_SEED_DATABASE
        self.mapping_log: List[EntityMappingLog] = []
        self._build_index()

    def _build_index(self):
        """Builds multi-tier lookup indices for rapid O(1) matching."""
        self.exact_map: Dict[str, str] = {}         # lower_raw -> Canonical
        self.normalized_map: Dict[str, str] = {}    # cleaned_string -> Canonical
        self.domain_map: Dict[str, str] = {}        # domain -> Canonical
        self.product_map: Dict[str, str] = {}       # lower_product -> Canonical Startup

        for canonical, meta in self.seed_db.items():
            # Canonical name itself
            self.exact_map[canonical.lower()] = canonical
            self.normalized_map[EntityNormalizer.clean(canonical)] = canonical

            # Aliases
            for alias in meta.get("aliases", []):
                self.exact_map[alias.lower()] = canonical
                self.normalized_map[EntityNormalizer.clean(alias)] = canonical

            # Domains
            for domain in meta.get("domains", []):
                self.domain_map[domain.lower()] = canonical

            # Products
            for product in meta.get("products", []):
                self.product_map[product.lower()] = canonical
                self.product_map[EntityNormalizer.clean(product)] = canonical

    def extract_domain(self, url_or_domain: str) -> Optional[str]:
        """Extracts the registered domain from an arbitrary URL or domain string."""
        if not url_or_domain:
            return None
        text = str(url_or_domain).strip().lower()
        if not text.startswith("http://") and not text.startswith("https://"):
            text = "https://" + text
        try:
            parsed = urlparse(text)
            hostname = parsed.hostname or ""
            # Strip leading www.
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname
        except Exception:
            return None

    def resolve_startup(
        self,
        raw_name: str,
        source_url: Optional[str] = None,
        entity_type: str = "STARTUP",
    ) -> Tuple[str, float, str]:
        """
        Executes multi-pass deterministic canonicalization.
        Returns: (canonical_name, confidence_score, resolution_method)
        """
        if not raw_name or not raw_name.strip():
            return "Unknown Entity", 0.0, "FAILED"

        raw_str = raw_name.strip()
        raw_lower = raw_str.lower()
        cleaned = EntityNormalizer.clean(raw_str)

        # -----------------------------------------------------
        # PASS 1: Exact Match on Seed Registry & Aliases (1.00)
        # -----------------------------------------------------
        if raw_lower in self.exact_map:
            canonical = self.exact_map[raw_lower]
            self._log(raw_str, canonical, entity_type, "EXACT_SEED", 1.00)
            return canonical, 1.00, "EXACT_SEED"

        # -----------------------------------------------------
        # PASS 2: Domain-Based Extraction & Resolution (0.99)
        # -----------------------------------------------------
        if source_url:
            domain = self.extract_domain(source_url)
            if domain and domain in self.domain_map:
                canonical = self.domain_map[domain]
                self._log(raw_str, canonical, entity_type, "DOMAIN_MATCH", 0.99)
                return canonical, 0.99, "DOMAIN_MATCH"

        # -----------------------------------------------------
        # PASS 3: Normalized String Match (0.95)
        # -----------------------------------------------------
        if cleaned and cleaned in self.normalized_map:
            canonical = self.normalized_map[cleaned]
            self._log(raw_str, canonical, entity_type, "NORMALIZATION_RULE", 0.95)
            return canonical, 0.95, "NORMALIZATION_RULE"

        # -----------------------------------------------------
        # PASS 4: High-Precision Fuzzy Token Sort (Threshold > 0.88)
        # -----------------------------------------------------
        best_match = None
        best_score = 0.0

        for seed_clean, canonical in self.normalized_map.items():
            if not seed_clean:
                continue
            score = SimilarityMetrics.token_sort_ratio(cleaned, seed_clean)
            if score > best_score:
                best_score = score
                best_match = canonical

        if best_match and best_score >= 0.88:
            self._log(raw_str, best_match, entity_type, "FUZZY_MATCH", best_score)
            return best_match, best_score, "FUZZY_MATCH"

        # -----------------------------------------------------
        # PASS 5: Fallback Clean Rule Normalization (0.80)
        # -----------------------------------------------------
        # If not in seed list, normalize title-cased entity name cleanly
        canonical = EntityNormalizer.title_case(raw_str)
        if not canonical:
            canonical = raw_str
        self._log(raw_str, canonical, entity_type, "RULE_NORMALIZATION", 0.80)
        return canonical, 0.80, "RULE_NORMALIZATION"

    def resolve_product(
        self,
        raw_product_name: str,
        startup_name: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> Tuple[str, str, float, str]:
        """
        Resolves product name and links it to its canonical parent startup.
        Returns: (canonical_product_name, canonical_startup_name, confidence, method)
        """
        raw_prod = (raw_product_name or "").strip()
        cleaned_prod = EntityNormalizer.clean(raw_prod)

        # Check product registry
        parent_startup = None
        if raw_prod.lower() in self.product_map:
            parent_startup = self.product_map[raw_prod.lower()]
        elif cleaned_prod in self.product_map:
            parent_startup = self.product_map[cleaned_prod]

        # If startup name provided, resolve startup
        if startup_name:
            resolved_startup, conf, method = self.resolve_startup(
                startup_name, source_url=source_url, entity_type="PRODUCT_STARTUP"
            )
            canonical_startup = parent_startup or resolved_startup
        else:
            canonical_startup = parent_startup or "Unknown Startup"

        canonical_product = EntityNormalizer.title_case(raw_prod)
        self._log(raw_prod, canonical_product, "PRODUCT", "PRODUCT_RULE", 0.90)
        return canonical_product, canonical_startup, 0.90, "PRODUCT_RULE"

    def _log(
        self,
        raw_name: str,
        canonical_name: str,
        entity_type: str,
        method: str,
        confidence: float,
    ):
        """Append to deterministic resolution audit log."""
        self.mapping_log.append(
            EntityMappingLog(
                raw_name=raw_name,
                canonical_name=canonical_name,
                entity_type=entity_type,
                resolution_method=method,
                confidence_score=confidence,
                resolved_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def get_logs(self) -> List[EntityMappingLog]:
        """Returns the full audit log of all entity resolution operations."""
        return self.mapping_log
