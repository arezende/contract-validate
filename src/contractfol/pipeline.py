"""
Pipeline Principal do ContractFOL.

Integra todos os componentes do sistema para validação automatizada
de contratos inter-institucionais:

1. Extração de cláusulas
2. Classificação deôntica
3. Tradução NL-FOL
4. Verificação formal (Z3)
5. Geração de explicações

Conforme a arquitetura descrita na Seção 5.1 da dissertação.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contractfol.classifiers import DeonticClassifier
from contractfol.extractors import ClauseExtractor
from contractfol.generators import ExplanationGenerator
from contractfol.models import Clause, Contract, ValidationReport, VerificationStatus
from contractfol.ontology import ContractOntology, get_ontology
from contractfol.translators import NLFOLTranslator
from contractfol.utils import DocumentLoader
from contractfol.verifiers import Z3Verifier


@dataclass
class PipelineConfig:
    """Configuração do pipeline."""

    # LLM settings
    llm_provider: str = "openai"  # "openai" ou "anthropic"
    llm_model: str = "gpt-4"
    llm_api_key: str | None = None

    # Translation settings
    max_refinement_attempts: int = 3
    use_heuristics: bool = True

    # Verification settings
    z3_timeout_ms: int = 30000

    # Output settings
    generate_report: bool = True
    verbose: bool = False


class ContractFOLPipeline:
    """
    Pipeline principal para validação de contratos.

    Orquestra todos os componentes do sistema ContractFOL para processar
    contratos e detectar inconsistências.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        llm_client: Any | None = None,
        ontology: ContractOntology | None = None,
    ):
        """
        Inicializa o pipeline.

        Args:
            config: Configurações do pipeline
            llm_client: Cliente LLM pré-configurado (opcional)
            ontology: Ontologia de domínio (opcional)
        """
        self.config = config or PipelineConfig()
        self.ontology = ontology or get_ontology()

        # Inicializar cliente LLM se não fornecido
        self.llm_client = llm_client or self._init_llm_client()

        # Inicializar componentes
        self.extractor = ClauseExtractor()
        self.classifier = DeonticClassifier(
            llm_client=self.llm_client,
            model=self.config.llm_model,
            use_heuristics=self.config.use_heuristics,
        )
        self.translator = NLFOLTranslator(
            llm_client=self.llm_client,
            model=self.config.llm_model,
            ontology=self.ontology,
            max_refinement_attempts=self.config.max_refinement_attempts,
        )
        self.verifier = Z3Verifier(
            ontology=self.ontology,
            timeout_ms=self.config.z3_timeout_ms,
        )
        self.explanation_generator = ExplanationGenerator(
            llm_client=self.llm_client,
            model=self.config.llm_model,
        )
        self.document_loader = DocumentLoader()

    def _init_llm_client(self) -> Any | None:
        """Inicializa cliente LLM baseado na configuração."""
        if not self.config.llm_api_key:
            # Tentar obter da variável de ambiente
            import os

            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                if self.config.verbose:
                    print("Aviso: Nenhuma API key configurada. Usando modo heurístico.")
                return None
            self.config.llm_api_key = api_key

        try:
            if self.config.llm_provider == "openai":
                from openai import OpenAI

                return OpenAI(api_key=self.config.llm_api_key)
            elif self.config.llm_provider == "anthropic":
                from anthropic import Anthropic

                return Anthropic(api_key=self.config.llm_api_key)
        except ImportError as e:
            if self.config.verbose:
                print(f"Aviso: Biblioteca LLM não instalada: {e}")
            return None
        except Exception as e:
            if self.config.verbose:
                print(f"Aviso: Erro ao inicializar LLM: {e}")
            return None

        return None

    def validate_contracts(
        self,
        contracts: list[Contract] | None = None,
        contract_texts: list[str] | None = None,
        file_paths: list[str | Path] | None = None,
    ) -> ValidationReport:
        """
        Valida um conjunto de contratos.

        Pode receber contratos já parseados, textos brutos ou caminhos de arquivos.

        Args:
            contracts: Lista de objetos Contract
            contract_texts: Lista de textos de contratos
            file_paths: Lista de caminhos para arquivos de contrato

        Returns:
            ValidationReport com resultados da validação
        """
        start_time = time.time()

        # Preparar contratos
        if contracts is None:
            contracts = []

        if file_paths:
            for path in file_paths:
                text = self.document_loader.load(path)
                if text:
                    contract = self.extractor.extract_from_text(text)
                    contracts.append(contract)

        if contract_texts:
            for i, text in enumerate(contract_texts):
                contract = self.extractor.extract_from_text(text, f"contract_{i + 1}")
                contracts.append(contract)

        if not contracts:
            return ValidationReport(contract_ids=[], status=VerificationStatus.UNKNOWN)

        # Criar relatório
        report = ValidationReport(
            contract_ids=[c.id for c in contracts],
        )

        # Coletar todas as cláusulas
        all_clauses: list[Clause] = []

        # Etapa 1: Extração (já feita acima ou nos contratos fornecidos)
        extraction_start = time.time()
        for contract in contracts:
            if not contract.clauses:
                # Se contrato não tem cláusulas, extrair do texto armazenado
                # (simplificação - em produção haveria texto armazenado)
                pass
            all_clauses.extend(contract.clauses)

        report.total_clauses = len(all_clauses)
        report.extraction_time_ms = (time.time() - extraction_start) * 1000

        if self.config.verbose:
            print(f"Extraídas {len(all_clauses)} cláusulas de {len(contracts)} contratos")

        # Etapa 2: Classificação deôntica
        classification_start = time.time()
        for clause in all_clauses:
            self.classifier.update_clause(clause)

        report.classification_time_ms = (time.time() - classification_start) * 1000

        if self.config.verbose:
            print(f"Classificação concluída em {report.classification_time_ms:.1f}ms")

        # Etapa 3: Tradução NL-FOL
        translation_start = time.time()
        translated_count = 0

        for clause in all_clauses:
            self.translator.update_clause_with_fol(clause)
            if clause.fol_parsed:
                translated_count += 1

        report.clauses_translated = translated_count
        report.translation_success_rate = (
            translated_count / len(all_clauses) if all_clauses else 0
        )
        report.translation_time_ms = (time.time() - translation_start) * 1000

        if self.config.verbose:
            print(
                f"Tradução: {translated_count}/{len(all_clauses)} "
                f"({report.translation_success_rate:.1%}) em {report.translation_time_ms:.1f}ms"
            )

        # Etapa 4: Verificação formal
        verification_start = time.time()
        verification_result = self.verifier.verify_consistency(all_clauses)

        report.status = verification_result.status
        report.conflicts = verification_result.conflicts
        report.verification_time_ms = verification_result.verification_time_ms

        if self.config.verbose:
            print(
                f"Verificação: {report.status.value} "
                f"({len(report.conflicts)} conflitos) em {report.verification_time_ms:.1f}ms"
            )

        # Etapa 5: Gerar explicações para conflitos
        for conflict in report.conflicts:
            explanation = self.explanation_generator.generate_explanation(
                conflict, all_clauses
            )
            conflict.explanation = explanation.detailed_explanation
            if explanation.suggestions:
                conflict.suggestion = explanation.suggestions[0]

        # Tempo total
        report.total_time_ms = (time.time() - start_time) * 1000

        return report

    def validate_text(self, text: str) -> ValidationReport:
        """
        Atalho para validar um único texto de contrato.
        """
        return self.validate_contracts(contract_texts=[text])

    def validate_file(self, file_path: str | Path) -> ValidationReport:
        """
        Atalho para validar um único arquivo de contrato.
        """
        return self.validate_contracts(file_paths=[file_path])

    def get_report_text(
        self, report: ValidationReport, clauses: list[Clause] | None = None
    ) -> str:
        """
        Gera relatório em texto formatado.

        Args:
            report: Resultado da validação
            clauses: Lista de cláusulas (opcional, para detalhes)

        Returns:
            Texto formatado do relatório
        """
        return self.explanation_generator.generate_report(report, clauses or [])

    def process_single_clause(self, clause_text: str) -> dict:
        """
        Processa uma única cláusula (para debugging/demonstração).

        Returns:
            Dicionário com resultados de cada etapa
        """
        from contractfol.models import Clause

        clause = Clause(
            id="test_clause",
            text=clause_text,
            contract_id="test_contract",
        )

        # Classificar
        self.classifier.update_clause(clause)

        # Traduzir
        translation_result = self.translator.translate(clause)

        return {
            "text": clause_text,
            "modality": clause.modality.value if clause.modality else None,
            "modality_confidence": clause.modality_confidence,
            "fol_formula": translation_result.fol_formula,
            "fol_valid": translation_result.is_valid,
            "fol_errors": translation_result.validation_errors,
            "translation_attempts": translation_result.attempts,
            "predicates_used": translation_result.predicates_used,
        }


def create_pipeline(
    api_key: str | None = None,
    provider: str = "openai",
    model: str = "gpt-4",
    verbose: bool = False,
) -> ContractFOLPipeline:
    """
    Função utilitária para criar pipeline configurado.

    Args:
        api_key: API key do provedor LLM
        provider: "openai" ou "anthropic"
        model: Nome do modelo
        verbose: Se deve imprimir logs

    Returns:
        Pipeline configurado
    """
    config = PipelineConfig(
        llm_provider=provider,
        llm_model=model,
        llm_api_key=api_key,
        verbose=verbose,
    )
    return ContractFOLPipeline(config=config)
