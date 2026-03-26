"""Tests for the scientific ContractFOL pipeline."""

from pathlib import Path

from contractfol.scientific.pipeline import (
    ContractFOLScientificPipeline,
    compilar_contrato,
    preprocessar,
    traduzir_contrato,
    verificar_consistencia_interna,
    verificar_conformidade_cruzada,
)


def _write_sample(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_preprocess_basic(tmp_path: Path):
    path = _write_sample(
        tmp_path,
        "a.txt",
        """CLÁUSULA PRIMEIRA - DAS PARTES\nO COB e a Confederação celebram o contrato.\n\nCLÁUSULA SEGUNDA - DAS OBRIGAÇÕES\nO COB deverá repassar os recursos em até 30 dias.""",
    )
    res = preprocessar(path, "A")
    assert res.total_clausulas >= 2
    assert any("COB" in parte for parte in res.partes)


def test_translate_and_compile_conflict(tmp_path: Path):
    path_a = _write_sample(
        tmp_path,
        "a.txt",
        """CLÁUSULA ÚNICA\nO COB deverá repassar os recursos em até 30 dias.""",
    )
    path_b = _write_sample(
        tmp_path,
        "b.txt",
        """CLÁUSULA ÚNICA\nO COB deverá repassar os recursos somente após 60 dias.""",
    )
    prep_a = preprocessar(path_a, "A")
    prep_b = preprocessar(path_b, "B")
    trad_a = traduzir_contrato(prep_a)
    trad_b = traduzir_contrato(prep_b)
    comp_a = compilar_contrato(trad_a)
    comp_b = compilar_contrato(trad_b)
    verif = verificar_conformidade_cruzada(comp_a, comp_b)
    assert verif.status.value == "unsat"
    assert verif.total_problemas >= 1


def test_interna_sat_on_simple_contract(tmp_path: Path):
    path = _write_sample(
        tmp_path,
        "sat.txt",
        """CLÁUSULA ÚNICA\nO COB deverá disponibilizar instalações esportivas.""",
    )
    prep = preprocessar(path, "A")
    trad = traduzir_contrato(prep)
    comp = compilar_contrato(trad)
    verif = verificar_consistencia_interna(comp)
    assert verif.status.value in {"sat", "unknown"}


def test_end_to_end_pipeline(tmp_path: Path):
    path_a = _write_sample(
        tmp_path,
        "a.txt",
        """CLÁUSULA ÚNICA\nO COB deverá repassar os recursos em até 30 dias.""",
    )
    path_b = _write_sample(
        tmp_path,
        "b.txt",
        """CLÁUSULA ÚNICA\nO COB deverá repassar os recursos somente após 60 dias.""",
    )
    pipeline = ContractFOLScientificPipeline()
    relatorio = pipeline.run(path_a, path_b)
    assert relatorio.total_invalidas >= 1
