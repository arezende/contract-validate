# ContractFOL v3

Pipeline neurossimbólico para detecção de defeitos em contratos comerciais.
Dissertação de mestrado — PESC/COPPE/UFRJ.

**Baseline:** *Better Call CLAUSE* (Choudhury et al., Findings of EACL 2026; arXiv:2511.00340)  
**Exemplar metodológico:** VERUS-LM (Callewaert, Vandevelde & Vennekens; arXiv:2501.14540)

---

## Visão geral

O pipeline tem dois braços que compartilham toda a infraestrutura (ingestão, LLM, métricas) e diferem apenas no passo de predição:

```
Corpus CLAUSE (CUAD + ContractNLI)
         │
         ├─── Braço LLM-only  ──► prompts exatos do artigo ──► veredito direto
         │
         └─── Braço neurossimbólico
                  │
                  ▼
            NL → Símbolos (LLM)
                  │
                  ▼
            Símbolos → NormElements / RIN (LLM)
                  │
                  ▼
            RIN → Z3 (compilador determinístico, zero LLM)
                  │
                  ▼
            check_sat ──► UNSAT = defeito detectado
                  │
                  ▼
            unsat_core ──► span + explicação auditável
```

Essa separação torna H₁ um controle limpo: a comparação isola o efeito do raciocínio simbólico, não uma diferença de infraestrutura.

---

## Hipóteses

| ID | Enunciado | Como se mede |
|----|-----------|--------------|
| **H₁** | O braço neurossimbólico supera o LLM-only na detecção de defeitos | `arms/neurosymbolic` vs. `arms/llm_only`, mesmo dado, mesmas métricas |
| **H₂** | Modelos de raciocínio superam modelos padrão como tradutores NL→FOL | Trocar o modelo em `nl2fol/`; contrastar `is_reasoning: true/false`; taxa de SAT espúrio nos originais |
| **H₃** | O refinamento CT3 melhora a qualidade da formalização | Ligar/desligar `solver/refine.py`; ablação sem / só sintático / sintático+semântico |

---

## Estrutura do repositório

```
contractfol/
├── config/
│   ├── models.yaml          # registry de 9 LLMs com is_reasoning flag
│   ├── experiment.yaml      # configuração de runs (braço, modelos, categorias, L1/L2)
│   └── prompts/             # prompts genéricos (sem exemplos do CLAUSE)
├── corpus/
│   ├── schema.py            # DiscrepancyInstance (Pydantic)
│   ├── ingest.py            # parser do metadata JSON do CLAUSE (FIELD_MAP configurável)
│   ├── sample.py            # amostragem estratificada + split dev/test congelado
│   └── fixtures.py          # instâncias sintéticas para testes (10 células cobertas)
├── kb/
│   ├── mine_citations.py    # conjunto fechado de citações legais (dimensão legal only)
│   ├── axioms.py            # 8 axiomas Z3 auditáveis (FCRA, UCC, WARN, FMLA, GDPR, FAA)
│   └── store.py             # KB store com tabela de proveniência
├── llm/
│   ├── interface.py         # generate(prompt, model_alias) → str  (async + sync)
│   ├── registry.py          # carrega models.yaml; list_models(); is_reasoning_model()
│   ├── cache.py             # cache em disco + retry 2/4/8/16s + parser JSON robusto
│   └── adapters/
│       ├── openai_compatible.py   # GPT-4o, LLaMA/Groq, DeepSeek, Kimi, Qwen
│       └── gemini.py              # Gemini 2.0/2.5 (SDK nativo)
├── rin/
│   └── schema.py            # Symbol · NormElement · RIN (Pydantic, serialização JSONL)
├── nl2fol/
│   ├── prompts.py           # prompts genéricos com exemplo fictício (anti-circularidade)
│   ├── symbols.py           # Step 4.1 — extração de Symbol via LLM
│   ├── formulas.py          # Step 4.2 — extração de NormElement → RIN via LLM
│   └── compile_z3.py        # compilador determinístico RIN → Z3 (ZERO chamadas de LLM)
├── solver/
│   ├── verify.py            # check_sat + protocolo dos dois UNSATs + classificação in-text/legal
│   ├── core.py              # unsat_core → span + explicação auditável (sem LLM)
│   ├── refine.py            # CT3: refinamento sintático + semântico (só no original_text)
│   └── completeness.py      # omissão: checagem de completude (mecanismo separado do SAT)
├── arms/
│   ├── llm_only.py          # 6 prompts CLAUSE (eval1/2/3 × L1/L2) + LLMPrediction
│   └── neurosymbolic.py     # orquestrador neurossimbólico (stub — Etapa 6+)
└── metrics/
    ├── eval1_2.py           # Accuracy/Precision/Recall/F1 por exact match
    ├── location.py          # location_alignment via grafo de componentes conexas (networkx)
    ├── explanation.py       # juiz duplo GPT-4o + Gemini-2.5 (temp=0.1, 4 dimensões 0–5)
    └── law_match.py         # comparação semântica de citação via Gemini (paralegal judge)
```

---

## Instalação

```bash
pip install -e .
python -m spacy download en_core_web_trf
```

Versões de métricas **pinadas** (divergir invalida a comparação com o artigo):

```
rouge-score==0.1.2
nltk==3.8.1
bert-score==0.3.13
networkx==3.1
```

### Variáveis de ambiente

| Variável | Provedor |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI (GPT-4o, GPT-4o-mini) |
| `GROQ_API_KEY` | Groq (LLaMA-3.3-70b) |
| `DEEPSEEK_API_KEY` | DeepSeek (deepseek-chat, deepseek-reasoner) |
| `MOONSHOT_API_KEY` | Kimi / Moonshot |
| `DASHSCOPE_API_KEY` | Qwen via Alibaba DashScope |
| `GOOGLE_API_KEY` | Gemini 2.0/2.5 |

---

## Modelos registrados

| Alias | Modelo | Adaptador | `is_reasoning` |
|-------|--------|-----------|----------------|
| `gpt-4o` | gpt-4o-2024-08-06 | openai_compatible | false |
| `gpt-4o-mini` | gpt-4o-mini-2024-07-18 | openai_compatible | false |
| `gemini-2.0-flash` | gemini-2.0-flash-exp | gemini | false |
| `gemini-2.5-flash` | gemini-2.5-flash-002 | gemini | false |
| `llama-3.3-70b` | meta-llama/llama-3.3-70b-instruct | openai_compatible | false |
| `qwen` | qwen-max | openai_compatible | false |
| `deepseek` | deepseek-chat | openai_compatible | false |
| `deepseek-reasoner` | deepseek-reasoner | openai_compatible | **true** |
| `kimi` | moonshot-v1-128k | openai_compatible | false |

O flag `is_reasoning` é o eixo de contraste de H₂.

---

## Corpus

**CLAUSE** (acesso controlado — solicitar via formulário oficial):
- CUAD: 4.711 contratos / 12.869 perturbações
- ContractNLI: 2.803 contratos / 11.086 perturbações
- Total: 23.955 perturbações validadas

**Taxonomia** — 5 tipos × 2 dimensões = 10 categorias:

| Tipo | in-text | legal |
|------|---------|-------|
| Ambiguity | ✓ | ✓ |
| Inconsistency | ✓ | ✓ |
| Misaligned Terminology | ✓ | ✓ |
| Omission | ✓ | ✓ |
| Structural Flaw | ✓ | ✓ |

---

## Protocolo dos dois UNSATs

UNSAT tem dois significados distintos neste pipeline — distingui-los é central:

| Contexto | UNSAT significa | Ação |
|----------|----------------|------|
| `original_text` (calibração) | Erro do tradutor — contradição espúria | Refinar com CT3 semântico |
| `changed_text` (teste) | Defeito real detectado | Reportar como Eval_1 = "Yes" |

O refinamento semântico (CT3) é aplicado **exclusivamente** no `original_text`. Aplicá-lo no `changed_text` eliminaria exatamente o sinal que se quer detectar.

A taxa de SAT espúrio nos originais é métrica de qualidade do tradutor e alimenta H₂.

---

## KB Legal

8 axiomas Z3 auditáveis com proveniência explícita (estatuto → axioma):

| ID | Estatuto | Tipologia | Restrição Z3 |
|----|----------|-----------|--------------|
| `fcra_dispute_deadline_30` | 15 U.S.C. § 1681i(a)(1)(A) | deadline_limit | `dispute_investigation_days ≤ 30` |
| `fcra_notification_deadline_5` | 15 U.S.C. § 1681i(a)(6)(A) | deadline_limit | `notification_days ≤ 5` |
| `warn_act_notice_60` | 29 U.S.C. § 2102(a) | deadline_limit | `notice_days ≥ 60` |
| `fmla_leave_12_weeks` | 29 U.S.C. § 2612(a)(1) | mandatory_disclosure | `leave_weeks ≥ 12` |
| `gdpr_art33_breach_notification_72h` | GDPR Art. 33 | deadline_limit | `breach_notification_hours ≤ 72` |
| `ucc_2_207_acceptance` | UCC § 2-207 | canonical_definition | `acceptance_with_additional_terms = True` |
| `faa_arbitration_clause_enforceable` | 9 U.S.C. § 2 | canonical_definition | — |
| `ucc_2_207_merchant_terms_deontic` | UCC § 2-207 | deontic_force | v2 only |

**Regra anti-circularidade:** axiomas derivados exclusivamente do texto do estatuto (`scraped_snippet_1/2` ou URL `.gov`/Cornell LII). Nunca do campo `explanation` ou `law_explanation` do CLAUSE.

---

## Métricas (paridade exata com o artigo)

### Eval_1 — Detecção binária
`eval1_metrics(predictions, gold_labels)` → `ClassificationMetrics(accuracy, precision, recall, f1, tp, fp, fn, tn)`

### Eval_2 — Classificação de dimensão
`eval2_metrics(predictions, gold_dimensions)` → `dict["in_text" | "legal" | "macro", ClassificationMetrics]`

### Eval_3 — Span + explicação + citação
- **`location_alignment`**: grafo não-direcionado `G=(V,E)`, aresta sse interseção não-vazia de frases normalizadas; TP = componente com ≥1 GT e ≥1 pred; ROUGE-1/2/L, METEOR, BERTScore (`microsoft/deberta-xlarge-mnli`)
- **`explanation_match`**: juiz duplo GPT-4o + Gemini-2.5, temp=0.1, 4 rubricas (Accuracy/Completeness/Clarity/Legal Reasoning, 0–5) + flag `adequate`
- **`law_match`**: juiz paralegal Gemini-2.5-flash, temp=0.0, score binário

---

## Braço LLM-only

Replica os prompts exatos do apêndice do artigo:

```python
from contractfol.arms.llm_only import run_batch_sync, LLMPrediction
from contractfol.corpus.sample import load_splits

dev, test = load_splits("data/splits/")
predictions = run_batch_sync(
    instances=dev,
    model_aliases=["gpt-4o-mini", "qwen", "deepseek"],
    eval_tasks=["eval1", "eval2", "eval3"],
    prompt_levels=["l1", "l2"],
    max_concurrent=5,
)
```

Os 6 prompts (`eval1_l1/l2`, `eval2_l1/l2`, `eval3_l1/l2`) estão em `arms/llm_only.py::PROMPTS` e marcados com `# NOTE: verify against CLAUSE appendix` — substituir pelo texto exato do artigo quando o acesso for concedido.

---

## Medidas anti-circularidade

1. **Prompting genérico** — nenhum exemplo do CLAUSE nos prompts de tradução
2. **KB do texto estatutário** — nunca do campo `explanation` do CLAUSE
3. **Split test congelado** — calibração de prompt apenas no dev set
4. **Juiz validado** — herda Tabela 8 do CLAUSE (diferenças vs. humano < 0,3)
5. **Corpus independente** — perturbações não criadas pelo autor do pipeline

---

## Subagentes de projeto

Seis agentes especializados em `.claude/agents/`:

| Agente | Quando usar |
|--------|-------------|
| `builder` | Implementar novos módulos seguindo a spec |
| `formalization-qa` | Após qualquer mudança em `nl2fol/`, `solver/`, `rin/` |
| `metric-parity-auditor` | Após qualquer mudança em `metrics/` |
| `circularity-reviewer` | Antes de qualquer experimento ou resultado reportado |
| `results-writer` | Converter saída de experimentos em tabelas ABNT |
| `desk-reject-simulator` | Antes de submeter ao IST |

---

## Referências

- CHOUDHURY, M. R. et al. **Better Call CLAUSE: A Discrepancy Benchmark for Auditing LLMs Legal Reasoning Capabilities.** Findings of EACL 2026, p. 5776–5818. arXiv:2511.00340.
- CALLEWAERT, B.; VANDEVELDE, S.; VENNEKENS, J. **VERUS-LM: a Versatile Framework for Combining LLMs with Symbolic Reasoning.** arXiv:2501.14540, 2025.
- HENDRYCKS, D. et al. **CUAD: An Expert-Annotated NLP Dataset for Legal Contracts.** arXiv:2103.06268, 2021.
- KOREEDA, Y.; MANNING, C. D. **ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts.** EMNLP 2021, p. 7578–7589.
- PAN, L. et al. **Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning.** Findings of EMNLP 2023, p. 3806–3824.
