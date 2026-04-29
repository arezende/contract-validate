#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup script para reorganizar a estrutura de output do pipeline ContractFOL.

Cria:
- output/E1/extractions/         (cláusulas extraídas)
- output/E2/deontic_maps/        (mapas deônticos)
- output/E3/fol_formulas/        (fórmulas FOL)
- output/compilation_logs.json   (log de compilações E2→E3)
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class OutputStructureManager:
    """Gerencia a estrutura de output do pipeline ContractFOL."""

    def __init__(self, base_output_dir: str = "src/contractfol/contractfol/data/output"):
        self.base_output = Path(base_output_dir)
        self.base_output.mkdir(parents=True, exist_ok=True)

        # Definir subpastas
        self.e1_dir = self.base_output / "E1" / "extractions"
        self.e2_dir = self.base_output / "E2" / "deontic_maps"
        self.e3_dir = self.base_output / "E3" / "fol_formulas"
        self.compilation_log = self.base_output / "compilation_logs.json"

    def create_structure(self) -> None:
        """Cria a estrutura de diretórios."""
        for dir_path in [self.e1_dir, self.e2_dir, self.e3_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Criado: {dir_path}")

    def initialize_compilation_log(self) -> None:
        """Inicializa o arquivo de log de compilações."""
        log_structure = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "compilations": []
        }

        # Se o arquivo existe, carrega o log existente
        if self.compilation_log.exists():
            with open(self.compilation_log, encoding='utf-8') as f:
                log_structure = json.load(f)
            log_structure["last_updated"] = datetime.now().isoformat()

        with open(self.compilation_log, 'w', encoding='utf-8') as f:
            json.dump(log_structure, f, ensure_ascii=False, indent=2)

        print(f"[OK] Log de compilações inicializado: {self.compilation_log}")

    def log_compilation(self, contract_id: str, deontic_map: Dict[str, Any],
                       fol_formula: Dict[str, Any], status: str = "success",
                       error_msg: str = None) -> None:
        """
        Registra uma compilação E2→E3.

        Args:
            contract_id: ID do contrato (ex: "contrato_1")
            deontic_map: Mapa deôntico (E2)
            fol_formula: Fórmula FOL (E3)
            status: "success" ou "error"
            error_msg: Mensagem de erro (se houver)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "contract_id": contract_id,
            "status": status,
            "deontic_map_file": f"{contract_id}_deontic_map.json",
            "fol_formula_file": f"{contract_id}_fol_formula.json",
            "num_clauses": len(deontic_map.get("clausulas", [])) if deontic_map else 0,
            "num_deontic_rules": len(deontic_map.get("regras_deonticas", [])) if deontic_map else 0,
            "num_fol_formulas": len(fol_formula.get("formulas", [])) if fol_formula else 0,
            "error": error_msg
        }

        # Carregar log existente
        if self.compilation_log.exists():
            with open(self.compilation_log, encoding='utf-8') as f:
                log_data = json.load(f)
        else:
            log_data = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "compilations": []
            }

        log_data["compilations"].append(log_entry)
        log_data["last_updated"] = datetime.now().isoformat()

        # Salvar log atualizado
        with open(self.compilation_log, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    def migrate_existing_files(self) -> None:
        """Migra arquivos existentes para a nova estrutura."""
        # Procurar por arquivos E2 e E3 na raiz de output
        e2_files = list(self.base_output.glob("*E2*.json"))
        e3_files = list(self.base_output.glob("*E3*.json"))

        for file in e2_files:
            dest = self.e2_dir / file.name
            if not dest.exists():
                shutil.move(str(file), str(dest))
                print(f"[MOVE] Migrado E2: {file.name}")

        for file in e3_files:
            dest = self.e3_dir / file.name
            if not dest.exists():
                shutil.move(str(file), str(dest))
                print(f"[MOVE] Migrado E3: {file.name}")

    def get_summary(self) -> Dict[str, Any]:
        """Retorna um resumo da estrutura criada."""
        return {
            "base_output": str(self.base_output),
            "e1_extractions": str(self.e1_dir),
            "e2_deontic_maps": str(self.e2_dir),
            "e3_fol_formulas": str(self.e3_dir),
            "compilation_logs": str(self.compilation_log),
            "e2_files": len(list(self.e2_dir.glob("*.json"))),
            "e3_files": len(list(self.e3_dir.glob("*.json")))
        }


def main():
    """Executa o setup da estrutura."""
    print("=" * 70)
    print("ContractFOL — Setup de Estrutura de Output")
    print("=" * 70)

    manager = OutputStructureManager()

    print("\n[1] Criando estrutura de diretórios...")
    manager.create_structure()

    print("\n[2] Inicializando log de compilações...")
    manager.initialize_compilation_log()

    print("\n[3] Migrando arquivos existentes...")
    manager.migrate_existing_files()

    print("\n" + "=" * 70)
    print("Resumo da Estrutura:")
    print("=" * 70)
    summary = manager.get_summary()
    for key, value in summary.items():
        print(f"{key:20s}: {value}")

    print("\n[DONE] Setup completo!")
    print("\nPróximos passos:")
    print("  1. Atualize o pipeline para salvar E2 em:", manager.e2_dir)
    print("  2. Atualize o pipeline para salvar E3 em:", manager.e3_dir)
    print("  3. Use log_compilation() para registrar compilações E2 -> E3")


if __name__ == "__main__":
    main()
