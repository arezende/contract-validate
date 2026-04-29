# 🚀 ContractFOL V3 — Guia de Início Rápido

**Status:** ✅ Pronto para uso em produção

---

## 📋 O que é ContractFOL V3?

Um **sistema inteligente de análise de contratos** que usa:
- 🤖 **AI (Google Gemini)** — Para extrair cláusulas e estrutura
- 🔍 **Verificação Formal (Z3)** — Para detectar contradições e inconsistências
- 📐 **Lógica Deôntica** — Para classificar obrigações, proibições, permissões
- 📄 **Relatórios Automáticos** — Markdown com notação deôntica + FOL

---

## ⚡ 5 Passos para Começar

### 1️⃣ Verificar Configuração
```bash
cat .env
```

Deve conter:
```ini
CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA
CONTRACTFOL_LLM=google
CONTRACTFOL_MODEL=gemini-2.0-flash
```

### 2️⃣ Colocar Contratos para Validar
```bash
cp seu_contrato.txt src/contractfol/contractfol/data/input/
# Ou
cp seu_contrato.docx src/contractfol/contractfol/data/input/
# Ou
cp seu_contrato.pdf src/contractfol/contractfol/data/input/
```

### 3️⃣ Executar o Pipeline
```bash
python -m contractfol.contractfol.main
```

### 4️⃣ Verificar os Resultados
```bash
ls src/contractfol/contractfol/data/output/
```

### 5️⃣ Analisar os Relatórios
```bash
# Ver resumo geral
cat src/contractfol/contractfol/data/output/INDICE_GERAL.json

# Ver relatório markdown
cat src/contractfol/contractfol/data/output/relatorio_*.md

# Ver dados estruturados (JSON)
cat src/contractfol/contractfol/data/output/E4/contrato_E4_seu_contrato.json
```

---

## 📊 O Que o Sistema Detecta?

### ✅ Problemas Detectados Automaticamente

| Tipo | Descrição | Exemplo | Severidade |
|------|-----------|---------|-----------|
| **Lacuna Penalidade** | Obrigação sem penalidade | "Deve entregar em 30 dias" — sem multa | MÉDIA |
| **Contradição Deôntica** | Mesmo agente + ação com "sim" e "não" | "Deve usar..." vs "Não pode usar..." | ALTA |
| **Inconsistência Prazo** | Prazos conflitantes entre cláusulas | CL_2: 30 dias vs CL_3: 15 dias | MÉDIA |
| **Omissão Prazo** | Obrigação sem prazo explícito | "Deve entregar" — quando? | BAIXA |
| **Ambiguidade** | Confiança LLM baixa na classificação | Texto não claro | BAIXA |

### 6️⃣ Verificações Formais (V1-V6)

1. **V1 SAT/UNSAT** — Contrato é consistente?
2. **V2 Contradições** — Há conflitos deônticos?
3. **V3 Prazos** — Prazos são consistentes?
4. **V4 Penalidades** — Obrigações têm penalidades?
5. **V5 Prazos Completos** — Todos os prazos definidos?
6. **V6 Razoabilidade** — Valores/prazos são razoáveis?

---

## 📁 Estrutura de Saídas

```
data/output/
├── E1/                      # Cláusulas extraídas
│   ├── contrato_E1_seu_contrato.json
│   └── ...
│
├── E2/                      # Estrutura deôntica
│   ├── contrato_E2_seu_contrato.json (tipo, agente, ação, prazo, valor)
│   └── ...
│
├── E3/                      # Compilação Z3
│   ├── contrato_E3_seu_contrato.json (taxa de sucesso)
│   └── ...
│
├── E4/                      # Análise formal
│   ├── contrato_E4_seu_contrato.json (problemas detectados)
│   └── ...
│
├── E5/                      # Relatórios
│   ├── relatorio_20260328_143620.md
│   └── ...
│
├── MAPA_DEONTICO/          # Rastreabilidade
│   ├── mapa_deontico_seu_contrato.json
│   └── ...
│
├── FOL/                    # Fórmulas lógicas
│   ├── formulas_fol_seu_contrato.json (FOL + Z3)
│   └── ...
│
└── INDICE_GERAL.json      # Resumo de todos os contratos
```

---

## 🔍 Exemplo de Resultado

### Entrada: `contrato_servicos.txt`
```
Contrato de Prestação de Serviços

CLÁUSULA 1: A contratada deve entregar relatório em 30 dias.
CLÁUSULA 2: Atraso incorre multa de 10% do valor mensal.
CLÁUSULA 3: A contratante deve fornecer dados em 5 dias.
CLÁUSULA 4: Contrato vigência de 12 meses.
```

### Saída: `INDICE_GERAL.json`
```json
{
  "data_processamento": "2026-03-28T14:39:15",
  "total_contratos": 1,
  "contratos_sucesso": 1,
  "resumo": [
    {
      "contrato": "contrato_servicos.txt",
      "contratante": "Empresa A",
      "contratado": "Empresa B",
      "clausulas": 4,
      "confianca": "85%",
      "problemas": 1,
      "status": "✅"
    }
  ]
}
```

### Saída: `relatorio_*.md`
```markdown
## Análise Contratual — ContractFOL V3

Contrato: contrato_servicos
Analisadas 4 cláusulas. 3 OK, 1 alerta, 0 erros.

### ⚠️ LACUNA_PENALIDADE
**Cláusula:** CL_3
**Descrição:** Obrigação sem penalidade (contratante deve fornecer dados)

**FOL:** Obrigacao(CONTRATANTE, Fornecer(dados)) ∧ Prazo(5, dias)
**Z3:** contratante_fornecer_5d = Bool('contratante_fornecer_5d')

**Recomendação:** Adicionar penalidade para garantir cumprimento da contratante.
```

---

## 🎯 Casos de Uso

### ✅ Caso 1: Validar Novo Contrato Antes de Assinar
```bash
# Colocar contrato em data/input/
python -m contractfol.contractfol.main
# Ler relatório em data/output/relatorio_*.md
# Tomar decisão baseada em problemas detectados
```

### ✅ Caso 2: Auditar Contratos Existentes
```bash
# Colocar todos os contratos em data/input/
python -m contractfol.contractfol.main
# Ver INDICE_GERAL.json para comparação
# Identificar padrões de problemas
```

### ✅ Caso 3: Extrair Dados Estruturados
```bash
# Após executar pipeline
# E2 contém estrutura deôntica em JSON
# FOL contém fórmulas lógicas + código Z3
# Integrar com seu sistema via JSON
```

---

## 🛠️ Configurações Avançadas

### Alterar Modelo do Gemini
```ini
# .env
CONTRACTFOL_MODEL=gemini-1.5-pro  # Mais potente, mais lento, mais caro
# ou
CONTRACTFOL_MODEL=gemini-1.5-flash  # Mais rápido, mais barato
```

### Ajustar Temperatura (Criatividade)
```ini
# .env
CONTRACTFOL_TEMPERATURE=0.3  # Mais determinístico (recomendado para contratos)
# ou
CONTRACTFOL_TEMPERATURE=0.7  # Padrão (balanceado)
```

### Ver Debug
```bash
# Ativar verbose (salve logs em arquivo)
python -m contractfol.contractfol.main 2>&1 | tee pipeline.log
```

---

## 📊 Interpretando Resultados

### Confiança (0-100%)
- **> 80%** — Excelente confiança LLM ✅
- **60-80%** — Boa confiança ⚠️
- **40-60%** — Confiança média — revisar manualmente
- **< 40%** — Baixa confiança — sempre revisar ❌

### Cobertura Penalidades
- **100%** — Todas obrigações têm penalidades ✅
- **50-99%** — Algumas cobertas — revisar lacunas ⚠️
- **0-50%** — Poucas cobertas — adicionar penalidades ❌

### Problemas Detectados
- **0** — Contrato bem estruturado ✅
- **1-3** — Pequenas inconsistências ⚠️
- **> 3** — Revisar estrutura do contrato ❌

---

## 🔧 Troubleshooting

### Erro: "Chave API inválida"
```bash
# Verificar .env
cat .env | grep CONTRACTFOL_API_KEY

# Testar em Python
python -c "import os; print(os.getenv('CONTRACTFOL_API_KEY'))"

# Se vazio, recriar .env
echo 'CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA' >> .env
```

### Erro: "Módulo não encontrado"
```bash
# Reinstalar dependências
pip install -r requirements.txt
# ou
pip install google-generativeai python-dotenv z3-solver rich pydantic anthropic openai
```

### Erro: "Arquivo não encontrado"
```bash
# Verificar caminho de input
ls src/contractfol/contractfol/data/input/

# Copiar contrato
cp seu_contrato.txt src/contractfol/contractfol/data/input/
```

### Pipeline Lento
- **Causa:** Muitos contratos, timeout do Gemini
- **Solução:** Processar em lotes menores ou usar modelo mais rápido (`gemini-2.0-flash`)

---

## 📚 Documentação Completa

- **GEMINI_SETUP.md** — Configuração detalhada
- **README_V3.md** — Documentação técnica
- **CONCLUSAO_FINAL.md** — Resultados da execução final
- **IMPLEMENTATION_COMPLETE.md** — Status técnico

---

## 🎓 Aprender Mais

### Sobre Deontic Logic
- **Obrigação:** "Deve fazer X" (deverá, é obrigado)
- **Proibição:** "Não pode fazer X" (é vedado, não poderá)
- **Permissão:** "Pode fazer X" (é permitido, poderá)
- **Direito:** "Tem direito a X" (receberá, fará jus)
- **Definição:** "X significa Y" (define termo)
- **Condição:** "Se X então Y" (condicional)

### Sobre First-Order Logic (FOL)
- **Fórmula:** `∀x: P(x) → Q(x)` (Para todo x, se P(x) então Q(x))
- **Solver:** Z3 prova se fórmula é satisfiável (SAT/UNSAT)
- **Contradição:** Quando negação da fórmula também é satisfiável = conflito

---

## 💡 Dicas Úteis

1. **Sempre revisar manualmente** contratos de alto valor
2. **Usar confiança como métrica** — quanto maior, melhor
3. **Agregar resultados** — INDICE_GERAL.json mostra padrões
4. **Iteração** — Re-rodar após fazer correções
5. **Feedback** — Reportar falsos positivos/negativos para melhoria

---

## 🚀 Próximos Passos

1. ✅ Adicionar seus contratos em `data/input/`
2. ✅ Rodar `python -m contractfol.contractfol.main`
3. ✅ Revisar `INDICE_GERAL.json` e `relatorio_*.md`
4. ✅ Validar problemas detectados manualmente
5. ✅ Corrigir contratos baseado em recomendações
6. ✅ Re-rodar para validação

---

## ✅ Status: Pronto para Produção

O sistema está **100% operacional** e testado com sucesso.

**Próximo passo:** Coloque seus contratos em `data/input/` e execute:
```bash
python -m contractfol.contractfol.main
```

Boa sorte! 🎉
