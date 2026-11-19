"""
Intelligent Proxy Rotation & Health Scoring Pool.
Maintains domain-level session affinity, tracks success/failure ratios,
and automatically isolates burned or throttled IPs.
"""

import time
import random
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("proxy_rotator")


class ProxyNode:
    def __init__(self, url: str, is_residential: bool = True):
        self.url = url
        self.is_residential = is_residential
        self.successes = 0
        self.failures = 0
        self.last_used = 0.0
        self.is_quarantined = False
        self.quarantine_until = 0.0

    @property
    def score(self) -> float:
        total = self.successes + self.failures
        if total == 0:
            return 1.0
        return self.successes / total


class SmartProxyRotator:
    """Manages pool of proxies with health scoring and domain affinity."""

    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.nodes: List[ProxyNode] = [ProxyNode(p) for p in (proxy_list or [])]
        self.domain_sessions: Dict[str, ProxyNode] = {}

    def get_proxy(self, domain: Optional[str] = None) -> Optional[str]:
        """Returns the healthiest proxy, maintaining sticky sessions per domain if requested."""
        if not self.nodes:
            return None

        now = time.time()
        # Unquarantine recovered nodes
        for node in self.nodes:
            if node.is_quarantined and now > node.quarantine_until:
                node.is_quarantined = False
                logger.info(f"Proxy {node.url} recovered from quarantine.")

        active_nodes = [n for n in self.nodes if not n.is_quarantined]
        if not active_nodes:
            # Fallback to least bad node if all quarantined
            active_nodes = self.nodes

        # Sticky domain session check
        if domain and domain in self.domain_sessions:
            sticky = self.domain_sessions[domain]
            if not sticky.is_quarantined:
                sticky.last_used = now
                return sticky.url

        # Weighted selection based on score
        weights = [max(0.1, n.score) for n in active_nodes]
        chosen = random.choices(active_nodes, weights=weights, k=1)[0]
        chosen.last_used = now

        if domain:
            self.domain_sessions[domain] = chosen

        return chosen.url

    def report_result(self, proxy_url: str, success: bool, status_code: int = 200):
        """Updates health statistics following request completion."""
        for node in self.nodes:
            if node.url == proxy_url:
                if success:
                    node.successes += 1
                else:
                    node.failures += 1
                    if status_code in (403, 429, 503):
                        # Quarantine for 5 minutes
                        node.is_quarantined = True
                        node.quarantine_until = time.time() + 300.0
                        logger.warning(f"Quarantining proxy {proxy_url} for 300s due to HTTP {status_code}")
                break
