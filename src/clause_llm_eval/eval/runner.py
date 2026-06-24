from __future__ import annotations

import time
from pathlib import Path

from tqdm import tqdm

from clause_llm_eval.eval.parsers import parse_response
from clause_llm_eval.eval.prompts import build_prompt
from clause_llm_eval.io import read_jsonl, write_jsonl
from clause_llm_eval.llm.providers import get_provider


def run_eval(
    input_jsonl: str,
    output_jsonl: str,
    task: str,
    provider_name: str,
    model: str,
    temperature: float = 0.0,
    limit: int | None = None,
    resume: bool = True,
    sleep_seconds: float = 0.0,
) -> dict:
    rows = read_jsonl(input_jsonl)
    if limit is not None:
        rows = rows[:limit]

    output_path = Path(output_jsonl)
    done_ids: set[str] = set()
    existing: list[dict] = []

    if resume and output_path.exists():
        existing = read_jsonl(output_path)
        done_ids = {r["eval_id"] for r in existing}

    provider = get_provider(provider_name)

    predictions = list(existing)
    remaining = [r for r in rows if r["eval_id"] not in done_ids]

    for row in tqdm(remaining, desc=f"Running {task}/{provider_name}/{model}"):
        prompt = build_prompt(task, row["doc"])

        try:
            raw = provider.complete(prompt=prompt, model=model, temperature=temperature)
            pred, parse_error = parse_response(task, raw)
        except Exception as exc:
            raw = ""
            pred = None
            parse_error = f"Erro de execução: {exc}"

        pred_row = {
            "eval_id": row["eval_id"],
            "instance_id": row["instance_id"],
            "source_dataset": row["source_dataset"],
            "perturb_type": row["perturb_type"],
            "dimension": row["dimension"],
            "task": task,
            "variant": row.get("variant"),
            "label": row["label"],
            "prediction": pred,
            "raw_response": raw,
            "parse_error": parse_error,
            "provider": provider_name,
            "model": model,
            "temperature": temperature,
        }

        predictions.append(pred_row)
        write_jsonl(predictions, output_jsonl)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return {
        "input_rows": len(rows),
        "already_done": len(done_ids),
        "new_predictions": len(remaining),
        "output": output_jsonl,
    }
