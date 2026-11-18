"""
Global Pipeline Configuration and Environment Credentials.
"""

import os
from typing import Dict, Any

# General Execution Parameters
DEFAULT_CONCURRENCY = 15
DEFAULT_REQUEST_TIMEOUT = 25.0
DEFAULT_FRESHNESS_HOURS = 24.0

# LLM Providers Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Storage & Export Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
RAW_DIR = os.path.join(DATA_DIR, "raw")
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

# Target Data Verticals Minimum Thresholds
TARGET_STARTUPS = 1000
TARGET_PRODUCTS = 1000
TARGET_PAPERS = 1000
