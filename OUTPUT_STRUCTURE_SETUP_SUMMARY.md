# Resumo: Reorganização da Estrutura de Output E2 ↔ E3

**Data:** 28 de março de 2026
**Status:** ✅ Concluído

---

## O Que Foi Feito

### 1. Criação de Estrutura de Diretórios

```
src/contractfol/contractfol/data/output/
├── E1/
│   └── extractions/              # Cláusulas extraídas de contratos
├── E2/
│   └── deontic_maps/             # Mapas deônticos (normalizados)
├── E3/
│   └── fol_formulas/             # Fórmulas FOL (validáveis com Z3)
└── compilation_logs.json         # Log central de compilações
```

### 2. Sistema de Logging de Compilações E2 → E3

Criado o módulo `src/contractfol/contractfol/core/compilation_logger.py` com:

- **CompilationLogger**: Classe para gerenciar logs de compilação
- **CompilationEntry**: Dataclass para estruturar registros
- **CompilationStatus**: Enum para status (SUCCESS, ERROR, PARTIAL, SKIPPED)

#### Recursos:
- ✅ Registrar compilações bem-sucedidas
- ✅ Registrar erros com rastreamento
- ✅ Estatísticas automáticas (cláusulas, regras, fórmulas)
- ✅ Tempo de compilação (ms)
- ✅ Metadados contextuais (modelo LLM, temperatura, versão)
- ✅ Filtros por contrato e status
- ✅ Resumo visual formatado

### 3. Arquivos de Suporte Criados

#### `setup_output_structure.py`
Script para inicializar a estrutura (já executado):
```bash
python setup_output_structure.py
```

#### `STRUCTURE_E2_E3.md`
Documentação técnica completa com:
- Exemplos de JSON para cada etapa
- Como usar o logger
- Integração com o pipeline
- Análise de logs

#### `examples_compilation_logger.py`
7 exemplos práticos de uso:
```bash
python examples_compilation_logger.py
```

---

## Como Usar

### Integração Básica no Pipeline

```python
from src.contractfol.contractfol.core.compilation_logger import get_logger
import time

logger = get_logger()
start = time.time()

# ... processar E2 → E3 ...

logger.log_success(
    contract_id="contrato_1",
    deontic_map=e2_data,
    fol_formula=e3_data,
    compilation_time_ms=(time.time() - start) * 1000,
    metadata={
        "modelo_llm": "claude-opus",
        "temperatura": 0.3,
        "versao_pipeline": "3.0"
    }
)
```

### Consultar Estatísticas

```python
logger = get_logger()

# Estatísticas gerais
stats = logger.get_statistics()
print(f"Compilacoes: {stats['total']}")
print(f"Sucesso: {stats['successful']}")
print(f"Formulas FOL: {stats['total_fol_formulas']}")

# Resumo formatado
logger.print_summary()
```

### Análise de Logs

```python
# Compilações de um contrato
logs = logger.get_compilations(contract_id="contrato_1")

# Erros
errors = logger.get_compilations(status="error")
for err in errors:
    print(f"{err['contract_id']}: {err['error']}")
```

---

## Estrutura do Log JSON

**Arquivo:** `output/compilation_logs.json`

```json
{
  "version": "1.0",
  "created_at": "2026-03-28T15:26:37",
  "last_updated": "2026-03-28T15:26:42",
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
      "metadata": {...}
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

---

## Próximos Passos para o Pipeline

1. **E1 (Extração):**
   - Salvar em: `output/E1/extractions/{contrato_id}_E1.json`

2. **E2 (Mapeamento Deôntico):**
   - Salvar em: `output/E2/deontic_maps/{contrato_id}_deontic_map.json`
   - Importar logger e registrar compilações

3. **E3 (Formalização FOL):**
   - Salvar em: `output/E3/fol_formulas/{contrato_id}_fol_formula.json`
   - Chamar `logger.log_success()` ou `logger.log_error()`

4. **Relatórios:**
   - Usar `logger.print_summary()` ao final
   - Analisar `compilation_logs.json` para métricas

---

## Benefícios

| Aspecto | Antes | Depois |
|--------|--------|--------|
| **Organização** | Arquivos soltos em output/ | Estrutura clara por etapa |
| **Rastreabilidade** | Nenhuma | Log completo com timestamp |
| **Estatísticas** | Manual/inexistente | Automáticas e centralizadas |
| **Debugging** | Difícil | Erros registrados com contexto |
| **Performance** | Desconhecido | Tempo de compilação medido |
| **Reuso** | N/A | Metadados para análise |

---

## Arquivos Modificados/Criados

```
✅ src/contractfol/contractfol/core/compilation_logger.py    [NOVO]
✅ setup_output_structure.py                                  [NOVO]
✅ examples_compilation_logger.py                             [NOVO]
✅ STRUCTURE_E2_E3.md                                         [NOVO]
✅ OUTPUT_STRUCTURE_SETUP_SUMMARY.md                          [NOVO - este arquivo]
✅ src/contractfol/contractfol/data/output/                   [ESTRUTURA CRIADA]
```

---

## Verificação

A estrutura foi criada com sucesso:

```
src/contractfol/contractfol/data/output/
├── E1/extractions/
├── E2/deontic_maps/
├── E3/fol_formulas/
└── compilation_logs.json (inicializado com estatísticas)
```

Execute para testar:
```bash
python examples_compilation_logger.py
```

---

## Documentação

Para mais detalhes, consulte:
- `STRUCTURE_E2_E3.md` — Documentação técnica completa
- `compilation_logger.py` — Docstrings do código
- `examples_compilation_logger.py` — Exemplos de uso
