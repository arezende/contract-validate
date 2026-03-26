"""Global configuration for the scientific ContractFOL pipeline."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
REPORTS_DIR = BASE_DIR / "reports"

LLM_PROVIDER = os.getenv("CONTRACTFOL_LLM", "anthropic")
LLM_MODEL = os.getenv("CONTRACTFOL_MODEL", "claude-sonnet-4-20250514")
LLM_TEMPERATURE = float(os.getenv("CONTRACTFOL_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("CONTRACTFOL_MAX_TOKENS", "4096"))

Z3_TIMEOUT_MS = int(os.getenv("CONTRACTFOL_Z3_TIMEOUT_MS", "30000"))
MAX_REFINEMENT_ITERATIONS = int(os.getenv("CONTRACTFOL_MAX_REFINEMENT", "3"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONTRACTFOL_CONFIDENCE_THRESHOLD", "0.7"))
