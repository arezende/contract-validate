#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Exemplos de uso do CompilationLogger para o pipeline ContractFOL.

Demonstra:
1. Registrar compilações bem-sucedidas
2. Registrar erros
3. Consultar estatísticas
4. Filtrar logs
"""

import time
import json
from pathlib import Path
from src.contractfol.contractfol.core.compilation_logger import (
    CompilationLogger,
    get_logger,
    CompilationStatus
)


def exemplo_1_compilacao_sucesso():
    """Exemplo 1: Registrar uma compilação bem-sucedida."""
    print("\n[EXEMPLO 1] Registrar compilacao bem-sucedida")
    print("-" * 70)

    logger = get_logger()
    start_time = time.time()

    # Simular processamento
    time.sleep(0.1)

    # Dados simulados
    deontic_map = {
        "clausulas": [
            {"id": "CL_1", "texto": "Clausula 1"},
            {"id": "CL_2", "texto": "Clausula 2"},
        ],
        "regras_deonticas": [
            {"tipo": "obrigacao", "sujeito": "Contratada"},
            {"tipo": "proibicao", "sujeito": "Contratante"},
        ]
    }

    fol_formula = {
        "formulas": [
            {"clausula_id": "CL_1", "formula": "forall x . P(x) -> Q(x)"},
            {"clausula_id": "CL_2", "formula": "exists x . R(x)"},
        ]
    }

    end_time = time.time()
    compilation_time = (end_time - start_time) * 1000

    logger.log_success(
        contract_id="contrato_1",
        deontic_map=deontic_map,
        fol_formula=fol_formula,
        compilation_time_ms=compilation_time,
        metadata={
            "modelo_llm": "claude-opus",
            "temperatura": 0.3,
            "versao_pipeline": "3.0"
        }
    )

    print(f"OK: Compilacao registrada para contrato_1")
    print(f"    Tempo: {compilation_time:.2f}ms")
    print(f"    Clausulas: {len(deontic_map['clausulas'])}")
    print(f"    Regras: {len(deontic_map['regras_deonticas'])}")
    print(f"    Formulas FOL: {len(fol_formula['formulas'])}")


def exemplo_2_compilacao_erro():
    """Exemplo 2: Registrar um erro de compilação."""
    print("\n[EXEMPLO 2] Registrar erro de compilacao")
    print("-" * 70)

    logger = get_logger()

    deontic_map = {
        "clausulas": [
            {"id": "CL_1", "texto": "Clausula com erro"},
        ],
        "regras_deonticas": []
    }

    logger.log_error(
        contract_id="contrato_2",
        error_msg="Falha ao converter para FOL: quantificador invalido",
        deontic_map=deontic_map,
        metadata={
            "fase": "conversao_e2_e3",
            "tipo_erro": "invalid_quantifier"
        }
    )

    print("OK: Erro registrado para contrato_2")
    print("    Tipo: invalid_quantifier")


def exemplo_3_multiplas_compilacoes():
    """Exemplo 3: Registrar múltiplas compilações."""
    print("\n[EXEMPLO 3] Registrar multiplas compilacoes")
    print("-" * 70)

    logger = get_logger()

    # Simular processamento de 3 contratos
    for i in range(3, 6):
        deontic_map = {
            "clausulas": [{"id": f"CL_{j}", "texto": f"Clausula {j}"} for j in range(5)],
            "regras_deonticas": [{"tipo": "obrigacao"} for _ in range(8)]
        }

        fol_formula = {
            "formulas": [{"clausula_id": f"CL_{j}", "formula": f"Formula {j}"} for j in range(8)]
        }

        logger.log_success(
            contract_id=f"contrato_{i}",
            deontic_map=deontic_map,
            fol_formula=fol_formula,
            compilation_time_ms=100 + i * 10
        )

        print(f"OK: contrato_{i} registrado")


def exemplo_4_consultar_estatisticas():
    """Exemplo 4: Consultar estatísticas gerais."""
    print("\n[EXEMPLO 4] Consultar estatisticas gerais")
    print("-" * 70)

    logger = get_logger()
    stats = logger.get_statistics()

    print(f"Total de compilacoes: {stats['total']}")
    print(f"Bem-sucedidas: {stats['successful']}")
    print(f"Erros: {stats['errors']}")
    print(f"Total de clausulas processadas: {stats['total_clauses']}")
    print(f"Total de regras deonticas: {stats['total_deontic_rules']}")
    print(f"Total de formulas FOL: {stats['total_fol_formulas']}")

    if stats['total'] > 0:
        taxa_sucesso = (stats['successful'] / stats['total']) * 100
        print(f"Taxa de sucesso: {taxa_sucesso:.1f}%")


def exemplo_5_filtrar_logs():
    """Exemplo 5: Filtrar logs por contrato e status."""
    print("\n[EXEMPLO 5] Filtrar logs")
    print("-" * 70)

    logger = get_logger()

    # Logs de um contrato específico
    logs_contrato_1 = logger.get_compilations(contract_id="contrato_1")
    print(f"Compilacoes de contrato_1: {len(logs_contrato_1)}")

    # Logs com erro
    logs_erro = logger.get_compilations(status="error")
    print(f"Compilacoes com erro: {len(logs_erro)}")

    if logs_erro:
        for log in logs_erro:
            print(f"  - {log['contract_id']}: {log['error']}")

    # Logs bem-sucedidos
    logs_sucesso = logger.get_compilations(status="success")
    print(f"Compilacoes bem-sucedidas: {len(logs_sucesso)}")


def exemplo_6_resumo_visual():
    """Exemplo 6: Imprimir resumo visual."""
    print("\n[EXEMPLO 6] Resumo visual do logger")
    print("-" * 70)

    logger = get_logger()
    logger.print_summary()


def exemplo_7_analise_logs_json():
    """Exemplo 7: Análise manual do arquivo JSON."""
    print("\n[EXEMPLO 7] Analise do arquivo de logs JSON")
    print("-" * 70)

    log_file = Path("src/contractfol/contractfol/data/output/compilation_logs.json")

    if not log_file.exists():
        print("Arquivo de logs nao encontrado")
        return

    with open(log_file, encoding='utf-8') as f:
        logs = json.load(f)

    # Compilações mais lentas
    slow = sorted(
        [c for c in logs["compilations"] if c.get("compilation_time_ms")],
        key=lambda x: x["compilation_time_ms"],
        reverse=True
    )[:3]

    if slow:
        print("Top 3 compilacoes mais lentas:")
        for c in slow:
            print(f"  {c['contract_id']}: {c['compilation_time_ms']:.2f}ms")

    # Contratos com mais regras
    by_rules = sorted(
        logs["compilations"],
        key=lambda x: x["num_deontic_rules"],
        reverse=True
    )[:3]

    if by_rules:
        print("\nTop 3 contratos com mais regras deonticas:")
        for c in by_rules:
            print(f"  {c['contract_id']}: {c['num_deontic_rules']} regras")


def main():
    """Executa todos os exemplos."""
    print("\n" + "=" * 70)
    print("EXEMPLOS DE USO - CompilationLogger")
    print("=" * 70)

    try:
        exemplo_1_compilacao_sucesso()
        exemplo_2_compilacao_erro()
        exemplo_3_multiplas_compilacoes()
        exemplo_4_consultar_estatisticas()
        exemplo_5_filtrar_logs()
        exemplo_6_resumo_visual()
        exemplo_7_analise_logs_json()

        print("\n" + "=" * 70)
        print("[DONE] Todos os exemplos executados")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
