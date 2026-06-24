# Pipeline de Avaliação LLM-Only — ContractFOL v3

Implementação do protocolo de avaliação do benchmark **CLAUSE** (Choudhury et al., EACL 2026,
arXiv:2511.00340) para medir a capacidade de LLMs de detectar, classificar e justificar
discrepâncias em contratos jurídicos norte-americanos.

---

## Visão Geral

O pipeline avalia o modelo sobre **contratos perturbados** (instâncias positivas do CLAUSE).
Cada contrato recebeu uma perturbação sintética controlada; o modelo deve identificar
o problema sem acesso ao documento original.

```
Dataset CLAUSE
     │
     ▼
Amostragem estratificada          ← n instâncias por célula (perturb_type × dimension)
     │
     ▼
Split dev / test (congelado)      ← 70% dev · 30% test
     │
     ▼
┌────────────────────────────────────────────────────────┐
│                   LLM (changed_text)                   │
│                                                        │
│  Eval_1 ─── Detectar   → "Yes" / "No"                 │
│  Eval_2 ─── Classificar → In-text / Outer-law / None  │
│  Eval_3 ─── Justificar  → spans JSON                  │
└────────────────────────────────────────────────────────┘
     │
     ▼
Métricas: F1 (Eval_1/2) · ROUGE/METEOR (Eval_3)
```

---

## Dataset

**Fonte:** CLAUSE benchmark — 35.927 instâncias distribuídas em 10 células:

| `perturb_type` | `dimension` |
|----------------|-------------|
| add / remove / replace / reorder / paraphrase | in_text · legal |

Cada instância contém:
- `original_text` — contrato original (sem perturbação)
- `changed_text` — contrato perturbado (entrada do LLM)
- `dimension` — `in_text` (contradição interna) ou `legal` (contradição com lei)
- `explanation` — descrição da perturbação (não exposta ao modelo)

> **Protocolo:** apenas os 70 contratos do split `dev` são utilizados durante o
> desenvolvimento. O split `test` é congelado e não deve ser carregado antes da
> avaliação final.

---

## Evals

### Eval_1 — Detecção Binária

O modelo lê o `changed_text` e responde "Yes" ou "No".

```
Prompt:
  You are a U.S. contract attorney who answers concisely.

  Please read the legal document below in full.

  Document:
  ```
  {changed_text}
  ```

  Does this document contain any discrepancy? Reply with only "Yes" or "No".
```

**Métricas:** Accuracy · Precision · Recall · F1
(com apenas instâncias positivas, Precision = 1.0; o indicador principal é Recall —
fração dos contratos perturbados que o modelo detecta.)

**Parsing:** resposta começa com "yes" → `True`; qualquer outra coisa → `False`.

---

### Eval_2 — Classificação de Dimensão

O modelo classifica o tipo de discrepância em três categorias.

```
Prompt:
  You are a legal expert specializing in U.S. law. You will read a legal
  document very carefully and classify it into one of the following three
  categories:

  1. In-text contradiction: ...
  2. Outer-law contradiction: ...
  3. No contradiction: ...

  Respond with only one of the labels: "In-text contradiction",
  "Outer-law contradiction", or "No contradiction".
  Do not provide any explanation.

  Document:
  {changed_text}
```

**Mapeamento de rótulos** (case-insensitive, busca por substring):

| Saída do modelo | Classe interna |
|-----------------|---------------|
| "In-text contradiction" / "in-text" / "in_text" | `in_text` |
| "Outer-law contradiction" / "outer-law" / "outer law" | `legal` |
| "No contradiction" / qualquer outra resposta | `none` |

**Métricas:** F1 por classe (`in_text`, `legal`, `none`) + macro-F1.
Como todas as instâncias são positivas, o gold nunca é `none`;
previsões `none` representam falsos negativos de classificação.

> Eval_1 e Eval_2 usam apenas **um nível de prompt** (sem variação L1/L2).

---

### Eval_3 — Extração de Span e Justificativa

O modelo identifica os trechos problemáticos e explica o motivo. Existem
**quatro variantes** (2 dimensões × 2 níveis de prompt):

| Variante | Dimensão | Nível |
|----------|----------|-------|
| `eval3_intext_l1` | in_text | L1 — zero-shot |
| `eval3_intext_l2` | in_text | L2 — one-shot |
| `eval3_legal_l1` | legal | L1 — zero-shot |
| `eval3_legal_l2` | legal | L2 — one-shot |

O prompt informa ao modelo a dimensão da contradição e solicita um array JSON:

```json
[
  {
    "text": "trecho exato extraído do contrato",
    "explanation": "o que contradiz e por quê",
    "law": "estatuto violado (somente legal)"
  }
]
```

Se o modelo não encontrar discrepância, deve retornar `[]`.

**Métricas de Location Alignment** (calculadas sobre instâncias positivas):

| Métrica | Descrição |
|---------|-----------|
| ROUGE-1 | Sobreposição de unigramas entre span predito e `changed_text` |
| ROUGE-2 | Sobreposição de bigramas |
| ROUGE-L | Subsequência comum mais longa |
| METEOR | Alinhamento semântico com stemming e sinônimos |

Modelos que não extraem nenhum span (lista vazia) recebem score 0 em todas as métricas
(contabilizados como falsos negativos).

> **Pacotes:** rouge-score 0.1.2 · nltk 3.8.1

---

## Configuração de Inferência

Parâmetros fixos seguindo o Apêndice A.2 do artigo CLAUSE:

| Parâmetro | OpenAI / Groq / DeepSeek | Gemini |
|-----------|--------------------------|--------|
| `temperature` | 0.2 | 0.2 |
| `top_p` | 1.0 | 0.95 |
| `max_tokens` | 8192 | 8192 |

Modelos disponíveis (`config/models.yaml`):

| Alias | Provedor | Modelo |
|-------|----------|--------|
| `gpt-4o` | OpenAI | gpt-4o-2024-08-06 |
| `gpt-4o-mini` | OpenAI | gpt-4o-mini-2024-07-18 |
| `gemini-2.0-flash` | Google | gemini-2.0-flash-exp |
| `gemini-2.5-flash` | Google | gemini-2.5-flash-002 |
| `llama-3.3-70b` | Groq | meta-llama/llama-3.3-70b-instruct |
| `deepseek` | DeepSeek | deepseek-chat |
| `deepseek-reasoner` | DeepSeek | deepseek-reasoner |
| `qwen` | Alibaba | qwen-max |
| `kimi` | Moonshot | moonshot-v1-128k |

---

## Execução

```bash
# Configuração mínima (usa experiment.yaml)
python experiments/run_llm_only.py

# Sobrepondo modelo e número de instâncias
python experiments/run_llm_only.py --models gpt-4o-mini --n-per-cell 7

# Dry-run (sem chamar APIs)
python experiments/run_llm_only.py --dry-run

# Múltiplos modelos
python experiments/run_llm_only.py --models gpt-4o-mini gemini-2.5-flash --tasks eval1 eval2
```

**Variáveis de ambiente necessárias** (arquivo `.env` na raiz ou exportadas):

```
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...
GROQ_API_KEY=gsk_...
DEEPSEEK_API_KEY=sk-...
```

---

## Saídas

```
outputs/llm_only/
├── {run_id}_predictions.jsonl   # uma predição por linha (LLMPrediction)
└── {run_id}_summary.json        # métricas agregadas por (modelo × task × level)
```

Cada linha do JSONL contém:

```json
{
  "instance_id": "clause_001",
  "model_alias": "gpt-4o-mini",
  "eval_task": "eval1",
  "prompt_level": "l1",
  "answer": true,
  "dimension": null,
  "location": null,
  "explanation": null,
  "law_citation": null,
  "spans": null,
  "raw_response": "Yes"
}
```

---

## Estrutura de Código

```
src/contractfol/
├── arms/
│   └── llm_only.py          # prompts, parsing, run_batch_sync
├── corpus/
│   ├── ingest.py            # carregamento do dataset CLAUSE
│   ├── sample.py            # amostragem estratificada, splits dev/test
│   └── schema.py            # DiscrepancyInstance (Pydantic)
├── llm/
│   ├── interface.py         # generate() — ponto de entrada unificado
│   ├── registry.py          # config/models.yaml → alias → parâmetros
│   └── adapters/
│       ├── openai_compatible.py
│       └── gemini.py        # google-genai SDK v1+ (client.aio)
├── metrics/
│   ├── eval1_2.py           # ClassificationMetrics, eval1_metrics, eval2_metrics
│   └── eval3.py             # LocationAlignmentMetrics, location_alignment
└── config/
    ├── models.yaml
    └── experiment.yaml

experiments/
└── run_llm_only.py          # CLI principal
```

---

## Salvaguardas de Protocolo

- **Split test congelado:** `load_test_split_with_warning()` emite aviso proeminente;
  o split `test` nunca deve ser carregado antes de congelar o sistema.
- **Dataset nunca commitado:** `data/` está no `.gitignore`.
- **Sem prompts com exemplos do CLAUSE:** os prompts não contêm instâncias do dataset;
  os exemplos one-shot (L2) são sintéticos e independentes.
- **Instâncias negativas removidas:** o pipeline avalia apenas contratos perturbados
  (positivos). Negativos artificiais (`changed_text = original_text`) foram eliminados
  para não enviesar os prompts do Eval_3.
