"""Location alignment metric via connected-component graph (CLAUSE paper)."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass

import networkx as nx


@dataclass
class LocationMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    rouge1: float       # mean over TP pairs
    rouge2: float
    rougeL: float
    meteor: float
    bertscore_f1: float


def _safe_div(num: float, den: float) -> float:
    return 0.0 if den == 0 else num / den


_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_sentences(text: str) -> frozenset[str]:
    """Lowercase, strip punctuation, split on sentence-ending chars, discard empty."""
    sentences = re.split(r"[.?!\n]", text)
    result: set[str] = set()
    for sent in sentences:
        sent = sent.lower().translate(_PUNCT_TABLE).strip()
        if sent:
            result.add(sent)
    return frozenset(result)


def _spans_overlap(a: str, b: str) -> bool:
    return bool(_normalize_sentences(a) & _normalize_sentences(b))


def location_alignment(
    gt_spans: list[str | None],
    pred_spans: list[str | None],
) -> LocationMetrics:
    """
    gt_spans[i] and pred_spans[i] correspond to the same instance.
    None = absent (not predicted / no GT annotation).
    """
    # Build per-instance node labels
    # Nodes are tuples: ("gt", i) or ("pred", i)
    G = nx.Graph()

    valid_gt: list[tuple[int, str]] = []    # (i, span) — non-None GT spans
    valid_pred: list[tuple[int, str]] = []  # (i, span) — non-None pred spans

    for i, (gt, pred) in enumerate(zip(gt_spans, pred_spans)):
        if gt is not None:
            G.add_node(("gt", i))
            valid_gt.append((i, gt))
        if pred is not None:
            G.add_node(("pred", i))
            valid_pred.append((i, pred))

    # Add edges where normalized sentence sets overlap
    for gi, gt_text in valid_gt:
        for pi, pred_text in valid_pred:
            if _spans_overlap(gt_text, pred_text):
                G.add_edge(("gt", gi), ("pred", pi))

    # Classify connected components
    tp_pairs: list[tuple[str, str]] = []
    fp_count = 0
    fn_count = 0

    for component in nx.connected_components(G):
        has_gt = any(node[0] == "gt" for node in component)
        has_pred = any(node[0] == "pred" for node in component)

        if has_gt and has_pred:
            # True positive component — collect one representative pair
            gt_nodes = [node for node in component if node[0] == "gt"]
            pred_nodes = [node for node in component if node[0] == "pred"]
            # Pair up: first GT node's text with first pred node's text
            gi = gt_nodes[0][1]
            pi = pred_nodes[0][1]
            tp_pairs.append((gt_spans[gi], pred_spans[pi]))  # type: ignore[arg-type]
        elif has_gt and not has_pred:
            fn_count += 1
        elif has_pred and not has_gt:
            fp_count += 1

    tp = len(tp_pairs)
    precision = _safe_div(tp, tp + fp_count)
    recall = _safe_div(tp, tp + fn_count)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    # Compute text-similarity metrics over TP pairs
    rouge1 = rouge2 = rougeL = meteor = bertscore_f1 = 0.0

    if tp_pairs:
        rouge1, rouge2, rougeL = _compute_rouge(tp_pairs)
        meteor = _compute_meteor(tp_pairs)
        bertscore_f1 = _compute_bertscore(tp_pairs)

    return LocationMetrics(
        tp=tp,
        fp=fp_count,
        fn=fn_count,
        precision=precision,
        recall=recall,
        f1=f1,
        rouge1=rouge1,
        rouge2=rouge2,
        rougeL=rougeL,
        meteor=meteor,
        bertscore_f1=bertscore_f1,
    )


def _compute_rouge(pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    from rouge_score import rouge_scorer  # type: ignore

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    r1_total = r2_total = rL_total = 0.0
    for gt_text, pred_text in pairs:
        scores = scorer.score(gt_text, pred_text)
        r1_total += scores["rouge1"].fmeasure
        r2_total += scores["rouge2"].fmeasure
        rL_total += scores["rougeL"].fmeasure

    n = len(pairs)
    return r1_total / n, r2_total / n, rL_total / n


_nltk_ready = False


def _ensure_nltk() -> None:
    global _nltk_ready
    if _nltk_ready:
        return
    import nltk  # type: ignore

    for resource in ("wordnet", "punkt", "punkt_tab"):
        try:
            nltk.download(resource, quiet=True)
        except Exception:
            pass
    _nltk_ready = True


def _compute_meteor(pairs: list[tuple[str, str]]) -> float:
    _ensure_nltk()
    import nltk  # type: ignore
    from nltk.translate.meteor_score import meteor_score  # type: ignore

    total = 0.0
    for gt_text, pred_text in pairs:
        ref_tokens = nltk.word_tokenize(gt_text.lower())
        hyp_tokens = nltk.word_tokenize(pred_text.lower())
        total += meteor_score([ref_tokens], hyp_tokens)

    return total / len(pairs)


def _compute_bertscore(pairs: list[tuple[str, str]]) -> float:
    from bert_score import score as bs_score  # type: ignore

    cands = [p for _, p in pairs]
    refs = [g for g, _ in pairs]

    P, R, F1 = bs_score(
        cands,
        refs,
        model_type="microsoft/deberta-xlarge-mnli",
        lang="en",
        verbose=False,
    )
    return float(F1.mean().item())
