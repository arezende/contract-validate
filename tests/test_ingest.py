import json

from clause_llm_eval.corpus.ingest import load_instances


def _write_clause_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "file_name": "SAME_NAME.txt",
                    "perturbation": [
                        {
                            "type": "Omissions - Legal",
                            "original_text": "Original contract text.",
                            "changed_text": "Changed contract text.",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_ingest_instance_ids_include_source_dataset(tmp_path):
    _write_clause_file(tmp_path / "CUAD_Dataset" / "Omissions" / "a.json")
    _write_clause_file(tmp_path / "NLI_Dataset" / "Omissions" / "a.json")

    instances = load_instances(tmp_path)
    ids = [i.instance_id for i in instances]

    assert len(ids) == 2
    assert len(set(ids)) == 2
    assert any(i.startswith("cuad_") for i in ids)
    assert any(i.startswith("nli_") for i in ids)
