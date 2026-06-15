"""
Análise estrutural por tipo de perturbação do dataset CLAUSE.

Examina o que muda entre original_text e changed_text em cada categoria,
cobertura de campos, padrões de localização e exemplos anotados.

Uso:
    python scripts/analyze_perturb_types.py --data data/raw/clause/datasets/
    python scripts/analyze_perturb_types.py --data data/raw/clause/datasets/ --samples 3
"""

from __future__ import annotations

import argparse
import logging
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))

from contractfol.corpus.ingest import load_instances
from contractfol.corpus.schema import DiscrepancyInstance

SEP = "─" * 72
PERTURB_TYPES = [
    "ambiguity",
    "inconsistency",
    "misaligned_terminology",
    "omission",
    "structural_flaw",
]


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


def _pct(n: int, total: int) -> str:
    return f"{n:>6,}  ({100 * n / total:5.1f}%)" if total else f"{n:>6,}  (  n/a)"


def _stats_str(values: list[int]) -> str:
    if not values:
        return "n/a"
    s = sorted(values)
    n = len(s)
    return (
        f"min={s[0]:,}  median={s[n//2]:,}  "
        f"p90={s[int(n*0.9)]:,}  max={s[-1]:,}"
    )


def _diff_summary(original: str, changed: str) -> str:
    """Return a short textual description of the diff."""
    words_o = set(original.split())
    words_c = set(changed.split())
    removed = words_o - words_c
    added = words_c - words_o
    parts: list[str] = []
    if removed:
        sample = list(removed)[:6]
        parts.append(f"  - removed: {' '.join(sample)}")
    if added:
        sample = list(added)[:6]
        parts.append(f"  + added:   {' '.join(sample)}")
    return "\n".join(parts) if parts else "  (no lexical diff)"


def _truncate(s: str, width: int = 200) -> str:
    return s[:width] + "…" if len(s) > width else s


# ──────────────────────────────────────────────────────────────────────────────


def analyze_type(
    pt: str,
    instances: list[DiscrepancyInstance],
    n_samples: int,
) -> None:
    section(f"TIPO: {pt.upper()}")

    group = [i for i in instances if i.perturb_type == pt]
    N = len(group)
    print(f"  Total: {N:,}")

    # in_text vs legal split
    by_dim = Counter(i.dimension for i in group)
    it, lg = by_dim.get("in_text", 0), by_dim.get("legal", 0)
    print(f"  Dimensão:  in_text={it:,} ({100*it/N:.1f}%)  "
          f"legal={lg:,} ({100*lg/N:.1f}%)")

    # CUAD vs NLI
    by_ds = Counter(i.source_dataset for i in group)
    print(f"  Dataset:   cuad={by_ds.get('cuad',0):,}  "
          f"nli={by_ds.get('nli',0):,}")

    # Text lengths
    orig_len = [len(i.original_text) for i in group]
    chng_len = [len(i.changed_text) for i in group]
    diff_len = [abs(len(i.changed_text) - len(i.original_text)) for i in group]
    print(f"\n  original_text  : {_stats_str(orig_len)}")
    print(f"  changed_text   : {_stats_str(chng_len)}")
    print(f"  |Δ| chars      : {_stats_str(diff_len)}")

    # Field coverage for this type
    fields = [
        "location", "contradicted_location", "contradicted_text",
        "contradicted_law", "law_citation", "scraped_snippet_1",
    ]
    print(f"\n  Cobertura de campos (% preenchido):")
    for f in fields:
        filled = sum(1 for i in group if getattr(i, f) is not None)
        print(f"    {f:<28} {100*filled/N:5.1f}%")

    # Location patterns
    locs = [i.location for i in group if i.location]
    if locs:
        sample_locs = Counter(locs).most_common(5)
        print(f"\n  Padrões de location (top 5):")
        for loc, cnt in sample_locs:
            print(f"    {repr(loc[:50]):<54} : {cnt:>4}")

    # Explanation length (proxy for complexity)
    expl_len = [len(i.explanation) for i in group]
    print(f"\n  explanation    : {_stats_str(expl_len)}")

    # Identical text flag
    identical = sum(
        1 for i in group
        if i.original_text.strip() == i.changed_text.strip()
    )
    empty_changed = sum(1 for i in group if not i.changed_text.strip())
    if identical or empty_changed:
        print(f"\n  ALERTAS: {identical} texto idêntico, "
              f"{empty_changed} changed_text vazio")

    # Representative samples — one in_text, one legal
    print(f"\n  {'─'*66}")
    print(f"  AMOSTRAS ({n_samples} por dimensão):")
    random.seed(42)
    for dim in ("in_text", "legal"):
        sub = [i for i in group if i.dimension == dim and i.changed_text.strip()]
        samples = random.sample(sub, min(n_samples, len(sub)))
        for inst in samples:
            print(f"\n  [{dim}]  {inst.instance_id}")
            print(f"  Dataset  : {inst.source_dataset}  |  "
                  f"Location : {inst.location}")
            print(f"\n  ORIGINAL : {_truncate(inst.original_text, 300)}")
            print(f"\n  CHANGED  : {_truncate(inst.changed_text, 300)}")
            print(f"\n  DIFF (léxico):")
            print(_diff_summary(inst.original_text, inst.changed_text))
            print(f"\n  EXPLANATION: {_truncate(inst.explanation, 250)}")
            if inst.law_citation:
                print(f"  LAW      : {inst.law_citation}")
            if inst.scraped_snippet_1:
                print(f"  SNIPPET  : {_truncate(inst.scraped_snippet_1, 150)}")
            print(f"  {'·'*64}")


# ──────────────────────────────────────────────────────────────────────────────


def cross_type_summary(instances: list[DiscrepancyInstance]) -> None:
    section("RESUMO COMPARATIVO ENTRE TIPOS")

    print(f"  {'Tipo':<28}  {'N':>6}  {'in_text':>8}  {'legal':>8}  "
          f"{'Δ_med':>7}  {'expl_med':>9}  {'loc%':>6}")
    print("  " + "─" * 72)
    for pt in PERTURB_TYPES:
        group = [i for i in instances if i.perturb_type == pt]
        N = len(group)
        it = sum(1 for i in group if i.dimension == "in_text")
        lg = N - it
        diffs = sorted(
            abs(len(i.changed_text) - len(i.original_text)) for i in group
        )
        diff_med = diffs[N // 2] if diffs else 0
        expls = sorted(len(i.explanation) for i in group)
        expl_med = expls[N // 2] if expls else 0
        loc_pct = 100 * sum(1 for i in group if i.location) / N if N else 0
        print(
            f"  {pt:<28}  {N:>6,}  {it:>8,}  {lg:>8,}  "
            f"{diff_med:>7}  {expl_med:>9}  {loc_pct:>5.1f}%"
        )

    # Special: changed_text == original_text (per type)
    print(f"\n  Textos idênticos (original == changed):")
    for pt in PERTURB_TYPES:
        group = [i for i in instances if i.perturb_type == pt]
        ident = sum(
            1 for i in group
            if i.original_text.strip() == i.changed_text.strip()
        )
        if ident:
            print(f"    {pt:<28} : {ident}")

    # Contradicted fields — which types rely on cross-reference?
    print(f"\n  contradicted_location preenchido (% do tipo):")
    for pt in PERTURB_TYPES:
        group = [i for i in instances if i.perturb_type == pt]
        N = len(group)
        filled = sum(1 for i in group if i.contradicted_location)
        print(f"    {pt:<28} : {100*filled/N:5.1f}%")


# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Análise estrutural por tipo de perturbação"
    )
    parser.add_argument("--data", required=True)
    parser.add_argument(
        "--samples", type=int, default=1,
        help="Número de exemplos por dimensão por tipo (default 1)"
    )
    parser.add_argument("--type", default=None,
                        help="Analisar apenas um tipo (ex: ambiguity)")
    args = parser.parse_args()

    print(f"\nCarregando dataset de: {args.data}")
    instances = load_instances(args.data)
    if not instances:
        print("Nenhuma instância carregada.")
        sys.exit(1)
    print(f"Instâncias carregadas: {len(instances):,}\n")

    types_to_analyze = (
        [args.type] if args.type else PERTURB_TYPES
    )
    for pt in types_to_analyze:
        analyze_type(pt, instances, args.samples)

    if not args.type:
        cross_type_summary(instances)

    print(f"\n{SEP}\n  Análise concluída.\n{SEP}\n")


if __name__ == "__main__":
    main()
