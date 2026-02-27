"""
Runner de Experimentos para Avaliação do ContractFOL.

Implementa o design experimental descrito na Seção 6.1 da dissertação:
- RQ1: ContractFOL detecta mais inconsistências que métodos baseados apenas em LLMs?
- RQ2: A taxa de falsos positivos do ContractFOL é menor?
- RQ3: O mecanismo de auto-refinamento melhora a precisão das traduções?
- RQ4: As explicações geradas são úteis e compreensíveis?

Métodos comparados:
1. ContractFOL (proposto)
2. GPT-4-CoT (Chain-of-Thought)
3. Claude-CoT
4. Gemini-CoT
5. Baseline Neural
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contractfol.evaluation.metrics import (
    DetectionMetrics,
    ExperimentResults,
    TimingMetrics,
    TranslationMetrics,
    calculate_metrics,
    compare_fol_formulas,
)
from contractfol.models import Clause, Contract, VerificationStatus
from contractfol.pipeline import ContractFOLPipeline, PipelineConfig


@dataclass
class ExperimentConfig:
    """Configuração do experimento."""

    # Dados
    contracts_dir: str = "data/contracts"
    clauses_file: str = "data/clauses/clausulas_anotadas.json"
    output_dir: str = "data/results"

    # LLM settings
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Provedor e modelo usados pelo ContractFOL
    llm_provider: str = "openai"   # "openai", "anthropic" ou "gemini"
    llm_model: str = "gpt-4"

    # Experimento
    methods: list[str] = field(
        default_factory=lambda: ["contractfol", "gpt4_cot", "claude_cot", "gemini_cot", "baseline"]
    )
    num_runs: int = 1  # Número de execuções para média
    verbose: bool = True


class BaselineMethod:
    """Método baseline baseado apenas em heurísticas textuais."""

    def __init__(self):
        self.conflict_keywords = {
            "obrigação_proibição": [
                ("obriga", "proíbe"),
                ("deverá", "é vedado"),
                ("deve", "não pode"),
                ("obriga-se", "é proibido"),
            ],
            "valores_inconsistentes": [
                ("R$", "R$"),  # Múltiplos valores podem indicar inconsistência
            ],
        }

    def detect_conflicts(self, clauses: list[Clause]) -> list[dict]:
        """Detecta conflitos usando heurísticas textuais simples."""
        conflicts = []

        for i, c1 in enumerate(clauses):
            for j, c2 in enumerate(clauses):
                if i >= j:
                    continue

                # Verificar padrões de conflito
                text1 = c1.text.lower()
                text2 = c2.text.lower()

                for conflict_type, patterns in self.conflict_keywords.items():
                    for p1, p2 in patterns:
                        if (p1 in text1 and p2 in text2) or (p2 in text1 and p1 in text2):
                            # Verificar se são sobre o mesmo assunto (heurística simples)
                            common_words = set(text1.split()) & set(text2.split())
                            if len(common_words) > 5:  # Alguma sobreposição
                                conflicts.append(
                                    {
                                        "clause_ids": [c1.id, c2.id],
                                        "conflict_type": conflict_type,
                                        "method": "baseline",
                                    }
                                )
                                break

        return conflicts


class LLMOnlyMethod:
    """Método baseado apenas em LLM com Chain-of-Thought."""

    def __init__(self, llm_client: Any, model: str = "gpt-4"):
        self.llm_client = llm_client
        self.model = model

    def detect_conflicts(self, clauses: list[Clause]) -> list[dict]:
        """Detecta conflitos usando apenas LLM."""
        if not self.llm_client:
            return []

        conflicts = []

        # Preparar texto das cláusulas
        clauses_text = "\n\n".join(
            f"[{c.id}] {c.text}" for c in clauses[:20]  # Limitar para contexto
        )

        prompt = f"""Analise as seguintes cláusulas contratuais e identifique TODOS os conflitos ou inconsistências entre elas.

Para cada conflito encontrado, responda no formato JSON:
{{"conflicts": [
  {{"clause_ids": ["id1", "id2"], "conflict_type": "tipo", "explanation": "explicação"}}
]}}

Cláusulas:
{clauses_text}

Use raciocínio passo a passo (Chain-of-Thought):
1. Primeiro, identifique as obrigações de cada parte
2. Identifique as proibições
3. Verifique se há obrigações contraditórias
4. Verifique se há valores ou prazos inconsistentes

Responda apenas com o JSON:"""

        try:
            if hasattr(self.llm_client, "chat"):
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2000,
                )
                result = response.choices[0].message.content
            elif hasattr(self.llm_client, "messages"):
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.content[0].text
            elif hasattr(self.llm_client, "generate_content"):
                # Google Gemini client
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 2000,
                    },
                )
                result = response.text
            else:
                return []

            # Parse JSON da resposta
            import re

            json_match = re.search(r"\{[^{}]*\"conflicts\"[^{}]*\[.*?\]\s*\}", result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                for c in data.get("conflicts", []):
                    c["method"] = f"llm_{self.model}"
                    conflicts.append(c)

        except Exception as e:
            print(f"Erro no LLM: {e}")

        return conflicts


class ExperimentRunner:
    """
    Executa experimentos comparativos conforme design da dissertação.
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: dict[str, ExperimentResults] = {}

        # Carregar ground truth
        self.ground_truth = self._load_ground_truth()

    def _load_ground_truth(self) -> dict:
        """Carrega dados anotados (ground truth)."""
        gt_path = Path(self.config.clauses_file)
        if gt_path.exists():
            with open(gt_path) as f:
                return json.load(f)
        return {"clauses": [], "conflict_pairs": []}

    def run_all(self) -> dict[str, ExperimentResults]:
        """
        Executa todos os métodos e retorna resultados comparativos.
        """
        print("=" * 60)
        print("EXPERIMENTO DE AVALIAÇÃO - ContractFOL")
        print("=" * 60)

        for method in self.config.methods:
            print(f"\n--- Executando: {method} ---")
            results = self._run_method(method)
            self.results[method] = results

        # Salvar resultados
        self._save_results()

        return self.results

    def _run_method(self, method: str) -> ExperimentResults:
        """Executa um método específico."""
        results = ExperimentResults(method_name=method)

        # Obter cláusulas do ground truth
        clauses = self._get_clauses_from_ground_truth()
        results.num_clauses = len(clauses)
        results.num_conflicts_ground_truth = len(
            self.ground_truth.get("conflict_pairs", [])
        )

        # Ground truth de conflitos
        gt_conflicts = [
            {"clause_ids": cp["clause_ids"], "conflict_type": cp["conflict_type"]}
            for cp in self.ground_truth.get("conflict_pairs", [])
        ]

        timing = TimingMetrics()
        all_predictions: list[dict] = []

        for run in range(self.config.num_runs):
            if self.config.verbose:
                print(f"  Run {run + 1}/{self.config.num_runs}")

            start_time = time.time()

            # Detectar conflitos
            if method == "contractfol":
                predictions, report = self._run_contractfol(clauses)
                # Extrair timing per-etapa do ValidationReport
                timing.extraction_times.append(report.extraction_time_ms)
                timing.classification_times.append(report.classification_time_ms)
                timing.translation_times.append(report.translation_time_ms)
                timing.verification_times.append(report.verification_time_ms)
                timing.total_times.append(report.total_time_ms)
            elif method == "gpt4_cot":
                predictions = self._run_llm_cot(clauses, "openai", "gpt-4")
                timing.total_times.append((time.time() - start_time) * 1000)
            elif method == "claude_cot":
                predictions = self._run_llm_cot(clauses, "anthropic", "claude-3-opus-20240229")
                timing.total_times.append((time.time() - start_time) * 1000)
            elif method == "gemini_cot":
                predictions = self._run_llm_cot(clauses, "gemini", "gemini-1.5-pro")
                timing.total_times.append((time.time() - start_time) * 1000)
            elif method == "baseline":
                predictions = self._run_baseline(clauses)
                timing.total_times.append((time.time() - start_time) * 1000)
            else:
                predictions = []
                timing.total_times.append(0.0)

            all_predictions.extend(predictions)

        # Usar predições de todas as runs para métricas (deduplicar pares)
        unique_predictions = {
            tuple(sorted(p.get("clause_ids", []))): p
            for p in all_predictions
        }
        final_predictions = list(unique_predictions.values())

        # Calcular métricas de detecção
        results.detection_metrics = calculate_metrics(final_predictions, gt_conflicts)
        results.timing_metrics = timing
        results.num_contracts = 1  # ground truth carregado como contrato único

        # Métricas de tradução (apenas para ContractFOL; clauses já foram atualizadas in-place)
        if method == "contractfol":
            results.translation_metrics = self._evaluate_translations(clauses)

        if self.config.verbose:
            print(f"  Precisão: {results.detection_metrics.precision:.2%}")
            print(f"  Recall: {results.detection_metrics.recall:.2%}")
            print(f"  F1-Score: {results.detection_metrics.f1_score:.2%}")
            print(f"  Tempo médio: {timing.mean_total_time:.1f}ms")

        return results

    def _get_clauses_from_ground_truth(self) -> list[Clause]:
        """Converte cláusulas do ground truth para objetos Clause."""
        clauses = []
        for item in self.ground_truth.get("clauses", []):
            clause = Clause(
                id=item["id"],
                text=item["text"],
                contract_id="test_contract",
            )
            clauses.append(clause)
        return clauses

    def _run_contractfol(self, clauses: list[Clause]) -> tuple[list[dict], Any]:
        """Executa pipeline ContractFOL.

        Returns:
            Tupla (predictions, report) onde report contém timing per-etapa.
        """
        # Selecionar API key de acordo com o provedor configurado
        provider = self.config.llm_provider
        if provider == "openai":
            api_key = self.config.openai_api_key
        elif provider == "anthropic":
            api_key = self.config.anthropic_api_key
        elif provider == "gemini":
            api_key = self.config.google_api_key
        else:
            api_key = self.config.openai_api_key

        config = PipelineConfig(
            llm_api_key=api_key,
            llm_provider=provider,
            llm_model=self.config.llm_model,
            verbose=False,
        )
        pipeline = ContractFOLPipeline(config=config)

        # Criar contrato com cláusulas (mesmos objetos — pipeline os modifica in-place)
        contract = Contract(id="test", title="Test Contract", clauses=clauses)
        report = pipeline.validate_contracts(contracts=[contract])

        # Converter conflitos para formato de comparação
        predictions = []
        for conflict in report.conflicts:
            predictions.append(
                {
                    "clause_ids": conflict.clause_ids,
                    "conflict_type": conflict.conflict_type.value,
                    "method": "contractfol",
                }
            )

        return predictions, report

    def _run_llm_cot(
        self, clauses: list[Clause], provider: str, model: str
    ) -> list[dict]:
        """Executa método LLM com Chain-of-Thought."""
        if provider == "openai":
            api_key = self.config.openai_api_key
        elif provider == "anthropic":
            api_key = self.config.anthropic_api_key
        elif provider == "gemini":
            api_key = self.config.google_api_key
        else:
            api_key = None

        if not api_key:
            print(f"  API key não configurada para {provider}")
            return []

        try:
            if provider == "openai":
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
            elif provider == "anthropic":
                from anthropic import Anthropic

                client = Anthropic(api_key=api_key)
            elif provider == "gemini":
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                client = genai.GenerativeModel(model)
            else:
                return []

            method = LLMOnlyMethod(client, model)
            return method.detect_conflicts(clauses)

        except Exception as e:
            print(f"  Erro ao inicializar {provider}: {e}")
            return []

    def _run_baseline(self, clauses: list[Clause]) -> list[dict]:
        """Executa método baseline."""
        baseline = BaselineMethod()
        return baseline.detect_conflicts(clauses)

    def _evaluate_translations(self, clauses: list[Clause]) -> TranslationMetrics:
        """Avalia qualidade das traduções NL-FOL."""
        metrics = TranslationMetrics()
        metrics.total_clauses = len(clauses)

        gt_clauses = {c["id"]: c for c in self.ground_truth.get("clauses", [])}

        for clause in clauses:
            if clause.id in gt_clauses and clause.fol_formula:
                gold_fol = gt_clauses[clause.id].get("fol_gold", "")
                if gold_fol:
                    is_correct, similarity = compare_fol_formulas(
                        clause.fol_formula, gold_fol
                    )
                    if is_correct:
                        metrics.correct_translations += 1
                        metrics.semantically_correct += 1

                if clause.fol_parsed:
                    metrics.syntactically_valid += 1

                if clause.fol_translation_attempts == 1:
                    metrics.correct_first_attempt += 1
                elif clause.fol_translation_attempts > 1:
                    metrics.correct_after_refinement += 1

        return metrics

    def _save_results(self):
        """Salva resultados em JSON, CSV e LaTeX."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        results_dict = {
            method: results.to_dict() for method, results in self.results.items()
        }
        results_dict["comparison"] = self._generate_comparison()

        # JSON completo
        json_file = output_dir / f"experiment_results_{timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        print(f"\nResultados JSON salvos em: {json_file}")

        # CSV de comparação
        csv_file = output_dir / f"comparison_{timestamp}.csv"
        self._export_csv(csv_file)
        print(f"Resultados CSV salvos em: {csv_file}")

        # LaTeX para dissertação
        tex_file = output_dir / f"comparison_{timestamp}.tex"
        self._export_latex(tex_file)
        print(f"Tabela LaTeX salva em: {tex_file}")

    def _export_csv(self, path: Path):
        """Exporta tabela comparativa em CSV."""
        import csv

        rows = []
        for method, results in self.results.items():
            dm = results.detection_metrics
            tm = results.timing_metrics
            row = {
                "metodo": method,
                "precisao": f"{dm.precision:.4f}",
                "recall": f"{dm.recall:.4f}",
                "f1_score": f"{dm.f1_score:.4f}",
                "acuracia": f"{dm.accuracy:.4f}",
                "verdadeiros_positivos": dm.true_positives,
                "falsos_positivos": dm.false_positives,
                "falsos_negativos": dm.false_negatives,
                "tempo_total_ms": f"{tm.mean_total_time:.1f}",
                "tempo_extracao_ms": f"{tm.mean_extraction_time:.1f}",
                "tempo_classificacao_ms": f"{tm.mean_classification_time:.1f}",
                "tempo_traducao_ms": f"{tm.mean_translation_time:.1f}",
                "tempo_verificacao_ms": f"{tm.mean_verification_time:.1f}",
                "num_clausulas": results.num_clauses,
                "gt_conflitos": results.num_conflicts_ground_truth,
            }
            rows.append(row)

        if rows:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    def _export_latex(self, path: Path):
        """Exporta tabela comparativa em LaTeX pronta para dissertação."""
        method_labels = {
            "contractfol": "ContractFOL (proposto)",
            "gpt4_cot": "GPT-4 + CoT",
            "claude_cot": "Claude + CoT",
            "gemini_cot": "Gemini + CoT",
            "baseline": "Baseline Heurístico",
        }

        lines = [
            "% Tabela gerada automaticamente pelo ExperimentRunner",
            "% Seção 6.3 da dissertação — Resultados Comparativos",
            r"\begin{table}[ht]",
            r"  \centering",
            r"  \caption{Resultados comparativos dos métodos de detecção de inconsistências contratuais}",
            r"  \label{tab:resultados-comparativos}",
            r"  \begin{tabular}{lrrrrr}",
            r"    \toprule",
            r"    \textbf{Método} & \textbf{Precisão} & \textbf{Recall} & \textbf{F1-Score} & \textbf{Tempo (ms)} \\",
            r"    \midrule",
        ]

        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1].detection_metrics.f1_score,
            reverse=True,
        )

        for method, results in sorted_results:
            dm = results.detection_metrics
            tm = results.timing_metrics
            label = method_labels.get(method, method)
            # Negrito para o método proposto
            if method == "contractfol":
                label = r"\textbf{" + label + "}"
            lines.append(
                f"    {label} & {dm.precision:.2%} & {dm.recall:.2%} & "
                f"{dm.f1_score:.2%} & {tm.mean_total_time:.0f}$\\pm${tm.std_total_time:.0f} \\\\"
            )

        lines += [
            r"    \bottomrule",
            r"  \end{tabular}",
            r"\end{table}",
        ]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _generate_comparison(self) -> dict:
        """Gera tabela comparativa dos métodos."""
        comparison = []

        for method, results in self.results.items():
            comparison.append(
                {
                    "method": method,
                    "precision": results.detection_metrics.precision,
                    "recall": results.detection_metrics.recall,
                    "f1_score": results.detection_metrics.f1_score,
                    "mean_time_ms": results.timing_metrics.mean_total_time,
                }
            )

        # Ordenar por F1-Score
        comparison.sort(key=lambda x: x["f1_score"], reverse=True)

        return comparison

    def print_comparison_table(self):
        """Imprime tabela comparativa formatada."""
        print("\n" + "=" * 70)
        print("RESULTADOS COMPARATIVOS")
        print("=" * 70)
        print(f"{'Método':<20} {'Precisão':>10} {'Recall':>10} {'F1-Score':>10} {'Tempo(ms)':>12}")
        print("-" * 70)

        for method, results in sorted(
            self.results.items(),
            key=lambda x: x[1].detection_metrics.f1_score,
            reverse=True,
        ):
            dm = results.detection_metrics
            tm = results.timing_metrics
            print(
                f"{method:<20} {dm.precision:>10.2%} {dm.recall:>10.2%} "
                f"{dm.f1_score:>10.2%} {tm.mean_total_time:>10.1f}±{tm.std_total_time:.1f}"
            )

        print("=" * 70)


def run_experiment(
    openai_key: str | None = None,
    anthropic_key: str | None = None,
    google_key: str | None = None,
    verbose: bool = True,
) -> dict:
    """
    Função utilitária para executar experimento completo.
    """
    config = ExperimentConfig(
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        google_api_key=google_key,
        verbose=verbose,
    )
    runner = ExperimentRunner(config)
    results = runner.run_all()
    runner.print_comparison_table()
    return results
