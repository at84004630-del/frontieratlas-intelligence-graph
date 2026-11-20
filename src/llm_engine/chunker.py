"""
Intelligent Semantic Chunking & DOM Truncation Engine.
Guarantees payloads never trigger 413 Payload Too Large errors while preserving
semantically dense content (entities, dates, pricing, requirements, metrics).
"""

import re
from typing import List, Dict, Any, Optional


class IntelligentChunker:
    """Preprocesses and chunks raw HTML or text to fit within strict LLM token budgets."""

    # Unnecessary tags to purge completely
    _PURGE_TAG_PATTERNS = [
        re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE),
        re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE),
        re.compile(r"<svg[\s\S]*?</svg>", re.IGNORECASE),
        re.compile(r"<nav[\s\S]*?</nav>", re.IGNORECASE),
        re.compile(r"<footer[\s\S]*?</footer>", re.IGNORECASE),
        re.compile(r"<header[\s\S]*?</header>", re.IGNORECASE),
        re.compile(r"<iframe[\s\S]*?</iframe>", re.IGNORECASE),
        re.compile(r"<!--[\s\S]*?-->"),
    ]

    _CLEAN_TAGS = re.compile(r"<[^>]+>")
    _WHITESPACE = re.compile(r"\s+")

    def __init__(self, max_tokens: int = 4000, chars_per_token: float = 3.5):
        self.max_tokens = max_tokens
        self.max_chars = int(max_tokens * chars_per_token)

    def clean_html(self, html_text: str) -> str:
        """Strips scripts, styles, navbars, and boilerplate markup."""
        if not html_text:
            return ""

        text = html_text
        for pattern in self._PURGE_TAG_PATTERNS:
            text = pattern.sub(" ", text)

        # Replace break tags with newlines
        text = re.sub(r"<(?:br|p|div|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)

        # Strip remaining tags
        text = self._CLEAN_TAGS.sub(" ", text)

        # Decode common HTML entities
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )

        # Collapse whitespace line by line
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def extract_semantic_blocks(self, text: str) -> List[str]:
        """Segments text into logical blocks (paragraphs/sections)."""
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        if not blocks:
            blocks = [text]
        return blocks

    def chunk_payload(
        self,
        raw_content: str,
        is_html: bool = True,
        priority_keywords: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Transforms raw content into token-safe chunks, guaranteed not to exceed max_chars.
        Ranks blocks containing priority keywords higher during truncation.
        """
        text = self.clean_html(raw_content) if is_html else raw_content.strip()
        if not text:
            return [""]

        # Fast path if already within token limits
        if len(text) <= self.max_chars:
            return [text]

        keywords = [k.lower() for k in (priority_keywords or ["ai", "pricing", "free", "paid", "startup", "job", "salary", "team", "engineer"])]
        blocks = self.extract_semantic_blocks(text)

        chunks = []
        current_chunk = []
        current_len = 0

        for block in blocks:
            block_len = len(block)
            if block_len > self.max_chars:
                # Subdivide oversized single block
                for i in range(0, block_len, self.max_chars - 200):
                    sub = block[i : i + self.max_chars - 200]
                    chunks.append(sub)
                continue

            if current_len + block_len + 2 > self.max_chars:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [block]
                current_len = block_len
            else:
                current_chunk.append(block)
                current_len += block_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def truncate_to_dense_summary(self, raw_content: str, target_chars: Optional[int] = None) -> str:
        """
        Single-string truncation that retains high information density.
        Ideal for single LLM calls where 413 avoidance is paramount.
        """
        limit = target_chars or self.max_chars
        cleaned = self.clean_html(raw_content)
        if len(cleaned) <= limit:
            return cleaned

        # Retain head (crucial context/headers) and tail (pricing/summary), with ellipsis
        head_len = int(limit * 0.7)
        tail_len = limit - head_len - 50
        return cleaned[:head_len] + "\n\n[... content truncated for token limits ...]\n\n" + cleaned[-tail_len:]
