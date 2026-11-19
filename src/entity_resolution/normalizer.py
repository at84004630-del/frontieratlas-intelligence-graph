"""
Text Normalization & Fuzzy Similarity Metrics for Entity Resolution.
Zero-dependency, high-speed pure Python implementations of Levenshtein,
Jaro-Winkler, and Token-Sort ratio with corporate legal suffix stripping.
"""

import re
from typing import Set


class EntityNormalizer:
    """Preprocesses entity strings by stripping corporate legal suffixes, punctuation, and noisy terms."""

    # Common corporate legal suffixes and designations
    _SUFFIX_PATTERN = re.compile(
        r"\b(?:inc|incorporated|corp|corporation|llc|l\.l\.c|ltd|limited|co|company|gmbh|s\.a|s\.a\.s|sas|s\.r\.l|p\.b\.c|pbc|"
        r"pvt|private|technologies|technology|tech|labs|laboratory|holdings|group|systems|software|ai|a\.i)\b\.?",
        re.IGNORECASE
    )

    _PUNCT_PATTERN = re.compile(r"[\.,\-_/\\#@!?:;()\[\]{}'\"`~]")

    @classmethod
    def clean(cls, text: str) -> str:
        """Removes corporate designations, punctuation, and excess whitespace."""
        if not text:
            return ""

        # Normalize unicode and lower
        cleaned = text.strip()

        # Remove domain extensions if present (e.g. .ai, .com, .io)
        cleaned = re.sub(r"\.(?:com|ai|io|co|org|net|app|dev|art)\b", "", cleaned, flags=re.IGNORECASE)

        # Remove corporate suffixes
        cleaned = cls._SUFFIX_PATTERN.sub(" ", cleaned)

        # Remove punctuation
        cleaned = cls._PUNCT_PATTERN.sub(" ", cleaned)

        # Collapse whitespace and lowercase
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    @classmethod
    def title_case(cls, text: str) -> str:
        """Clean title case formatting for canonical presentation."""
        cleaned = cls.clean(text)
        return " ".join(word.capitalize() for word in cleaned.split())


class SimilarityMetrics:
    """High-speed string similarity algorithms for deterministic canonical resolution."""

    @staticmethod
    def jaro_winkler(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
        """Computes Jaro-Winkler similarity metric (0.0 to 1.0)."""
        if not s1 or not s2:
            return 1.0 if s1 == s2 else 0.0
        if s1 == s2:
            return 1.0

        len1, len2 = len(s1), len(s2)
        match_bound = max(len1, len2) // 2 - 1
        if match_bound < 0:
            match_bound = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2
        matches = 0

        for i in range(len1):
            start = max(0, i - match_bound)
            end = min(i + match_bound + 1, len2)
            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        # Transpositions
        k = 0
        transpositions = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        transpositions //= 2

        jaro = (
            (matches / len1) +
            (matches / len2) +
            ((matches - transpositions) / matches)
        ) / 3.0

        # Winkler prefix bonus (up to 4 chars)
        prefix = 0
        for i in range(min(4, min(len1, len2))):
            if s1[i] == s2[i]:
                prefix += 1
            else:
                break

        return jaro + (prefix * prefix_weight * (1.0 - jaro))

    @classmethod
    def token_sort_ratio(cls, s1: str, s2: str) -> float:
        """Sorts tokens alphabetically and computes Jaro-Winkler similarity."""
        tokens1 = " ".join(sorted(s1.split()))
        tokens2 = " ".join(sorted(s2.split()))
        return cls.jaro_winkler(tokens1, tokens2)
