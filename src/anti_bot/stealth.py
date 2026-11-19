"""
Anti-Bot Evasion & Stealth Navigation Architecture.
Handles Cloudflare Turnstile, perimeter challenges, TLS fingerprinting,
and headless browser detection countermeasures.
"""

import random
from typing import Dict, List, Optional


class StealthHeaders:
    """Generates authentic browser headers matching modern Chrome and Safari releases."""

    CHROME_VERSIONS = ["128.0.0.0", "129.0.0.0", "130.0.0.0", "131.0.0.0"]
    PLATFORMS = [
        ("Windows NT 10.0; Win64; x64", '"Windows"'),
        ("Macintosh; Intel Mac OS X 10_15_7", '"macOS"'),
        ("X11; Linux x86_64", '"Linux"'),
    ]

    @classmethod
    def get_headers(cls, referer: Optional[str] = None) -> Dict[str, str]:
        version = random.choice(cls.CHROME_VERSIONS)
        major = version.split(".")[0]
        os_str, sec_platform = random.choice(cls.PLATFORMS)

        ua = f"Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"

        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Sec-Ch-Ua": f'"Chromium";v="{major}", "Not=A?Brand";v="24", "Google Chrome";v="{major}"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": sec_platform,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"

        return headers


class PlaywrightStealthConfig:
    """JavaScript injection snippets to evade common bot detection frameworks (FingerprintJS, Datadome, Cloudflare)."""

    STEALTH_JS = """
    // 1. Mask navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // 2. Mock plugins array
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // 3. Mock languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    // 4. Mock WebGL vendor & renderer
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
            return 'Google Inc. (NVIDIA)';
        }
        if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
            return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        }
        return getParameter.apply(this, arguments);
    };

    // 5. Mock Chrome runtime
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    """

    @classmethod
    def is_cloudflare_challenge(cls, status_code: int, html_body: str) -> bool:
        """Detects whether a response is a Cloudflare managed challenge or Turnstile gate."""
        if status_code in (403, 503):
            indicators = [
                "cf-turnstile",
                "challenge-platform",
                "Checking your browser",
                "Just a moment...",
                "cloudflare-static",
                "ray ID:",
            ]
            return any(ind.lower() in html_body.lower() for ind in indicators)
        return False
