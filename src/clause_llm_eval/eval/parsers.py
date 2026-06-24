from __future__ import annotations

import json
import re
from typing import Any


def parse_response(task: str, raw: str) -> tuple[Any, str | None]:
    if task == "eval1":
        return parse_eval1(raw)
    if task == "eval2":
        return parse_eval2(raw)
    if task == "eval3":
        return parse_eval3(raw)
    raise ValueError(f"Tarefa desconhecida: {task}")


def parse_eval1(raw: str) -> tuple[int | None, str | None]:
    text = raw.strip().lower()
    token = re.sub(r"[^a-z]", "", text.split()[0]) if text.split() else ""

    if token == "yes":
        return 1, None
    if token == "no":
        return 0, None

    if text.startswith("yes"):
        return 1, None
    if text.startswith("no"):
        return 0, None

    return None, f"Resposta Eval_1 inválida: {raw!r}"


def parse_eval2(raw: str) -> tuple[str | None, str | None]:
    text = raw.strip().lower()
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z_]", "", text)

    if text in {"in_text", "intext", "internal", "internal_contradiction"}:
        return "in_text", None
    if text in {"legal", "outer_law", "outerlaw", "external", "external_legal"}:
        return "legal", None
    if text in {"none", "no", "no_contradiction", "no_discrepancy"}:
        return "none", None

    if "in_text" in text or "internal" in text:
        return "in_text", None
    if "legal" in text or "outer" in text or "external" in text:
        return "legal", None
    if "none" in text or text == "no":
        return "none", None

    return None, f"Resposta Eval_2 inválida: {raw!r}"


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    if arr_start >= 0 and arr_end > arr_start and (obj_start < 0 or arr_start < obj_start):
        return text[arr_start:arr_end + 1]
    if obj_start >= 0 and obj_end > obj_start:
        return text[obj_start:obj_end + 1]
    return text


def parse_eval3(raw: str) -> tuple[dict | None, str | None]:
    try:
        obj = json.loads(_extract_json(raw))
    except Exception as exc:
        return None, f"JSON inválido Eval_3: {exc}; raw={raw!r}"

    if isinstance(obj, list):
        obj = {
            "has_discrepancy": bool(obj),
            "dimension": None,
            "spans": obj,
        }

    if not isinstance(obj, dict):
        return None, "Eval_3 não retornou objeto JSON."

    if "has_discrepancy" not in obj or "spans" not in obj:
        return None, "Eval_3 sem campos obrigatórios."

    if not isinstance(obj["spans"], list):
        return None, "Eval_3 retornou spans em formato invÃ¡lido."

    return obj, None
