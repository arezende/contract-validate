from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from clause_llm_eval.io import read_json, write_jsonl
from clause_llm_eval.schemas import DiscrepancyInstance


CATEGORY_MAP = {
    "ambiguities": "ambiguity",
    "ambiguity": "ambiguity",
    "inconsistencies": "inconsistency",
    "inconsistency": "inconsistency",
    "misaligned_terminology": "misaligned_terminology",
    "misaligned terminology": "misaligned_terminology",
    "omissions": "omission",
    "omission": "omission",
    "structural_flaws": "structural_flaw",
    "structural flaws": "structural_flaw",
}


def _clean_id_part(value: str) -> str:
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:120] or "unknown"


def infer_source_dataset(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if any("cuad_dataset" == p for p in parts):
        return "cuad"
    if any("nli_dataset" == p for p in parts):
        return "nli"
    if any("cuad" in p for p in parts):
        return "cuad"
    if any("nli" in p for p in parts):
        return "nli"
    raise ValueError(f"Não foi possível inferir source_dataset a partir de {path}")


def infer_category_from_parent(path: Path) -> str:
    parent = path.parent.name
    key = parent.lower().replace("_", " ").strip()
    key2 = parent.lower().strip()

    if key2 in CATEGORY_MAP:
        return CATEGORY_MAP[key2]
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]

    raise ValueError(f"Categoria desconhecida pelo diretório pai: {parent} em {path}")


def parse_type(type_text: str, fallback_category: str) -> tuple[str, str]:
    text = (type_text or "").strip().lower()
    normalized = text.replace("_", " ")

    perturb_type = fallback_category

    if "ambigu" in normalized:
        perturb_type = "ambiguity"
    elif "inconsisten" in normalized:
        perturb_type = "inconsistency"
    elif "misaligned" in normalized or "terminology" in normalized:
        perturb_type = "misaligned_terminology"
    elif "omission" in normalized:
        perturb_type = "omission"
    elif "structural" in normalized or "flaw" in normalized:
        perturb_type = "structural_flaw"

    if "legal" in normalized or "outer" in normalized or "law" in normalized:
        dimension = "legal"
    else:
        dimension = "in_text"

    return perturb_type, dimension


def coerce_url(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v)
    text = str(value).strip()
    return text or None


def load_instances(data_root: str | Path) -> list[DiscrepancyInstance]:
    data_root = Path(data_root)
    files = sorted(data_root.rglob("*.json"))

    instances: list[DiscrepancyInstance] = []

    for file_path in files:
        source_dataset = infer_source_dataset(file_path)
        fallback_category = infer_category_from_parent(file_path)

        data = read_json(file_path)
        if isinstance(data, dict):
            contracts = [data]
        elif isinstance(data, list):
            contracts = data
        else:
            raise ValueError(f"Formato JSON inesperado em {file_path}")

        for ci, contract in enumerate(contracts):
            file_name = contract.get("file_name") or file_path.stem
            perturbations = contract.get("perturbation") or []

            if not isinstance(perturbations, list):
                continue

            for pi, perturb in enumerate(perturbations):
                if not isinstance(perturb, dict):
                    continue

                perturb_type, dimension = parse_type(
                    str(perturb.get("type", "")),
                    fallback_category=fallback_category,
                )

                stem = _clean_id_part(Path(file_name).stem)
                category = _clean_id_part(fallback_category)
                instance_id = f"{source_dataset}_{category}_{stem}_c{ci}_p{pi}"

                original_text = perturb.get("original_text") or contract.get("original_text") or ""
                changed_text = perturb.get("changed_text") or contract.get("changed_text") or ""

                if not original_text or not changed_text:
                    continue

                inst = DiscrepancyInstance(
                    instance_id=instance_id,
                    source_dataset=source_dataset,
                    perturb_type=perturb_type,
                    dimension=dimension,
                    original_text=str(original_text),
                    changed_text=str(changed_text),
                    explanation=perturb.get("explanation"),
                    justification=perturb.get("justification"),
                    location=perturb.get("location"),
                    contradicted_location=perturb.get("contradicted_location"),
                    contradicted_text=perturb.get("contradicted_text"),
                    contradicted_law=perturb.get("contradicted_law"),
                    law_citation=perturb.get("law_citation"),
                    law_url1=coerce_url(perturb.get("law_url1")),
                    law_url2=coerce_url(perturb.get("law_url2")),
                    scraped_snippet_1=perturb.get("scraped_snippet_1"),
                    scraped_snippet_2=perturb.get("scraped_snippet_2"),
                    gold_label=True,
                )
                instances.append(inst)

    return instances


def ingest_to_jsonl(data_root: str | Path, output: str | Path) -> None:
    instances = load_instances(data_root)
    write_jsonl((i.model_dump() for i in instances), output)
