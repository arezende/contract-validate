"""
Métricas de Avaliação para o ContractFOL.

Implementa as métricas utilizadas na avaliação experimental conforme
Seção 6.3 da dissertação:
- Precisão, Recall e F1-Score para detecção de inconsistências
- Taxa de correção de tradução NL-FOL
- Métricas de tempo de processamento
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectionMetrics:
    """Métricas de detecção de inconsistências."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precisão: TP / (TP + FP)"""
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def f1_score(self) -> float:
        """F1-Score: 2 * (P * R) / (P + R)"""
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @property
    def accuracy(self) -> float:
        """Acurácia: (TP + TN) / Total"""
        total = (
            self.true_positives
            + self.true_negatives
            + self.false_positives
            + self.false_negatives
        )
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total

    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy": self.accuracy,
        }


@dataclass
class TranslationMetrics:
    """Métricas de tradução NL-FOL."""

    total_clauses: int = 0
    correct_translations: int = 0
    syntactically_valid: int = 0
    semantically_correct: int = 0

    # Métricas por número de tentativas de refinamento
    correct_first_attempt: int = 0
    correct_after_refinement: int = 0

    @property
    def syntax_accuracy(self) -> float:
        """Taxa de correção sintática."""
        if self.total_clauses == 0:
            return 0.0
        return self.syntactically_valid / self.total_clauses

    @property
    def semantic_accuracy(self) -> float:
        """Taxa de correção semântica."""
        if self.total_clauses == 0:
            return 0.0
        return self.semantically_correct / self.total_clauses

    @property
    def refinement_improvement(self) -> float:
        """Melhoria obtida com refinamento."""
        if self.total_clauses == 0:
            return 0.0
        without_refinement = self.correct_first_attempt / self.total_clauses
        with_refinement = (
            self.correct_first_attempt + self.correct_after_refinement
        ) / self.total_clauses
        return with_refinement - without_refinement

    def to_dict(self) -> dict:
        return {
            "total_clauses": self.total_clauses,
            "correct_translations": self.correct_translations,
            "syntactically_valid": self.syntactically_valid,
            "semantically_correct": self.semantically_correct,
            "syntax_accuracy": self.syntax_accuracy,
            "semantic_accuracy": self.semantic_accuracy,
            "correct_first_attempt": self.correct_first_attempt,
            "correct_after_refinement": self.correct_after_refinement,
            "refinement_improvement": self.refinement_improvement,
        }


@dataclass
class TimingMetrics:
    """Métricas de tempo de processamento."""

    extraction_times: list[float] = field(default_factory=list)
    classification_times: list[float] = field(default_factory=list)
    translation_times: list[float] = field(default_factory=list)
    verification_times: list[float] = field(default_factory=list)
    total_times: list[float] = field(default_factory=list)

    def _mean(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _std(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = self._mean(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5

    @property
    def mean_extraction_time(self) -> float:
        return self._mean(self.extraction_times)

    @property
    def mean_classification_time(self) -> float:
        return self._mean(self.classification_times)

    @property
    def mean_translation_time(self) -> float:
        return self._mean(self.translation_times)

    @property
    def mean_verification_time(self) -> float:
        return self._mean(self.verification_times)

    @property
    def mean_total_time(self) -> float:
        return self._mean(self.total_times)

    @property
    def std_total_time(self) -> float:
        return self._std(self.total_times)

    def to_dict(self) -> dict:
        return {
            "extraction": {
                "mean_ms": self.mean_extraction_time,
                "std_ms": self._std(self.extraction_times),
            },
            "classification": {
                "mean_ms": self.mean_classification_time,
                "std_ms": self._std(self.classification_times),
            },
            "translation": {
                "mean_ms": self.mean_translation_time,
                "std_ms": self._std(self.translation_times),
            },
            "verification": {
                "mean_ms": self.mean_verification_time,
                "std_ms": self._std(self.verification_times),
            },
            "total": {
                "mean_ms": self.mean_total_time,
                "std_ms": self.std_total_time,
            },
        }


@dataclass
class ExperimentResults:
    """Resultados completos de um experimento."""

    method_name: str
    detection_metrics: DetectionMetrics = field(default_factory=DetectionMetrics)
    translation_metrics: TranslationMetrics = field(default_factory=TranslationMetrics)
    timing_metrics: TimingMetrics = field(default_factory=TimingMetrics)

    # Metadados
    num_contracts: int = 0
    num_clauses: int = 0
    num_conflicts_ground_truth: int = 0

    def to_dict(self) -> dict:
        return {
            "method": self.method_name,
            "detection": self.detection_metrics.to_dict(),
            "translation": self.translation_metrics.to_dict(),
            "timing": self.timing_metrics.to_dict(),
            "metadata": {
                "num_contracts": self.num_contracts,
                "num_clauses": self.num_clauses,
                "num_conflicts_ground_truth": self.num_conflicts_ground_truth,
            },
        }


def calculate_metrics(
    predictions: list[dict],
    ground_truth: list[dict],
) -> DetectionMetrics:
    """
    Calcula métricas de detecção comparando predições com ground truth.

    Args:
        predictions: Lista de conflitos detectados
            [{"clause_ids": [...], "conflict_type": "..."}]
        ground_truth: Lista de conflitos reais
            [{"clause_ids": [...], "conflict_type": "..."}]

    Returns:
        DetectionMetrics com TP, FP, FN calculados
    """
    metrics = DetectionMetrics()

    # Criar conjuntos de pares de cláusulas para comparação
    pred_pairs = set()
    for p in predictions:
        clause_ids = tuple(sorted(p.get("clause_ids", [])))
        if len(clause_ids) >= 2:
            pred_pairs.add(clause_ids)

    gt_pairs = set()
    for g in ground_truth:
        clause_ids = tuple(sorted(g.get("clause_ids", [])))
        if len(clause_ids) >= 2:
            gt_pairs.add(clause_ids)

    # Calcular métricas
    metrics.true_positives = len(pred_pairs & gt_pairs)
    metrics.false_positives = len(pred_pairs - gt_pairs)
    metrics.false_negatives = len(gt_pairs - pred_pairs)

    return metrics


def compute_wilson_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Calcula intervalo de confiança de Wilson para proporções.

    Usado para estimar IC do F1-Score considerando TP como "sucessos"
    e (TP + FP + FN) como "total de julgamentos".

    Args:
        successes: Número de acertos (ex: TP)
        total: Total de tentativas (ex: TP + FP + FN)
        confidence: Nível de confiança (padrão: 0.95)

    Returns:
        (lower, upper) — limites inferior e superior do IC
    """
    import math

    if total == 0:
        return 0.0, 0.0

    # z-score para o nível de confiança solicitado (aproximação normal)
    z_table = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
    z = z_table.get(confidence, 1.960)

    p_hat = successes / total
    denominator = 1 + (z ** 2) / total
    centre = (p_hat + (z ** 2) / (2 * total)) / denominator
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / total + (z ** 2) / (4 * total ** 2))) / denominator

    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return lower, upper


def compute_f1_confidence_interval(
    metrics: "DetectionMetrics",
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Estima intervalo de confiança do F1-Score usando propagação via Wilson.

    Estratégia: calcula IC de precisão e recall separadamente (Wilson score)
    e propaga via min/max do F1 nos extremos do IC.

    Args:
        metrics: DetectionMetrics já calculadas
        confidence: Nível de confiança

    Returns:
        (f1_lower, f1_upper)
    """
    tp = metrics.true_positives
    fp = metrics.false_positives
    fn = metrics.false_negatives

    # IC da Precisão: TP / (TP + FP)
    p_total = tp + fp
    p_lower, p_upper = compute_wilson_interval(tp, p_total, confidence) if p_total > 0 else (0.0, 1.0)

    # IC do Recall: TP / (TP + FN)
    r_total = tp + fn
    r_lower, r_upper = compute_wilson_interval(tp, r_total, confidence) if r_total > 0 else (0.0, 1.0)

    def f1(p: float, r: float) -> float:
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    f1_lower = f1(p_lower, r_lower)
    f1_upper = f1(p_upper, r_upper)
    return f1_lower, f1_upper


def compare_fol_formulas(predicted: str, gold: str) -> tuple[bool, float]:
    """
    Compara uma fórmula FOL predita com a fórmula gold standard.

    Retorna:
        (is_correct, similarity_score)
    """
    # Normalizar fórmulas
    def normalize(f: str) -> str:
        f = f.lower().strip()
        # Remover espaços extras
        f = " ".join(f.split())
        # Normalizar operadores
        f = f.replace("∧", " and ")
        f = f.replace("∨", " or ")
        f = f.replace("→", " -> ")
        f = f.replace("¬", " not ")
        f = f.replace("∀", "forall ")
        f = f.replace("∃", "exists ")
        return f

    pred_norm = normalize(predicted)
    gold_norm = normalize(gold)

    # Verificar igualdade exata
    if pred_norm == gold_norm:
        return True, 1.0

    # Calcular similaridade aproximada (Jaccard nos tokens)
    pred_tokens = set(pred_norm.replace("(", " ").replace(")", " ").replace(",", " ").split())
    gold_tokens = set(gold_norm.replace("(", " ").replace(")", " ").replace(",", " ").split())

    if not pred_tokens or not gold_tokens:
        return False, 0.0

    intersection = len(pred_tokens & gold_tokens)
    union = len(pred_tokens | gold_tokens)
    similarity = intersection / union if union > 0 else 0.0

    # Considerar correto se similaridade > 0.8
    return similarity > 0.8, similarity
