# CLAUSE LLM Eval

Projeto Python para avaliar LLMs no benchmark **CLAUSE** com foco em:

1. reduzir custo usando **subamostra estratificada de 10%**;
2. avaliar **Eval_1**, **Eval_2** e uma versão inicial de **Eval_3**;
3. estimar incerteza com **bootstrap estratificado sobre predições salvas**;
4. comparar os resultados obtidos com os valores reportados pelos autores.

> O dataset CLAUSE tem acesso controlado. Os arquivos do dataset **não devem ser commitados**. A pasta `data/` está no `.gitignore`.

---

## 1. Estrutura esperada do dataset

Coloque os dados brutos em:

```text
data/raw/clause/datasets/
├── CUAD_Dataset/
│   ├── Ambiguities/
│   ├── Inconsistencies/
│   ├── Misaligned_Terminology/
│   ├── Omissions/
│   └── Structural_Flaws/
└── NLI_Dataset/
    ├── Ambiguities/
    ├── Inconsistencies/
    ├── Misaligned_Terminology/
    ├── Omissions/
    └── Structural_Flaws/
```

---

## 2. Instalação

### Windows PowerShell

```powershell
cd C:\Projetos
Expand-Archive .\clause_llm_eval_project.zip -DestinationPath .
cd .\clause_llm_eval_project

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .
copy .env.example .env
```

### Linux / WSL

```bash
cd ~/projetos
unzip clause_llm_eval_project.zip
cd clause_llm_eval_project

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

---

## 3. Pipeline recomendado

### 3.1 Ingestão do CLAUSE

```bash
clause-eval ingest \
  --data data/raw/clause/datasets \
  --output data/splits/all_instances.jsonl
```

### 3.2 Criar split dev/test congelado

```bash
clause-eval make-splits \
  --input data/splits/all_instances.jsonl \
  --dev-output data/splits/dev.jsonl \
  --test-output data/splits/test.jsonl \
  --test-fraction 0.30 \
  --seed 42
```

Depois da primeira geração, **não altere** `test.jsonl`.

### 3.3 Criar subamostra estratificada de 10% do teste

```bash
clause-eval sample \
  --input data/splits/test.jsonl \
  --output data/splits/test_10pct_stratified.jsonl \
  --fraction 0.10 \
  --seed 42
```

### 3.4 Construir Eval_1

Eval_1 usa `changed_text` como positivo e `original_text` como negativo.

```bash
clause-eval build-eval1 \
  --input data/splits/test_10pct_stratified.jsonl \
  --output data/eval/eval1_test_10pct.jsonl \
  --seed 42
```

### 3.5 Construir Eval_2

Eval_2 usa `changed_text` e espera a dimensão `in_text` ou `legal`.

```bash
clause-eval build-eval2 \
  --input data/splits/test_10pct_stratified.jsonl \
  --output data/eval/eval2_test_10pct.jsonl \
  --seed 42
```

### 3.6 Rodar um modelo

Teste primeiro com `mock`:

```bash
clause-eval run \
  --input data/eval/eval1_test_10pct.jsonl \
  --output runs/eval1_mock_predictions.jsonl \
  --task eval1 \
  --provider mock \
  --model mock
```

OpenAI:

```bash
clause-eval run \
  --input data/eval/eval1_test_10pct.jsonl \
  --output runs/eval1_gpt4o_mini_predictions.jsonl \
  --task eval1 \
  --provider openai \
  --model gpt-4o-mini \
  --temperature 0
```

Gemini:

```bash
clause-eval run \
  --input data/eval/eval1_test_10pct.jsonl \
  --output runs/eval1_gemini_predictions.jsonl \
  --task eval1 \
  --provider gemini \
  --model gemini-2.5-flash \
  --temperature 0
```

Ollama local:

```bash
clause-eval run \
  --input data/eval/eval1_test_10pct.jsonl \
  --output runs/eval1_llama_predictions.jsonl \
  --task eval1 \
  --provider ollama \
  --model llama3.1:8b \
  --temperature 0
```

### 3.7 Calcular métricas

```bash
clause-eval metrics \
  --input runs/eval1_gpt4o_mini_predictions.jsonl \
  --task eval1 \
  --output reports/eval1_gpt4o_mini_metrics.json
```

### 3.8 Bootstrap estratificado

```bash
clause-eval bootstrap \
  --input runs/eval1_gpt4o_mini_predictions.jsonl \
  --task eval1 \
  --output reports/eval1_gpt4o_mini_bootstrap.json \
  --n-bootstrap 5000 \
  --seed 42
```

---

## 4. Protocolo científico adotado

- `dev.jsonl` é usado para calibrar prompts e parsers.
- `test.jsonl` é congelado antes da avaliação.
- A subamostra de 10% é estratificada por `perturb_type × dimension`.
- Para Eval_1, a unidade-base é `instance_id`; o par `original_text`/`changed_text` é preservado.
- O bootstrap é aplicado **sobre as predições salvas**, não reexecutando o LLM.
- Intervalos de confiança são calculados pelos percentis 2,5% e 97,5%.

---

## 5. Observação metodológica

A amostra de 10% não é bootstrap. Ela é uma **subamostra estratificada para redução de custo**.

O bootstrap vem depois, sobre as predições salvas, para estimar a incerteza das métricas.
