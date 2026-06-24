from clause_llm_eval.corpus.sample import stratified_fraction_sample
from clause_llm_eval.io import write_jsonl, read_jsonl


def test_sample(tmp_path):
    rows = []
    for i in range(100):
        rows.append({
            "instance_id": f"a{i}",
            "perturb_type": "ambiguity",
            "dimension": "in_text",
        })
    for i in range(100):
        rows.append({
            "instance_id": f"b{i}",
            "perturb_type": "omission",
            "dimension": "legal",
        })

    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    write_jsonl(rows, input_path)

    report = stratified_fraction_sample(str(input_path), str(output_path), fraction=0.10, seed=42)
    sampled = read_jsonl(output_path)

    assert len(sampled) == 20
    assert report["sampled_total"] == 20
