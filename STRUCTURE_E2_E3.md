# Estrutura de Output E2 → E3 do Pipeline ContractFOL

## Resumo

O pipeline ContractFOL reorganizou a estrutura de saída para melhorar rastreabilidade:

```
output/
├── E1/
│   └── extractions/          # Extração de cláusulas (E1)
├── E2/
│   ├── deontic_maps/         # Mapas deônticos (E2)
│   └── deontic_maps_logs/    # Logs de processamento E2
├── E3/
│   ├── fol_formulas/         # Fórmulas FOL (E3)
│   └── fol_formulas_logs/    # Logs de processamento E3
└── compilation_logs.json     # Log central de compilações E2→E3
```

## Arquivos de Output

### E1 - Extração de Cláusulas
**Diretório:** `output/E1/extractions/`

```json
{
  "timestamp": "20260328_135507",
  "etapa": "E1 — Pré-processamento",
  "arquivo": "contrato_1.txt",
  "titulo": "contrato_1",
  "partes": ["Empresa Alpha Ltda", "Serviços Beta ME"],
  "contratante": "Empresa Alpha Ltda",
  "contratado": "Serviços Beta ME",
  "clausulas": [
    {
      "id": "CL_1",
      "numero": "1",
      "secao": "OBJETO",
      "texto": "O presente instrumento tem por objeto..."
    }
  ]
}
```

### E2 - Mapas Deônticos
**Diretório:** `output/E2/deontic_maps/`

```json
{
  "timestamp": "20260328_140000",
  "etapa": "E2 — Mapeamento Deôntico",
  "contrato_id": "contrato_1",
  "clausulas": [...],
  "regras_deonticas": [
    {
      "clausula_id": "CL_1",
      "tipo": "obrigacao|permissao|proibicao",
      "sujeito": "CONTRATADA",
      "acao": "executar servicos",
      "condicoes": ["equipamentos disponiveis"],
      "penalidades": ["multa contratual"]
    }
  ]
}
```

### E3 - Fórmulas FOL
**Diretório:** `output/E3/fol_formulas/`

```json
{
  "timestamp": "20260328_140500",
  "etapa": "E3 — Formalização FOL",
  "contrato_id": "contrato_1",
  "formulas": [
    {
      "clausula_id": "CL_1",
      "tipo_deontico": "obrigacao",
      "formula_fol": "forall x . (Entidade(x) AND Contratada(x) AND EquipamentosDisponiveis() -> Obrigacao(ExecutarServicos(x)))",
      "satisfiavel": true,
      "confianca": 0.95
    }
  ]
}
```

## Log de Compilações E2 → E3

**Arquivo:** `output/compilation_logs.json`

Mantém histórico de todas as compilações:

```json
{
  "version": "1.0",
  "created_at": "2026-03-28T14:00:00",
  "last_updated": "2026-03-28T15:30:00",
  "compilations": [
    {
      "timestamp": "2026-03-28T15:30:00.123456",
      "contract_id": "contrato_1",
      "status": "success",
      "deontic_map_file": "contrato_1_deontic_map.json",
      "fol_formula_file": "contrato_1_fol_formula.json",
      "num_clauses": 15,
      "num_deontic_rules": 42,
      "num_fol_formulas": 42,
      "compilation_time_ms": 234.5,
      "error": null,
      "warning": null,
      "metadata": {
        "modelo_llm": "claude-opus",
        "temperatura": 0.3,
        "versao_pipeline": "3.0"
      }
    }
  ],
  "statistics": {
    "total": 10,
    "successful": 8,
    "errors": 2,
    "total_clauses": 150,
    "total_deontic_rules": 420,
    "total_fol_formulas": 418
  }
}
```

## Uso no Pipeline

### Inicializar o Logger

```python
from src.contractfol.contractfol.core.compilation_logger import get_logger

logger = get_logger()
```

### Registrar Compilação Bem-Sucedida

```python
import time

start_time = time.time()

# ... processar contrato ...
deontic_map = {...}
fol_formula = {...}

end_time = time.time()
compilation_time_ms = (end_time - start_time) * 1000

logger.log_success(
    contract_id="contrato_1",
    deontic_map=deontic_map,
    fol_formula=fol_formula,
    compilation_time_ms=compilation_time_ms,
    metadata={
        "modelo_llm": "claude-opus",
        "temperatura": 0.3,
        "versao_pipeline": "3.0"
    }
)
```

### Registrar Erro

```python
try:
    # ... processar contrato ...
except Exception as e:
    logger.log_error(
        contract_id="contrato_1",
        error_msg=str(e),
        deontic_map=deontic_map if 'deontic_map' in locals() else None,
        metadata={"fase": "conversao_para_fol"}
    )
```

### Consultar Estatísticas

```python
# Obter estatísticas gerais
stats = logger.get_statistics()
print(f"Total compilacoes: {stats['total']}")
print(f"Bem-sucedidas: {stats['successful']}")
print(f"Formulas FOL geradas: {stats['total_fol_formulas']}")

# Imprimir resumo formatado
logger.print_summary()
```

### Filtrar Compilações

```python
# Compilações de um contrato específico
contrato_logs = logger.get_compilations(contract_id="contrato_1")

# Compilações com erro
error_logs = logger.get_compilations(status="error")

# Ambos
specific_errors = logger.get_compilations(
    contract_id="contrato_1",
    status="error"
)
```

## Integração com Pipeline Existente

Para integrar o logging ao pipeline atual:

1. **No módulo E2 (Mapeamento Deôntico):**
   ```python
   from src.contractfol.contractfol.core.compilation_logger import get_logger

   logger = get_logger()
   # Após gerar mapa deôntico, salvar em output/E2/deontic_maps/
   ```

2. **No módulo E3 (Formalização FOL):**
   ```python
   logger = get_logger()

   # Após processar E2→E3
   logger.log_success(
       contract_id=contrato_id,
       deontic_map=e2_data,
       fol_formula=e3_data,
       compilation_time_ms=tempo_ms
   )
   ```

## Benefícios da Nova Estrutura

- **Rastreabilidade completa:** Cada compilação registrada com timestamp
- **Organização clara:** Cada etapa em seu próprio diretório
- **Estatísticas automáticas:** Contagem de cláusulas, regras e fórmulas
- **Debugging facilitado:** Logs de erro detalhados com rastreamento
- **Análise de performance:** Tempo de compilação registrado para cada contrato
- **Metadados contextuais:** Versão do pipeline, modelo LLM, parâmetros utilizados

## Exemplo de Análise de Logs

```python
import json
from pathlib import Path

log_file = Path("src/contractfol/contractfol/data/output/compilation_logs.json")

with open(log_file) as f:
    logs = json.load(f)

# Compilações lentas
slow_compilations = [
    c for c in logs["compilations"]
    if c.get("compilation_time_ms", 0) > 1000
]
print(f"Compilacoes lentes (>1s): {len(slow_compilations)}")

# Taxa de sucesso
success_rate = logs["statistics"]["successful"] / logs["statistics"]["total"]
print(f"Taxa de sucesso: {success_rate*100:.1f}%")

# Média de regras por contrato
avg_rules = logs["statistics"]["total_deontic_rules"] / logs["statistics"]["total"]
print(f"Media de regras por contrato: {avg_rules:.1f}")
```
