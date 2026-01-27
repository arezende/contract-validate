"""
Configurações e fixtures para testes.
"""

import sys
from pathlib import Path

import pytest

# Adicionar src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_contract_text():
    """Texto de contrato de exemplo para testes."""
    return """
CONTRATO DE PATROCÍNIO ESPORTIVO

CLÁUSULA PRIMEIRA - DAS PARTES
O COMITÊ OLÍMPICO DO BRASIL, doravante denominado COB, e a empresa
PATROCINADORA S.A., doravante denominada PATROCINADOR, celebram o presente contrato.

CLÁUSULA SEGUNDA - DO OBJETO
O presente contrato tem por objeto o patrocínio de atletas olímpicos.

CLÁUSULA TERCEIRA - DAS OBRIGAÇÕES DO PATROCINADOR
O PATROCINADOR obriga-se a realizar o pagamento das parcelas até o quinto dia útil
de cada mês, no valor de R$ 100.000,00.

CLÁUSULA QUARTA - DO USO DA MARCA
O PATROCINADOR obriga-se a exibir a marca do COB em materiais promocionais.

CLÁUSULA QUINTA - RESTRIÇÕES
É vedado ao PATROCINADOR o uso da marca do COB sem autorização prévia.
"""


@pytest.fixture
def sample_clauses():
    """Lista de cláusulas de exemplo."""
    from contractfol.models import Clause

    return [
        Clause(
            id="c1",
            text="O PATROCINADOR obriga-se a realizar o pagamento mensal.",
            contract_id="test",
        ),
        Clause(
            id="c2",
            text="É vedado ao CONTRATADO utilizar a marca sem autorização.",
            contract_id="test",
        ),
        Clause(
            id="c3",
            text="O ATLETA poderá utilizar as instalações do centro.",
            contract_id="test",
        ),
    ]


@pytest.fixture
def ontology():
    """Ontologia de domínio."""
    from contractfol.ontology import get_ontology

    return get_ontology()
