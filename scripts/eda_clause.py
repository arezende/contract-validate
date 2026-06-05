"""
Análise exploratória do dataset CLAUSE.

Uso:
    python scripts/eda_clause.py --data data/raw/clause/datasets/
    python scripts/eda_clause.py --data data/raw/clause/datasets/ --output reports/eda/

Requer apenas: pip install -e .  (já instalado)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.basicConfig(level=logging.WARNING)  # silencia INFO do ingestor durante EDA

# ─── compatibilidade src-layout ───────────────────────────────────────────────
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))

from contractfol.corpus.ingest import load_instances
from contractfol.corpus.schema import DiscrepancyInstance

# ──────────────────────────────────────────────────────────────────────────────

SEP = "─" * 72


def _pct(n: int, total: int) -> str:
    return f"{n:>6,}  ({100 * n / total:5.1f}%)" if total else f"{n:>6,}  (  n/a)"


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ─── 1. Carregamento ──────────────────────────────────────────────────────────

def load(data_path: Path) -> list[DiscrepancyInstance]:
    logging.getLogger().setLevel(logging.INFO)
    instances = load_instances(data_path)
    logging.getLogger().setLevel(logging.WARNING)
    return instances


# ─── 2. Estatísticas gerais ───────────────────────────────────────────────────

def stats_overview(instances: list[DiscrepancyInstance]) -> None:
    section("1. VISÃO GERAL")
    N = len(instances)
    print(f"  Total de instâncias : {N:,}")
    print(f"  Datasets            : {Counter(i.source_dataset for i in instances)}")

    by_ds = Counter(i.source_dataset for i in instances)
    for ds, cnt in sorted(by_ds.items()):
        print(f"    {ds:6s} : {_pct(cnt, N)}")


# ─── 3. Distribuição por categoria ───────────────────────────────────────────

def stats_categories(instances: list[DiscrepancyInstance]) -> None:
    section("2. DISTRIBUIÇÃO POR CATEGORIA (perturb_type × dimension)")
    N = len(instances)

    # tabela 5 × 2
    perturb_types = ["ambiguity", "inconsistency", "misaligned_terminology",
                     "omission", "structural_flaw"]
    dimensions    = ["in_text", "legal"]

    counts: dict[tuple[str, str], int] = Counter(
        (i.perturb_type, i.dimension) for i in instances
    )

    header = f"  {'Tipo':<28}  {'in_text':>10}  {'legal':>10}  {'total':>10}"
    print(header)
    print("  " + "-" * 64)
    for pt in perturb_types:
        it = counts.get((pt, "in_text"), 0)
        lg = counts.get((pt, "legal"), 0)
        tot = it + lg
        print(f"  {pt:<28}  {it:>10,}  {lg:>10,}  {_pct(tot, N)}")
    print("  " + "-" * 64)
    for dim in dimensions:
        tot = sum(v for (_, d), v in counts.items() if d == dim)
        print(f"  {'TOTAL ' + dim:<28}  {_pct(tot, N)}")


# ─── 4. Campos opcionais — taxa de preenchimento ──────────────────────────────

def stats_field_coverage(instances: list[DiscrepancyInstance]) -> None:
    section("3. COBERTURA DE CAMPOS OPCIONAIS")
    N = len(instances)
    optional_fields = [
        "location", "contradicted_location", "contradicted_text",
        "contradicted_law", "law_citation", "law_url1", "law_url2",
        "scraped_snippet_1", "scraped_snippet_2",
    ]
    print(f"  {'Campo':<28}  {'preenchido':>12}  {'%':>6}")
    print("  " + "-" * 50)
    for field in optional_fields:
        filled = sum(1 for i in instances if getattr(i, field) is not None)
        print(f"  {field:<28}  {filled:>12,}  {100*filled/N:>5.1f}%")

    # Verificação: campos legais só em instâncias legal
    legal_instances = [i for i in instances if i.dimension == "legal"]
    n_legal = len(legal_instances)
    if n_legal:
        print(f"\n  Instâncias legal: {n_legal:,}")
        for field in ["law_citation", "law_url1", "scraped_snippet_1"]:
            filled = sum(1 for i in legal_instances if getattr(i, field) is not None)
            print(f"    {field:<28} preenchido em {100*filled/n_legal:.1f}% das legais")


# ─── 5. Comprimento dos textos ────────────────────────────────────────────────

def stats_text_lengths(instances: list[DiscrepancyInstance]) -> None:
    section("4. COMPRIMENTO DOS TEXTOS (caracteres)")

    def _stats(values: list[int]) -> str:
        if not values:
            return "n/a"
        values_sorted = sorted(values)
        n = len(values_sorted)
        mean = sum(values_sorted) / n
        median = values_sorted[n // 2]
        p90 = values_sorted[int(n * 0.9)]
        mx = values_sorted[-1]
        return f"média={mean:,.0f}  mediana={median:,}  p90={p90:,}  máx={mx:,}"

    orig_lens  = [len(i.original_text) for i in instances]
    chng_lens  = [len(i.changed_text)  for i in instances]
    expl_lens  = [len(i.explanation)   for i in instances]

    print(f"  original_text : {_stats(orig_lens)}")
    print(f"  changed_text  : {_stats(chng_lens)}")
    print(f"  explanation   : {_stats(expl_lens)}")

    # Diferença de comprimento original vs changed
    diffs = [abs(len(i.changed_text) - len(i.original_text)) for i in instances]
    print(f"  |changed - original| : {_stats(diffs)}")


# ─── 6. Contratos únicos e perturbações por contrato ─────────────────────────

def stats_contracts(instances: list[DiscrepancyInstance]) -> None:
    section("5. CONTRATOS E PERTURBAÇÕES POR CONTRATO")

    # instance_id = "<file_stem>_p<idx>" — extrai o stem
    def stem(iid: str) -> str:
        # remove sufixo _pN
        return iid.rsplit("_p", 1)[0]

    contracts: dict[str, list[DiscrepancyInstance]] = defaultdict(list)
    for i in instances:
        contracts[stem(i.instance_id)].append(i)

    n_contracts = len(contracts)
    perturbs_per_contract = [len(v) for v in contracts.values()]
    perturbs_per_contract.sort()
    n = len(perturbs_per_contract)

    print(f"  Contratos únicos   : {n_contracts:,}")
    print(f"  Perturbações/contrato:")
    print(f"    mínimo  : {perturbs_per_contract[0]}")
    print(f"    mediana : {perturbs_per_contract[n // 2]}")
    print(f"    máximo  : {perturbs_per_contract[-1]}")
    print(f"    média   : {sum(perturbs_per_contract)/n:.1f}")

    # Distribuição de frequências
    freq = Counter(perturbs_per_contract)
    print(f"\n  Distribuição de perturbações por contrato:")
    for k in sorted(freq.keys())[:15]:
        bar = "█" * min(freq[k] // max(1, n_contracts // 40), 40)
        print(f"    {k:>3} perturb(s): {freq[k]:>5,} contratos  {bar}")


# ─── 7. Problemas de qualidade ───────────────────────────────────────────────

def stats_quality(instances: list[DiscrepancyInstance]) -> None:
    section("6. ALERTAS DE QUALIDADE")

    issues: list[str] = []

    # Textos idênticos (perturbação não foi aplicada)
    identical = [i for i in instances if i.original_text.strip() == i.changed_text.strip()]
    if identical:
        issues.append(f"  ALERTA: {len(identical)} instâncias com original_text == changed_text")
        for x in identical[:3]:
            print(f"    ex: {x.instance_id}")

    # Textos vazios
    empty_orig = [i for i in instances if not i.original_text.strip()]
    empty_chng = [i for i in instances if not i.changed_text.strip()]
    empty_expl = [i for i in instances if not i.explanation.strip()]
    if empty_orig:
        issues.append(f"  ALERTA: {len(empty_orig)} instâncias com original_text vazio")
    if empty_chng:
        issues.append(f"  ALERTA: {len(empty_chng)} instâncias com changed_text vazio")
    if empty_expl:
        issues.append(f"  ALERTA: {len(empty_expl)} instâncias com explanation vazio")

    # Instâncias legal sem lei citada
    legal_no_law = [i for i in instances
                    if i.dimension == "legal" and not i.law_citation]
    if legal_no_law:
        issues.append(
            f"  INFO: {len(legal_no_law)} instâncias 'legal' sem law_citation "
            f"(podem ter scraped_snippet mesmo assim)"
        )

    # IDs duplicados
    id_counts = Counter(i.instance_id for i in instances)
    dups = {iid: cnt for iid, cnt in id_counts.items() if cnt > 1}
    if dups:
        issues.append(f"  ALERTA: {len(dups)} instance_ids duplicados")

    if issues:
        for msg in issues:
            print(msg)
    else:
        print("  Nenhum problema encontrado.")


# ─── 8. Amostra de instâncias ────────────────────────────────────────────────

def show_sample(instances: list[DiscrepancyInstance], n: int = 2) -> None:
    section(f"7. AMOSTRA DE {n} INSTÂNCIAS")
    import random
    random.seed(42)
    sample = random.sample(instances, min(n, len(instances)))
    for inst in sample:
        print(f"\n  instance_id       : {inst.instance_id}")
        print(f"  source_dataset    : {inst.source_dataset}")
        print(f"  perturb_type      : {inst.perturb_type}")
        print(f"  dimension         : {inst.dimension}")
        print(f"  location          : {inst.location}")
        print(f"  original_text     : {inst.original_text[:120]}...")
        print(f"  changed_text      : {inst.changed_text[:120]}...")
        print(f"  explanation       : {inst.explanation[:120]}...")
        if inst.law_citation:
            print(f"  law_citation      : {inst.law_citation}")


# ─── 9. Export JSON resumo ────────────────────────────────────────────────────

def export_summary(instances: list[DiscrepancyInstance], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    N = len(instances)

    counts = Counter((i.source_dataset, i.perturb_type, i.dimension) for i in instances)

    summary = {
        "total_instances": N,
        "by_dataset": dict(Counter(i.source_dataset for i in instances)),
        "by_perturb_type": dict(Counter(i.perturb_type for i in instances)),
        "by_dimension": dict(Counter(i.dimension for i in instances)),
        "by_category": {
            f"{ds}|{pt}|{dim}": cnt
            for (ds, pt, dim), cnt in sorted(counts.items())
        },
        "field_coverage": {
            field: sum(1 for i in instances if getattr(i, field) is not None)
            for field in ["location", "contradicted_location", "law_citation",
                          "scraped_snippet_1", "scraped_snippet_2"]
        },
    }

    out_path = output_dir / "eda_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n  Resumo exportado para: {out_path}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EDA do dataset CLAUSE")
    parser.add_argument("--data",   required=True, help="Caminho para a pasta datasets/")
    parser.add_argument("--output", default=None,  help="Pasta para exportar resumo JSON")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERRO: caminho não encontrado: {data_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCarregando dataset de: {data_path}")
    instances = load(data_path)

    if not instances:
        print("Nenhuma instância carregada. Verifique o caminho e o formato dos arquivos.")
        sys.exit(1)

    stats_overview(instances)
    stats_categories(instances)
    stats_field_coverage(instances)
    stats_text_lengths(instances)
    stats_contracts(instances)
    stats_quality(instances)
    show_sample(instances)

    if args.output:
        export_summary(instances, Path(args.output))

    print(f"\n{SEP}\n  EDA concluída.\n{SEP}\n")


if __name__ == "__main__":
    main()
