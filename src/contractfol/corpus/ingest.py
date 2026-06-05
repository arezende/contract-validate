"""CLAUSE dataset JSON ingestor for ContractFOL corpus.

Converts CLAUSE metadata JSON records into validated DiscrepancyInstance objects.
The FIELD_MAP at the top of this file is the single point of maintenance: update
the values (CLAUSE field names) when the actual CLAUSE JSON schema is confirmed.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from contractfol.corpus.schema import DiscrepancyInstance

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field mapping — update these when the actual CLAUSE JSON schema is confirmed.
# Keys   = DiscrepancyInstance field names
# Values = CLAUSE JSON field names
# ---------------------------------------------------------------------------
FIELD_MAP: dict[str, str] = {
    "instance_id":            "id",
    "source_dataset":         "dataset",           # expected: "cuad" | "nli"
    "perturb_type":           "perturbation_type",
    "dimension":              "dimension",          # expected: "in_text" | "legal"
    "original_text":          "original_text",
    "changed_text":           "changed_text",
    "explanation":            "explanation",
    "location":               "location",
    "contradicted_location":  "contradicted_location",
    "contradicted_text":      "contradicted_text",
    "contradicted_law":       "contradicted_law",
    "law_citation":           "law_citation",
    "law_url1":               "law_url1",
    "law_url2":               "law_url2",
    "scraped_snippet_1":      "scraped_snippet_1",
    "scraped_snippet_2":      "scraped_snippet_2",
}

# Fields that require normalization before Pydantic validation.
# Normalization: lowercase + replace spaces with underscores.
_NORMALIZE_FIELDS = {"source_dataset", "perturb_type", "dimension"}


def _normalize(value: object) -> str:
    """Lowercase string and replace spaces with underscores."""
    return str(value).lower().replace(" ", "_")


def _map_record(raw: dict) -> dict:
    """Apply FIELD_MAP and normalization to a raw CLAUSE JSON record."""
    mapped: dict = {}
    for dest_field, src_field in FIELD_MAP.items():
        value = raw.get(src_field)
        if value is not None:
            mapped[dest_field] = _normalize(value) if dest_field in _NORMALIZE_FIELDS else value
    return mapped


def _load_json_file(path: Path) -> list[dict]:
    """Read a JSON file and return a list of records.

    Accepts both a JSON array at the top level and a single object (wrapped
    into a list automatically).
    """
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected JSON structure in {path}: {type(data)}")


def load_instances(path: str | Path) -> list[DiscrepancyInstance]:
    """Load DiscrepancyInstance objects from a JSON file or directory of JSON files.

    Validation failures are logged and skipped; the ingest continues for all
    remaining records.  A summary (total loaded, total skipped, breakdown by
    source_dataset × perturb_type × dimension) is emitted at INFO level.

    Parameters
    ----------
    path:
        Path to a single ``.json`` file or a directory containing ``.json``
        files (non-recursive).

    Returns
    -------
    list[DiscrepancyInstance]
        All successfully validated instances.
    """
    path = Path(path)

    # Collect candidate files.
    if path.is_dir():
        json_files = sorted(path.glob("*.json"))
        if not json_files:
            logger.warning("No .json files found in directory: %s", path)
            return []
    elif path.is_file():
        json_files = [path]
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    instances: list[DiscrepancyInstance] = []
    skipped = 0
    breakdown: dict[tuple[str, str, str], int] = defaultdict(int)

    for json_file in json_files:
        try:
            raw_records = _load_json_file(json_file)
        except Exception as exc:
            logger.error("Failed to read %s: %s", json_file, exc)
            continue

        for raw in raw_records:
            mapped = _map_record(raw)
            instance_id = mapped.get("instance_id", raw.get("id", "<unknown>"))
            try:
                inst = DiscrepancyInstance(**mapped)
            except ValidationError as exc:
                logger.error(
                    "Validation failed for instance_id=%r — skipping.\n"
                    "  Raw record: %r\n"
                    "  Errors: %s",
                    instance_id,
                    raw,
                    exc,
                )
                skipped += 1
                continue

            instances.append(inst)
            key = (inst.source_dataset, inst.perturb_type, inst.dimension)
            breakdown[key] += 1

    total = len(instances)
    logger.info(
        "Ingest complete — loaded: %d, skipped: %d", total, skipped
    )
    if breakdown:
        logger.info("Breakdown by (source_dataset, perturb_type, dimension):")
        for (ds, pt, dim), count in sorted(breakdown.items()):
            logger.info("  %-6s | %-24s | %-8s : %d", ds, pt, dim, count)

    return instances
