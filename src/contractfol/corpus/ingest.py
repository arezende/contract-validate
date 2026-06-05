"""CLAUSE dataset JSON ingestor for ContractFOL corpus.

Real CLAUSE JSON structure (confirmed from dataset inspection):

  [                                      ← array of contract objects
    {
      "file_name": "COMPANY_DATE.txt",   ← source contract filename
      "perturbation": [                  ← one or more perturbations per contract
        {
          "type": "Ambiguities - In Text Contradiction",
          "original_text": "...",
          "changed_text":  "...",
          "explanation":   "...",        ← description of what changed
          "justification": "...",        ← why this is a contradiction
          "location":               "Section X.Y",
          "contradicted_location":  "Section A.B",   (optional)
          "contradicted_text":      "...",            (optional)
          "contradiction_exists":   "YES",
          -- legal-dimension only --
          "contradicted_law":   "...",
          "law_citation":       "...",
          "law_url1":           "...",
          "law_url2":           "...",
          "scraped_snippet_1":  "...",
          "scraped_snippet_2":  "...",
        },
        ...
      ]
    },
    ...
  ]

One DiscrepancyInstance is created per perturbation entry.
instance_id  = "<file_stem>_p<index>"
source_dataset is inferred from the directory path
               (CUAD_Dataset → "cuad", NLI_Dataset → "nli").
perturb_type + dimension are parsed from the "type" field.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from contractfol.corpus.schema import DiscrepancyInstance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Windows long-path workaround
# rglob() uses FindFirstFile (no 260-char limit) but open() uses CreateFile
# (fails for paths > MAX_PATH).  Prepending \\?\ switches to extended-length
# mode (up to 32,767 chars).
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> object:
    """Read and parse a JSON file, handling Windows MAX_PATH on retry."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        if sys.platform != "win32":
            raise
        long = "\\\\?\\" + os.path.abspath(str(path))
        with open(long, "r", encoding="utf-8") as fh:
            return json.load(fh)


# ---------------------------------------------------------------------------
# Type-field parser
# Maps CLAUSE "type" strings → (perturb_type, dimension)
# "Ambiguities - In Text Contradiction" → ("ambiguity", "in_text")
# "Inconsistency - Legal"               → ("inconsistency", "legal")
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("ambiguit",     "ambiguity"),
    ("inconsistenc", "inconsistency"),
    ("inconsenc",    "inconsistency"),   # dataset typo: "Inconsencies"
    ("misaligned",   "misaligned_terminology"),
    ("terminology",  "misaligned_terminology"),
    ("omission",     "omission"),
    ("structural",   "structural_flaw"),
]


def _parse_type_field(type_str: str) -> tuple[str, str]:
    """Return (perturb_type, dimension) from a CLAUSE 'type' string."""
    lower = type_str.lower()

    dimension = "legal" if "legal" in lower else "in_text"

    perturb_type = "ambiguity"  # default fallback
    for keyword, mapped in _TYPE_KEYWORDS:
        if keyword in lower:
            perturb_type = mapped
            break
    else:
        logger.warning("Unknown perturbation type string %r — defaulting to 'ambiguity'", type_str)

    return perturb_type, dimension


# ---------------------------------------------------------------------------
# Source-dataset inference from directory path
# ---------------------------------------------------------------------------

def _infer_source_dataset(file_path: Path) -> str:
    """Return 'cuad' or 'nli' based on a parent directory name."""
    parts_lower = [p.lower() for p in file_path.parts]
    if any("nli" in p for p in parts_lower):
        return "nli"
    return "cuad"


# ---------------------------------------------------------------------------
# URL field coercion — real CLAUSE data stores law_url1/2 as list[str]
# ---------------------------------------------------------------------------

def _coerce_url(value: object) -> str | None:
    """Normalise a URL field that may arrive as str, list[str], or None."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value)


# ---------------------------------------------------------------------------
# Single perturbation → DiscrepancyInstance
# ---------------------------------------------------------------------------

def _perturbation_to_instance(
    file_name: str,
    contract_idx: int,
    perturb_idx: int,
    perturb: dict,
    source_dataset: str,
    category: str = "",
    json_stem: str = "",
) -> DiscrepancyInstance:
    """Convert one perturbation dict to a DiscrepancyInstance.

    ``json_stem`` is the stem of the actual JSON file on disk; it is used
    instead of ``Path(file_name).stem`` because ``file_name`` (the field
    inside the JSON) is not unique within a category directory.
    ``contract_idx`` disambiguates JSON files that contain multiple
    contract objects (rare but present in the dataset).
    ``category`` is the immediate parent directory name.
    """
    stem = json_stem if json_stem else Path(file_name).stem
    prefix = f"{category}_" if category else ""
    contract_part = f"_c{contract_idx}" if contract_idx else ""
    instance_id = f"{prefix}{stem}{contract_part}_p{perturb_idx}"

    perturb_type, dimension = _parse_type_field(perturb.get("type", ""))

    return DiscrepancyInstance(
        instance_id=instance_id,
        source_dataset=source_dataset,
        perturb_type=perturb_type,
        dimension=dimension,
        original_text=perturb["original_text"],
        changed_text=perturb["changed_text"],
        explanation=perturb.get("explanation") or perturb.get("justification") or "",
        location=perturb.get("location"),
        contradicted_location=perturb.get("contradicted_location"),
        contradicted_text=perturb.get("contradicted_text"),
        contradicted_law=perturb.get("contradicted_law"),
        law_citation=perturb.get("law_citation"),
        law_url1=_coerce_url(perturb.get("law_url1")),
        law_url2=_coerce_url(perturb.get("law_url2")),
        scraped_snippet_1=perturb.get("scraped_snippet_1"),
        scraped_snippet_2=perturb.get("scraped_snippet_2"),
        gold_label=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_instances(path: str | Path) -> list[DiscrepancyInstance]:
    """Load DiscrepancyInstance objects from the CLAUSE dataset.

    Accepts:
    - A single ``.json`` file
    - A directory of ``.json`` files (non-recursive)
    - A root directory that is walked recursively for all ``.json`` files

    Each JSON file must follow the CLAUSE format: a top-level array of objects,
    each with a ``file_name`` and a ``perturbation`` array.

    Validation failures are logged and skipped.
    A summary is emitted at INFO level.
    """
    path = Path(path)

    if path.is_file():
        json_files = [path]
    elif path.is_dir():
        json_files = sorted(path.rglob("*.json"))
        if not json_files:
            logger.warning("No .json files found under: %s", path)
            return []
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    instances: list[DiscrepancyInstance] = []
    skipped = 0
    breakdown: defaultdict[tuple[str, str, str], int] = defaultdict(int)

    for json_file in json_files:
        source_dataset = _infer_source_dataset(json_file)
        try:
            data = _read_json(json_file)
        except Exception as exc:
            logger.error("Failed to read %s: %s", json_file, exc)
            continue

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            logger.error("Unexpected top-level JSON type in %s: %s", json_file, type(data))
            continue

        category = json_file.parent.name
        json_stem = json_file.stem

        for ci, contract_obj in enumerate(data):
            file_name = contract_obj.get("file_name", json_file.name)
            perturbations = contract_obj.get("perturbation", [])

            for pi, perturb in enumerate(perturbations):
                try:
                    inst = _perturbation_to_instance(
                        file_name, ci, pi, perturb, source_dataset, category, json_stem
                    )
                except (KeyError, ValidationError) as exc:
                    logger.error(
                        "Skipping perturbation c%d/p%d of %r: %s",
                        ci, pi, file_name, exc,
                    )
                    skipped += 1
                    continue

                instances.append(inst)
                breakdown[(inst.source_dataset, inst.perturb_type, inst.dimension)] += 1

    logger.info("Ingest complete — loaded: %d, skipped: %d", len(instances), skipped)
    if breakdown:
        logger.info("Breakdown by (dataset, perturb_type, dimension):")
        for (ds, pt, dim), count in sorted(breakdown.items()):
            logger.info("  %-6s | %-26s | %-8s : %d", ds, pt, dim, count)

    return instances
