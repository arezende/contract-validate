"""
KB citation miner for ContractFOL v3.

Extracts the closed and finite set of statutes referenced in the CLAUSE
dataset (legal dimension only). Citations are deduplicated and sorted by
frequency. This module NEVER reads explanation or law_explanation fields —
only law_citation, law_url1, and law_url2 from DiscrepancyInstance.
"""

from __future__ import annotations

import re
from collections import defaultdict

from contractfol.corpus.schema import DiscrepancyInstance


def _normalize_citation(citation: str) -> str:
    """
    Normalise a citation string for deduplication:
    - lowercase
    - strip leading/trailing whitespace
    - collapse multiple internal spaces to one
    - remove spaces around § (treat "§ 1681" and "§1681" as identical)
    """
    s = citation.strip().lower()
    # Remove spaces immediately before or after §
    s = re.sub(r"\s*§\s*", "§", s)
    # Collapse multiple spaces
    s = re.sub(r" {2,}", " ", s)
    return s


def mine_citations(
    instances: list[DiscrepancyInstance],
) -> list[dict]:
    """
    From legal-dimension instances only, extract and deduplicate all law
    citations.

    Returns a list of dicts:
        [{"citation": str, "law_url1": str|None, "law_url2": str|None,
          "instance_count": int, "instance_ids": list[str]}, ...]
    Sorted by instance_count descending (most-referenced statutes first).

    Only processes instances where dimension == "legal".
    Sources: law_citation, law_url1, law_url2 fields only.
    Never reads explanation or law_explanation.
    """
    # norm_key → canonical display form (first seen, with original casing)
    canonical: dict[str, str] = {}
    # norm_key → set of instance ids
    ids_by_key: dict[str, set[str]] = defaultdict(set)
    # norm_key → first seen url1
    url1_by_key: dict[str, str | None] = {}
    # norm_key → first seen url2
    url2_by_key: dict[str, str | None] = {}

    for inst in instances:
        if inst.dimension != "legal":
            continue
        if not inst.law_citation:
            continue

        key = _normalize_citation(inst.law_citation)
        if key not in canonical:
            canonical[key] = inst.law_citation.strip()
            url1_by_key[key] = inst.law_url1
            url2_by_key[key] = inst.law_url2
        ids_by_key[key].add(inst.instance_id)

    result: list[dict] = []
    for key, cite in canonical.items():
        result.append(
            {
                "citation": cite,
                "law_url1": url1_by_key[key],
                "law_url2": url2_by_key[key],
                "instance_count": len(ids_by_key[key]),
                "instance_ids": sorted(ids_by_key[key]),
            }
        )

    # Sort by frequency descending, then citation ascending for stability
    result.sort(key=lambda r: (-r["instance_count"], r["citation"]))
    return result


def citations_to_yaml(citations: list[dict], output_path: str) -> None:
    """Write the citation list to a YAML file for manual review / annotation.

    Parameters
    ----------
    citations:
        Output of :func:`mine_citations`.
    output_path:
        Destination file path (will be overwritten if it exists).
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PyYAML is required for citations_to_yaml. "
            "Install it with: pip install pyyaml"
        ) from exc

    with open(output_path, "w", encoding="utf-8") as fh:
        yaml.dump(
            citations,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
