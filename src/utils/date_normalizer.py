"""
Robust Date Normalization & 24-Hour Freshness Engine.
Handles ISO-8601, RFC-2822, relative strings ('2 hours ago'), epoch timestamps,
and HTML meta tags with clock-skew tolerance and deterministic heuristics.
"""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import re
from typing import Optional, Tuple


class DateNormalizer:
    """Production-grade date normalizer with strict 24-hour freshness verification."""

    # Pre-compiled regex patterns for relative time
    _RELATIVE_PATTERNS = [
        (re.compile(r"(\d+)\s*(?:sec|second)s?\s*ago", re.IGNORECASE), "seconds"),
        (re.compile(r"(\d+)\s*(?:min|minute)s?\s*ago", re.IGNORECASE), "minutes"),
        (re.compile(r"(\d+)\s*(?:hr|hour)s?\s*ago", re.IGNORECASE), "hours"),
        (re.compile(r"(\d+)\s*(?:d|day)s?\s*ago", re.IGNORECASE), "days"),
        (re.compile(r"just\s*now", re.IGNORECASE), "just_now"),
        (re.compile(r"yesterday", re.IGNORECASE), "yesterday"),
        (re.compile(r"today", re.IGNORECASE), "today"),
    ]

    _ABSOLUTE_FORMATS = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    @classmethod
    def parse(
        cls,
        date_input: Optional[str | int | float | datetime],
        reference_time: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        Normalize an arbitrary date input into a timezone-aware UTC datetime.
        Returns None if parsing fails completely.
        """
        if not date_input:
            return None

        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # 1. Already datetime
        if isinstance(date_input, datetime):
            if date_input.tzinfo is None:
                return date_input.replace(tzinfo=timezone.utc)
            return date_input.astimezone(timezone.utc)

        # 2. Integer/Float Epoch Timestamp
        if isinstance(date_input, (int, float)):
            try:
                # Distinguish milliseconds vs seconds
                ts = float(date_input)
                if ts > 1e11:  # Milliseconds
                    ts /= 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                return None

        # 3. String Processing
        raw = str(date_input).strip()
        if not raw:
            return None

        # Check for numeric timestamp in string format
        if raw.isdigit():
            return cls.parse(float(raw), reference_time=now)

        # Check relative formats
        for pattern, unit in cls._RELATIVE_PATTERNS:
            match = pattern.search(raw)
            if match:
                if unit == "just_now" or unit == "today":
                    return now
                elif unit == "yesterday":
                    return now - timedelta(days=1)
                elif match.groups():
                    val = int(match.group(1))
                    if unit == "seconds":
                        return now - timedelta(seconds=val)
                    elif unit == "minutes":
                        return now - timedelta(minutes=val)
                    elif unit == "hours":
                        return now - timedelta(hours=val)
                    elif unit == "days":
                        return now - timedelta(days=val)

        # Try RFC-2822 (standard for RSS pubDate: e.g. "Fri, 20 Nov 2026 15:30:00 +0000")
        try:
            rfc_dt = parsedate_to_datetime(raw)
            if rfc_dt:
                if rfc_dt.tzinfo is None:
                    return rfc_dt.replace(tzinfo=timezone.utc)
                return rfc_dt.astimezone(timezone.utc)
        except Exception:
            pass

        # Try fromisoformat (Python 3.11+ handles most ISO formats)
        try:
            iso_raw = raw.replace("Z", "+00:00")
            iso_dt = datetime.fromisoformat(iso_raw)
            if iso_dt.tzinfo is None:
                return iso_dt.replace(tzinfo=timezone.utc)
            return iso_dt.astimezone(timezone.utc)
        except Exception:
            pass

        # Try strptime with known patterns
        for fmt in cls._ABSOLUTE_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue

        return None

    @classmethod
    def is_within_24_hours(
        cls,
        date_input: Optional[str | int | float | datetime],
        reference_time: Optional[datetime] = None,
        max_age_hours: float = 24.0,
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Validates whether the item was published within the last 24 hours.
        Allows up to 1 hour future skew for server time drift.
        Returns: (is_fresh: bool, parsed_datetime: Optional[datetime])
        """
        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        parsed_dt = cls.parse(date_input, reference_time=now)
        if not parsed_dt:
            return False, None

        age_seconds = (now - parsed_dt).total_seconds()
        # Accept between -3600s (future clock skew) and max_age_hours * 3600
        is_fresh = -3600 <= age_seconds <= (max_age_hours * 3600)
        return is_fresh, parsed_dt

    @classmethod
    def format_iso(cls, dt: Optional[datetime]) -> str:
        """Standardize output to ISO-8601 UTC string."""
        if not dt:
            return datetime.now(timezone.utc).isoformat()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
