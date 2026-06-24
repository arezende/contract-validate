# Estrutura do Dataset CLAUSE

Dataset do benchmark **CLAUSE** (Choudhury et al., EACL 2026, arXiv:2511.00340),
utilizado no ContractFOL v3 para avaliar a capacidade de LLMs de detectar discrepâncias
em contratos jurídicos norte-americanos.

> **Acesso controlado:** os arquivos do dataset nunca são commitados.
> `data/` está no `.gitignore`. Solicite acesso aos autores do artigo.

---

## Localização no Repositório

```
data/
├── raw/
│   └── clause/
│       └── datasets/              ← diretório raiz passado em --data
│           ├── CUAD_Dataset/      ← contratos da base CUAD
│           │   ├── Ambiguities/
│           │   │   └── *.json
│           │   ├── Inconsistencies/
│           │   │   └── *.json
│           │   ├── Misaligned_Terminology/
│           │   │   └── *.json
│           │   ├── Omissions/
│           │   │   └── *.json
│           │   └── Structural_Flaws/
│           │       └── *.json
│           └── NLI_Dataset/       ← contratos derivados de NLI
│               └── (mesma estrutura de subdiretórios)
└── splits/
    ├── dev.jsonl                  ← split de desenvolvimento (gerado automaticamente)
    └── test.jsonl                 ← split de teste (congelado após primeira geração)
```

---

## Formato Bruto (JSON)

Cada arquivo `.json` contém um array de objetos de contrato:

```json
[
  {
    "file_name": "COMPANY_20210101.txt",
    "perturbation": [
      {
        "type": "Ambiguities - In Text Contradiction",
        "original_text": "O texto original do contrato, sem perturbação...",
        "changed_text":  "O texto perturbado do contrato...",
        "explanation":   "Descrição da perturbação introduzida.",
        "justification": "Por que isso constitui uma discrepância.",
        "location":               "Section 3.1",
        "contradicted_location":  "Section 7.2",
        "contradicted_text":      "Trecho que é contradito...",
        "contradiction_exists":   "YES",

        "contradicted_law":   "(somente dimensão legal)",
        "law_citation":       "Fair Labor Standards Act, 29 U.S.C. § 207(a)(1)",
        "law_url1":           "https://...",
        "law_url2":           "https://...",
        "scraped_snippet_1":  "Texto do estatuto...",
        "scraped_snippet_2":  "Texto do estatuto (alternativo)..."
      }
    ]
  }
]
```

Um arquivo pode conter múltiplos objetos de contrato; cada perturbação gera
uma instância independente.

---

## Esquema Canônico (`DiscrepancyInstance`)

Após a ingestão, cada perturbação é representada por um `DiscrepancyInstance`:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `instance_id` | `str` | ✅ | Identificador único: `{categoria}_{stem}[_c{ci}]_p{pi}` |
| `source_dataset` | `"cuad"` \| `"nli"` | ✅ | Inferido do diretório pai |
| `perturb_type` | ver tabela abaixo | ✅ | Tipo de perturbação |
| `dimension` | `"in_text"` \| `"legal"` | ✅ | Dimensão da contradição |
| `original_text` | `str` | ✅ | Contrato original (sem perturbação) |
| `changed_text` | `str` | ✅ | Contrato perturbado — **entrada do LLM** |
| `explanation` | `str` | ✅ | Justificativa GT (não exposta ao modelo) |
| `location` | `str` \| `None` | — | Seção onde a perturbação foi inserida |
| `contradicted_location` | `str` \| `None` | — | Seção que é contradita |
| `contradicted_text` | `str` \| `None` | — | Trecho contradito |
| `contradicted_law` | `str` \| `None` | — | (legal) lei contradita |
| `law_citation` | `str` \| `None` | — | (legal) citação formal do estatuto |
| `law_url1` / `law_url2` | `str` \| `None` | — | (legal) URLs do estatuto |
| `scraped_snippet_1` / `_2` | `str` \| `None` | — | (legal) texto do estatuto — fonte legítima para KB |
| `gold_label` | `bool` | ✅ | Sempre `True` por construção (instâncias perturbadas) |

---

## Tipos de Perturbação (`perturb_type`)

| Valor interno | Campo `type` no JSON (exemplos) | Descrição |
|---------------|----------------------------------|-----------|
| `ambiguity` | "Ambiguities - In Text Contradiction" | Linguagem vaga ou com múltiplas interpretações |
| `inconsistency` | "Inconsistency - Legal" | Provisões contraditórias |
| `misaligned_terminology` | "Misaligned Terminology - In Text" | Termos usados de forma inconsistente |
| `omission` | "Omissions - Legal" | Cláusula obrigatória ausente |
| `structural_flaw` | "Structural Flaws - In Text Contradiction" | Problema de estrutura ou referência cruzada |

---

## Dimensões (`dimension`)

| Valor | Significado |
|-------|-------------|
| `in_text` | A contradição é interna ao documento (uma parte contradiz outra) |
| `legal` | Uma cláusula contradiz lei federal, estadual ou municipal dos EUA |

---

## Células de Estratificação

O dataset é organizado em **10 células** (`perturb_type` × `dimension`):

|  | `in_text` | `legal` |
|--|-----------|---------|
| `ambiguity` | ✅ | ✅ |
| `inconsistency` | ✅ | ✅ |
| `misaligned_terminology` | ✅ | ✅ |
| `omission` | ✅ | ✅ |
| `structural_flaw` | ✅ | ✅ |

O artigo CLAUSE reporta **35.927 instâncias** no total distribuídas nessas células.

---

## Fontes de Contratos

| Dataset | Descrição |
|---------|-----------|
| **CUAD** | Contract Understanding Atticus Dataset — 510 contratos comerciais reais anotados por advogados |
| **NLI** | Contratos derivados de pares de inferência de linguagem natural |

---

## Pipeline de Ingestão

```
data/raw/clause/datasets/
        │
        ▼
load_instances(path)          ← corpus/ingest.py
        │  rglob("*.json")
        │  para cada arquivo:
        │    infer source_dataset   (CUAD_Dataset → "cuad", NLI_Dataset → "nli")
        │    infer category          (nome do diretório pai: "Ambiguities", etc.)
        │    para cada perturbation:
        │      parse type field      → (perturb_type, dimension)
        │      build instance_id     → "{category}_{stem}_p{idx}"
        │      coerce law_url1/2     (pode chegar como list[str])
        │
        ▼
list[DiscrepancyInstance]     ← 35.927 instâncias (dataset completo)
        │
        ▼
stratified_sample(n_per_cell=50)   ← corpus/sample.py
        │  até 50 instâncias por célula
        │  seed=42 (determinístico)
        │
        ▼
make_splits(test_fraction=0.30)
        │  70% → dev.jsonl
        │  30% → test.jsonl
        │  estratificado por célula
        │
        ▼
data/splits/dev.jsonl   ← ≤ 350 instâncias (10 células × 35)
data/splits/test.jsonl  ← ≤ 150 instâncias (10 células × 15)
```

---

## Splits JSONL

Após a geração, cada linha de `dev.jsonl` / `test.jsonl` é uma
`DiscrepancyInstance` serializada:

```jsonl
{"instance_id":"Ambiguities_contract_p0","source_dataset":"cuad","perturb_type":"ambiguity","dimension":"in_text","original_text":"...","changed_text":"...","explanation":"...","location":"Section 2","contradicted_location":null,"contradicted_text":null,"contradicted_law":null,"law_citation":null,"law_url1":null,"law_url2":null,"scraped_snippet_1":null,"scraped_snippet_2":null,"gold_label":true}
```

---

## Regras de Protocolo

| Regra | Detalhe |
|-------|---------|
| **Dataset nunca commitado** | `data/` está no `.gitignore` |
| **Split test congelado** | Após a primeira geração, `test.jsonl` não deve ser modificado |
| **Dev para calibração** | Todo ajuste de prompt e limiar usa apenas `dev.jsonl` |
| **`explanation` não exposta** | O campo `explanation`/`justification` nunca é inserido em prompts nem usado para construir a KB |
| **KB somente de estatutos** | `scraped_snippet_1/2` e URLs de lei são as únicas fontes legítimas para a base de conhecimento jurídico |
