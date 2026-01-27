# ContractFOL Makefile

.PHONY: install test lint format demo experiment clean help

# Instalação
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testes
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=contractfol --cov-report=html

# Qualidade de código
lint:
	ruff check src/
	mypy src/contractfol/

format:
	black src/ tests/
	ruff check --fix src/

# Demo e experimento
demo:
	python -c "from contractfol.cli import demo; demo()"

experiment:
	python scripts/run_experiment.py

experiment-full:
	python scripts/run_experiment.py --methods contractfol gpt4_cot claude_cot baseline --runs 3

# CLI
validate:
	contractfol validate $(FILE)

translate:
	contractfol translate "$(CLAUSE)"

# Limpeza
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Ajuda
help:
	@echo "ContractFOL - Validação Automatizada de Contratos"
	@echo ""
	@echo "Comandos disponíveis:"
	@echo "  make install       - Instala o pacote"
	@echo "  make install-dev   - Instala com dependências de desenvolvimento"
	@echo "  make test          - Executa testes"
	@echo "  make test-cov      - Executa testes com cobertura"
	@echo "  make lint          - Verifica qualidade do código"
	@echo "  make format        - Formata código"
	@echo "  make demo          - Executa demonstração"
	@echo "  make experiment    - Executa experimento de avaliação"
	@echo "  make clean         - Remove arquivos temporários"
	@echo ""
	@echo "Exemplos:"
	@echo "  make validate FILE=contrato.txt"
	@echo "  make translate CLAUSE='O patrocinador obriga-se a pagar'"
