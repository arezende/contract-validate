"""
Testes do Pipeline ContractFOL.
"""

import pytest

from contractfol.models import Clause, Contract, DeonticModality
from contractfol.ontology import ContractOntology, get_ontology
from contractfol.extractors import ClauseExtractor
from contractfol.classifiers import DeonticClassifier
from contractfol.translators.nl_fol_translator import FOLSyntaxValidator


class TestOntology:
    """Testes da ontologia de domínio."""

    def test_ontology_creation(self):
        ontology = ContractOntology()
        assert len(ontology.predicates) > 0
        assert "Obrigacao" in ontology.predicates
        assert "Permissao" in ontology.predicates
        assert "Proibicao" in ontology.predicates

    def test_predicate_signatures(self):
        ontology = get_ontology()
        signatures = ontology.get_predicate_signatures()
        assert "Obrigacao(agente, acao, prazo)" in signatures

    def test_validate_formula_predicates(self):
        ontology = get_ontology()

        # Fórmula válida
        is_valid, unknown = ontology.validate_formula_predicates(
            "Obrigacao(patrocinador, Pagamento(parcelas), prazo)"
        )
        assert is_valid

        # Fórmula com predicado desconhecido
        is_valid, unknown = ontology.validate_formula_predicates(
            "PredicadoInexistente(x, y)"
        )
        assert not is_valid
        assert "PredicadoInexistente" in unknown


class TestClauseExtractor:
    """Testes do extrator de cláusulas."""

    def test_extract_basic_clauses(self):
        text = """
        CLÁUSULA PRIMEIRA - DAS PARTES
        O CONTRATANTE e o CONTRATADO celebram o presente contrato.

        CLÁUSULA SEGUNDA - DO OBJETO
        O presente contrato tem por objeto a prestação de serviços.

        CLÁUSULA TERCEIRA - DAS OBRIGAÇÕES
        O CONTRATADO obriga-se a executar os serviços com diligência.
        """
        extractor = ClauseExtractor()
        contract = extractor.extract_from_text(text)

        assert len(contract.clauses) >= 3
        assert any("PRIMEIRA" in c.text or "PARTES" in c.text for c in contract.clauses)

    def test_extract_numbered_clauses(self):
        text = """
        Art. 1º Este contrato estabelece as condições gerais.
        Art. 2º O pagamento será mensal.
        Art. 3º O prazo de vigência é de 12 meses.
        """
        extractor = ClauseExtractor()
        contract = extractor.extract_from_text(text)

        assert len(contract.clauses) >= 3

    def test_extract_parties(self):
        text = """
        O CONTRATANTE e o CONTRATADO, também denominado PATROCINADOR,
        celebram o presente contrato de patrocínio.
        """
        extractor = ClauseExtractor()
        contract = extractor.extract_from_text(text)

        party_roles = [p.role for p in contract.parties]
        assert "CONTRATANTE" in party_roles or any("CONTRATANTE" in r for r in party_roles)


class TestDeonticClassifier:
    """Testes do classificador deôntico."""

    def test_classify_obligation(self):
        classifier = DeonticClassifier()
        clause = Clause(
            id="1",
            text="O CONTRATADO obriga-se a entregar o produto até o dia 30.",
            contract_id="test",
        )
        modality, confidence = classifier.classify(clause)

        assert modality == DeonticModality.OBRIGACAO_ATIVA
        assert confidence > 0.5

    def test_classify_prohibition(self):
        classifier = DeonticClassifier()
        clause = Clause(
            id="2",
            text="É vedado ao CONTRATADO utilizar a marca sem autorização.",
            contract_id="test",
        )
        modality, confidence = classifier.classify(clause)

        assert modality == DeonticModality.PROIBICAO
        assert confidence > 0.5

    def test_classify_permission(self):
        classifier = DeonticClassifier()
        clause = Clause(
            id="3",
            text="O ATLETA poderá utilizar as instalações do centro de treinamento.",
            contract_id="test",
        )
        modality, confidence = classifier.classify(clause)

        assert modality == DeonticModality.PERMISSAO
        assert confidence > 0.5

    def test_classify_condition(self):
        classifier = DeonticClassifier()
        clause = Clause(
            id="4",
            text="Caso o PATROCINADOR não realize o pagamento, incidirá multa.",
            contract_id="test",
        )
        modality, confidence = classifier.classify(clause)

        assert modality == DeonticModality.CONDICAO
        assert confidence > 0.3


class TestFOLValidator:
    """Testes do validador de sintaxe FOL."""

    def test_valid_formula(self):
        validator = FOLSyntaxValidator()
        formula = "Obrigacao(patrocinador, Pagamento(parcelas), prazo)"
        is_valid, errors = validator.validate(formula)

        assert is_valid
        assert len(errors) == 0

    def test_unbalanced_parentheses(self):
        validator = FOLSyntaxValidator()
        formula = "Obrigacao(patrocinador, Pagamento(parcelas), prazo"
        is_valid, errors = validator.validate(formula)

        assert not is_valid
        assert any("parênteses" in e.lower() for e in errors)

    def test_empty_formula(self):
        validator = FOLSyntaxValidator()
        is_valid, errors = validator.validate("")

        assert not is_valid
        assert any("vazia" in e.lower() for e in errors)


class TestModels:
    """Testes dos modelos de dados."""

    def test_clause_creation(self):
        clause = Clause(
            id="test_1",
            text="Texto da cláusula",
            contract_id="contract_1",
        )
        assert clause.id == "test_1"
        assert clause.modality is None

    def test_contract_creation(self):
        contract = Contract(
            id="contract_1",
            title="Contrato de Teste",
        )
        assert contract.clause_count == 0
        assert not contract.processed

    def test_contract_with_clauses(self):
        clause1 = Clause(id="c1", text="Cláusula 1", contract_id="contract_1")
        clause2 = Clause(id="c2", text="Cláusula 2", contract_id="contract_1")

        contract = Contract(
            id="contract_1",
            title="Contrato de Teste",
            clauses=[clause1, clause2],
        )
        assert contract.clause_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
