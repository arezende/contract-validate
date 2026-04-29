# ContractFOL V3 — Análise Intra-Contrato Neurossimbólica

## 🎯 Objetivo

Analisar **um contrato por vez**, detectando e formalizando:
- ✅ **Contradições internas** (obrigações conflitantes)
- ✅ **Inconsistências de prazo** (prazos incompatíveis)
- ✅ **Lacunas** (obrigações sem penalidade)
- ✅ **Ambiguidades** (baixa confiança do LLM)
- ✅ **Mapa deôntico** (visão completa por agente)

## 📊 Arquitetura: 5 Estágios (E1-E5)

```
E1: Pré-processamento → Extrai e segmenta cláusulas
    ↓
E2: Extração Estruturada → LLM → JSON (agente, ação, prazo, etc.)
    ↓
E3: Compilação Z3 → Monta Solver com todas as restrições
    ↓
E4: Análise Formal → 6 verificações (V1-V6)
    │   V1: Consistência geral (SAT/UNSAT)
    │   V2: Contradições deônticas
    │   V3: Inconsistência de prazos
    │   V4: Cobertura de penalidades
    │   V5: Completude de prazos
    │   V6: Razoabilidade
    ↓
E5: Relatório → Terminal (Rich) + Markdown exportado
```

## 🚀 Uso

### CLI

```bash
# Analisar um contrato
python -m contractfol.contractfol.main tests/contrato_problemas.txt

# Ou com caminho completo
python -m contractfol.contractfol.main /path/to/meu_contrato.txt
```

### Python API

```python
from pathlib import Path
from contractfol.contractfol import (
    preprocessar,
    extrair_contrato,
    compilar_extracao,
    analisar_contrato,
    gerar_relatorio,
)

# E1
contrato = preprocessar(Path("contrato.txt"))

# E2
extracao = extrair_contrato(contrato)

# E3
solver, formulas, ns = compilar_extracao(extracao)

# E4
analise = analisar_contrato("contrato.txt", extracao, solver)

# E5
relatorio = gerar_relatorio("contrato.txt", analise, extracao)

print(f"✅ {relatorio.estatisticas['total_clausulas']} cláusulas")
print(f"🔴 {relatorio.estatisticas['total_problemas']} problemas")
```

## 📁 Estrutura de Diretórios

```
contractfol/
├── main.py                    # CLI
├── config.py                  # Configurações
├── models/
│   ├── enums.py              # Enumerações (TipoDeontico, Severidade, etc.)
│   └── schemas.py            # Pydantic models (E1-E5 outputs)
├── core/
│   ├── e1_preprocessor.py    # Segmentação de cláusulas
│   ├── e2_extractor.py       # Extração via LLM → JSON
│   ├── e3_compiler.py        # Compilação Z3
│   ├── e4_analyzer.py        # 6 verificações (V1-V6)
│   └── e5_reporter.py        # Relatório
├── prompts/
│   └── extraction.py         # Few-shot examples + system prompt
├── tests/
│   └── contrato_problemas.txt  # Contrato de teste com defeitos injetados
└── data/
    ├── input/                # Contratos para análise
    └── output/               # Relatórios gerados
```

## 🧪 Defeitos Injetados no Contrato de Teste

O arquivo `tests/contrato_problemas.txt` contém **5 defeitos propostos**:

| # | Tipo | Cláusulas | Descrição |
|---|------|-----------|-----------|
| 1 | Contradição deôntica | CL_3.3 vs CL_4.2 | Proíbe pessoal permanente vs permite pessoal permanente |
| 2 | Inconsistência prazo | CL_2.1 vs CL_3.1 | Repasse 30d depende de PC, PC é 90d |
| 3 | Lacuna penalidade | CL_2.2 | Obrigação do COB sem penalidade |
| 4 | Lacuna penalidade | CL_2.3 | Obrigação do COB sem penalidade |
| 5 | Lacuna penalidade | CL_3.2 | Obrigação da Confederação sem penalidade |

## ⚙️ Configuração

Edite `config.py`:

```python
LLM_PROVIDER = "anthropic"  # ou "openai"
LLM_MODEL = "claude-sonnet-4-20250514"
Z3_TIMEOUT_MS = 30000
PRAZO_RAZOAVEL_DIAS = 365
```

Variáveis de ambiente:

```bash
export CONTRACTFOL_LLM=anthropic
export CONTRACTFOL_MODEL=claude-sonnet-4-20250514
export CONTRACTFOL_API_KEY=sk-...
```

## 📋 Saída Esperada

### E1 — Pré-processamento
```
📄 E1 — Pré-processamento
  📄 Texto extraído: 3245 caracteres
  ✂️  Cláusulas segmentadas: 7
  🤝 Partes detectadas: COB, Confederação, CBAt
```

### E4 — Análise Formal
```
🔍 E4 — Análise Formal
  V1 Consistência geral...      ❌ UNSAT
  V2 Contradições deônticas... ❌ 1 conflito
  V3 Consistência de prazos...  ⚠️  1 alerta
  V4 Cobertura penalidades...   🟡 3 sem penalidade
  V5 Completude de prazos...    ✅ OK
  V6 Razoabilidade...           ✅ OK
```

### E5 — Relatório
```
📋 E5 — Relatório de Análise Contratual

Contrato: contrato_problemas
Data: 2026-03-26 14:30

Resumo: Analisadas 7 cláusulas. 3 OK, 3 alertas, 1 erro.
Cobertura penalidades: 50%
```

## 📄 Exportação Markdown

Relatórios exportados em `data/output/relatorio_YYYYMMDD_HHMMSS.md`

Contém:
- Tabela com status de cada cláusula
- Lista detalhada de problemas com sugestões
- Estatísticas finais

## ✅ Checklist de Validação

- [x] E0: Estrutura + schemas + config
- [x] E1: Segmentação → 7 cláusulas extraídas
- [x] E2: Extração LLM → JSON estruturado
- [x] E3: Compilação Z3 → Solver montado
- [x] E4-V1: Consistência geral → UNSAT
- [x] E4-V2: Contradições deônticas → CL_3.3 vs CL_4.2
- [x] E4-V3: Consistência prazos → CL_2.1 vs CL_3.1
- [x] E4-V4: Cobertura penalidades → 3 lacunas
- [x] E4-V5: Completude prazos → OK
- [x] E4-V6: Razoabilidade → OK
- [x] E5: Relatório terminal + Markdown
- [x] main.py: CLI funcional

## 🔗 Referências

- Plano: `CONTRACTFOL_IMPLEMENTATION_PLAN_V3.md`
- Dissertação: Validação Neurossimbólica de Contratos Interinstitucionais
- Autor: Anderson Rezende (COPPE/UFRJ)
