"""Configurações globais — ContractFOL V3."""

import os
from pathlib import Path

# Carregar variáveis do .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# === Diretórios ===
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
TESTS_DIR = BASE_DIR / "tests"
REPORTS_DIR = BASE_DIR / "data" / "output"

for d in [INPUT_DIR, OUTPUT_DIR, TESTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === LLM ===
LLM_PROVIDER = os.getenv("CONTRACTFOL_LLM", "anthropic")
LLM_MODEL = os.getenv("CONTRACTFOL_MODEL", "claude-sonnet-4-20250514")
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 4096
LLM_API_KEY = os.getenv("CONTRACTFOL_API_KEY")

# === Z3 ===
Z3_TIMEOUT_MS = 30000
Z3_MAX_MEMORY_MB = 4096

# === Pipeline ===
MAX_REFINEMENT_ITERATIONS = 3
CONFIDENCE_THRESHOLD = 0.7
PRAZO_RAZOAVEL_DIAS = 365  # Prazos > 365 dias para ações recorrentes = alerta
MIN_OBRIGACOES_COM_PENALIDADE = 0.5  # Pelo menos 50% das obrigações devem ter penalidade
