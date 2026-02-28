"""
Testes do Detector de Cláusulas Abusivas.

Testa as 3 camadas de detecção (heurística, formal, LLM)
e a integração com o pipeline principal.
"""

import pytest

from contractfol.detectors.abusive_clause_detector import (
    AbusiveClauseDetector,
    DetectorConfig,
)
from contractfol.knowledge.legal_rules import LegalRule, get_legal_rules, get_rule_by_id
from contractfol.models import (
    AbusiveClauseType,
    AbusiveClauseViolation,
    Clause,
    Contract,
    ValidationReport,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def detector():
    """Detector com todas as camadas heurística e formal ativas, sem LLM."""
    config = DetectorConfig(
        use_heuristics=True,
        use_formal_verification=True,
        use_llm=False,  # Sem LLM nos testes unitários
        multa_threshold_percent=10.0,
        confidence_threshold=0.5,
    )
    return AbusiveClauseDetector(config=config)


@pytest.fixture
def detector_heuristic_only():
    """Detector apenas com camada heurística."""
    config = DetectorConfig(
        use_heuristics=True,
        use_formal_verification=False,
        use_llm=False,
        confidence_threshold=0.5,
    )
    return AbusiveClauseDetector(config=config)


def _make_clause(text: str, clause_id: str = "test_clause_1") -> Clause:
    """Helper para criar cláusulas de teste."""
    return Clause(id=clause_id, text=text, contract_id="test_contract")


# ============================================================================
# Testes da Base de Regras Legais
# ============================================================================


class TestLegalRules:
    """Testes da base de conhecimento legal."""

    def test_rules_loaded(self):
        rules = get_legal_rules()
        assert len(rules) >= 14

    def test_all_rules_have_patterns(self):
        rules = get_legal_rules()
        for rule in rules:
            assert len(rule.heuristic_patterns) > 0, (
                f"Regra {rule.id} sem padrões heurísticos"
            )

    def test_all_rules_have_legal_basis(self):
        rules = get_legal_rules()
        for rule in rules:
            assert rule.legal_basis, f"Regra {rule.id} sem base legal"

    def test_all_rules_have_llm_hint(self):
        rules = get_legal_rules()
        for rule in rules:
            assert rule.llm_prompt_hint, f"Regra {rule.id} sem hint LLM"

    def test_get_rule_by_id(self):
        rule = get_rule_by_id("CC_424_EXCLUSAO_RESP")
        assert rule is not None
        assert rule.violation_type == AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE

    def test_get_rule_by_id_nonexistent(self):
        rule = get_rule_by_id("INEXISTENTE")
        assert rule is None

    def test_rule_heuristic_matching(self):
        rule = get_rule_by_id("CC_424_EXCLUSAO_RESP")
        assert rule is not None

        # Deve casar com texto de exclusão de responsabilidade
        matched, confidence = rule.matches_heuristic(
            "A CONTRATANTE fica isenta de qualquer responsabilidade"
        )
        assert matched
        assert confidence > 0.5

        # Não deve casar com texto normal
        matched, confidence = rule.matches_heuristic(
            "O prazo de vigência do presente contrato é de 12 meses."
        )
        assert not matched


# ============================================================================
# Testes da Camada 1: Detecção Heurística
# ============================================================================


class TestHeuristicDetection:
    """Testes da Camada 1 - detecção heurística."""

    def test_detect_exclusao_responsabilidade(self, detector_heuristic_only):
        clause = _make_clause(
            "A CONTRATANTE fica isenta de qualquer responsabilidade "
            "por danos causados à CONTRATADA na execução do objeto."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE in types

    def test_detect_rescisao_unilateral(self, detector_heuristic_only):
        clause = _make_clause(
            "A CONTRATANTE poderá rescindir o presente contrato a qualquer "
            "momento, independentemente de justa causa ou aviso prévio."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.RESCISAO_UNILATERAL in types

    def test_detect_modificacao_unilateral(self, detector_heuristic_only):
        clause = _make_clause(
            "A CONTRATANTE reserva-se o direito de alterar unilateralmente "
            "quaisquer condições deste contrato."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.MODIFICACAO_UNILATERAL in types

    def test_detect_multa_excessiva(self, detector_heuristic_only):
        clause = _make_clause(
            "Em caso de inadimplemento, incidirá multa de 50% sobre "
            "o valor total do contrato."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.MULTA_EXCESSIVA in types

    def test_multa_within_threshold_not_detected(self, detector_heuristic_only):
        clause = _make_clause(
            "Em caso de atraso no pagamento, incidirá multa de 2% "
            "sobre o valor da parcela em atraso."
        )
        violations = detector_heuristic_only.detect(clause)

        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.MULTA_EXCESSIVA not in types

    def test_detect_renuncia_direito(self, detector_heuristic_only):
        clause = _make_clause(
            "A CONTRATADA renuncia irrevogavelmente a qualquer direito "
            "de reclamação judicial ou extrajudicial."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.RENUNCIA_DIREITO in types

    def test_detect_desvantagem_exagerada(self, detector_heuristic_only):
        clause = _make_clause(
            "Todos os benefícios decorrentes da parceria serão de "
            "propriedade exclusiva da CONTRATANTE."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.DESVANTAGEM_EXAGERADA in types

    def test_detect_perda_prestacoes(self, detector_heuristic_only):
        clause = _make_clause(
            "Em caso de rescisão, a CONTRATADA perderá a totalidade dos "
            "valores já pagos, sem direito a devolução ou restituição."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.PERDA_PRESTACOES in types

    def test_detect_boa_fe_violacao(self, detector_heuristic_only):
        clause = _make_clause(
            "A CONTRATANTE poderá, a seu exclusivo critério, decidir "
            "sobre a continuidade dos serviços sem direito a qualquer "
            "questionamento pela CONTRATADA."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) >= 1
        types = [v.violation_type for v in violations]
        assert AbusiveClauseType.BOA_FE_VIOLACAO in types

    def test_clausula_normal_sem_violacao(self, detector_heuristic_only):
        clause = _make_clause(
            "O prazo de vigência do presente contrato é de 12 meses, "
            "contados a partir da data de assinatura."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) == 0

    def test_clausula_obrigacao_normal_sem_violacao(self, detector_heuristic_only):
        clause = _make_clause(
            "O CONTRATADO obriga-se a entregar o relatório mensal "
            "até o quinto dia útil de cada mês."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) == 0

    def test_clausula_permissao_normal_sem_violacao(self, detector_heuristic_only):
        clause = _make_clause(
            "O ATLETA poderá utilizar as instalações do centro de "
            "treinamento durante a vigência do contrato."
        )
        violations = detector_heuristic_only.detect(clause)

        assert len(violations) == 0


# ============================================================================
# Testes da Camada 2: Detecção Formal
# ============================================================================


class TestFormalDetection:
    """Testes da Camada 2 - verificação formal."""

    def test_detect_rescisao_assimetrica_formal(self):
        config = DetectorConfig(
            use_heuristics=False,
            use_formal_verification=True,
            use_llm=False,
            confidence_threshold=0.5,
        )
        detector = AbusiveClauseDetector(config=config)

        clause = _make_clause(
            "O CONTRATANTE poderá rescindir o presente instrumento, "
            "porém a CONTRATADA não poderá rescindir em nenhuma hipótese."
        )
        violations = detector.detect(clause)

        assert len(violations) >= 1
        assert any(
            v.detection_layer == "formal" and
            v.violation_type == AbusiveClauseType.RESCISAO_UNILATERAL
            for v in violations
        )

    def test_exclusao_resp_com_adesao_formal(self):
        config = DetectorConfig(
            use_heuristics=False,
            use_formal_verification=True,
            use_llm=False,
            confidence_threshold=0.5,
        )
        detector = AbusiveClauseDetector(config=config)

        clause = _make_clause(
            "O aderente aceita integralmente os termos deste contrato de adesão "
            "e fica isento de qualquer responsabilidade o fornecedor."
        )
        violations = detector.detect(clause)

        assert len(violations) >= 1
        assert any(
            v.detection_layer == "formal"
            for v in violations
        )


# ============================================================================
# Testes de Integração (Detector completo)
# ============================================================================


class TestAbusiveDetectorIntegration:
    """Testes de integração do detector completo."""

    def test_multiple_violations_same_clause(self, detector):
        clause = _make_clause(
            "A CONTRATANTE poderá rescindir o contrato a qualquer momento "
            "sem aviso prévio, ficando isenta de qualquer responsabilidade. "
            "A CONTRATADA renuncia irrevogavelmente a qualquer direito "
            "de reclamação."
        )
        violations = detector.detect(clause)

        assert len(violations) >= 2
        types = {v.violation_type for v in violations}
        assert len(types) >= 2

    def test_deduplication(self, detector):
        clause = _make_clause(
            "A empresa fica isenta de toda responsabilidade e exonera-se "
            "de qualquer responsabilidade por danos."
        )
        violations = detector.detect(clause)

        # Mesmo tipo de violação não deve aparecer duplicado
        type_counts = {}
        for v in violations:
            key = v.violation_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        for type_name, count in type_counts.items():
            assert count == 1, f"Violação {type_name} duplicada ({count}x)"

    def test_violation_has_all_fields(self, detector):
        clause = _make_clause(
            "A CONTRATANTE reserva-se o direito de alterar unilateralmente "
            "quaisquer condições deste contrato."
        )
        violations = detector.detect(clause)

        assert len(violations) >= 1
        v = violations[0]
        assert v.id
        assert v.clause_id == clause.id
        assert v.violation_type is not None
        assert v.legal_basis
        assert v.description
        assert v.suggestion
        assert v.severity in ("HIGH", "MEDIUM", "LOW")
        assert 0.0 <= v.confidence <= 1.0
        assert v.detection_layer in ("heuristic", "formal", "llm")

    def test_confidence_threshold_filtering(self):
        config = DetectorConfig(
            use_heuristics=True,
            use_formal_verification=False,
            use_llm=False,
            confidence_threshold=0.99,  # Limiar muito alto
        )
        detector = AbusiveClauseDetector(config=config)

        clause = _make_clause(
            "A CONTRATANTE reserva-se o direito de alterar unilateralmente "
            "quaisquer condições deste contrato."
        )
        violations = detector.detect(clause)

        # Com limiar muito alto, poucas ou nenhuma violação deve passar
        for v in violations:
            assert v.confidence >= 0.99


# ============================================================================
# Testes dos Modelos
# ============================================================================


class TestAbusiveModels:
    """Testes dos modelos de dados para cláusulas abusivas."""

    def test_abusive_clause_type_values(self):
        assert AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE.value == "EXCLUSAO_RESPONSABILIDADE"
        assert AbusiveClauseType.MULTA_EXCESSIVA.value == "MULTA_EXCESSIVA"

    def test_abusive_clause_violation_creation(self):
        violation = AbusiveClauseViolation(
            id="test_1",
            clause_id="clause_1",
            violation_type=AbusiveClauseType.MULTA_EXCESSIVA,
            legal_basis="CC, Art. 413",
            description="Multa excessiva detectada",
            suggestion="Reduzir multa",
            severity="HIGH",
            confidence=0.9,
            detection_layer="heuristic",
        )
        assert violation.id == "test_1"
        assert violation.violation_type == AbusiveClauseType.MULTA_EXCESSIVA
        assert violation.confidence == 0.9

    def test_validation_report_abusive_fields(self):
        report = ValidationReport(contract_ids=["c1"])
        assert report.abusive_clause_count == 0
        assert not report.has_abusive_clauses

        violation = AbusiveClauseViolation(
            id="test_1",
            clause_id="clause_1",
            violation_type=AbusiveClauseType.MULTA_EXCESSIVA,
            legal_basis="CC, Art. 413",
            description="Multa excessiva detectada",
            suggestion="Reduzir multa",
        )
        report.abusive_clauses.append(violation)

        assert report.abusive_clause_count == 1
        assert report.has_abusive_clauses


# ============================================================================
# Testes da Ontologia Estendida
# ============================================================================


class TestOntologyExtensions:
    """Testes dos novos predicados e axiomas da ontologia."""

    def test_new_predicates_exist(self):
        from contractfol.ontology import get_ontology

        ontology = get_ontology()
        new_predicates = [
            "Rescisao", "Multa", "RenunciaDir",
            "ModificacaoUnilateral", "ExclusaoResp", "ContratoAdesao",
        ]
        for pred in new_predicates:
            assert pred in ontology.predicates, (
                f"Predicado {pred} não encontrado na ontologia"
            )

    def test_new_axioms_count(self):
        from contractfol.ontology import ContractOntology

        ontology = ContractOntology()
        # 5 axiomas originais + 3 novos = 8
        assert len(ontology.axioms) >= 8

    def test_validate_new_predicates_in_formula(self):
        from contractfol.ontology import get_ontology

        ontology = get_ontology()

        is_valid, unknown = ontology.validate_formula_predicates(
            "Rescisao(contratante, contrato_001)"
        )
        assert is_valid

        is_valid, unknown = ontology.validate_formula_predicates(
            "ExclusaoResp(contratante, contrato_001)"
        )
        assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
