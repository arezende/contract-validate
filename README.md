# ContractFOL

**Validação Automatizada de Contratos Inter-Institucionais utilizando Large Language Models e Lógica de Primeira Ordem**

Artefato computacional desenvolvido como parte da dissertação de mestrado de Anderson Rezende no Programa de Engenharia de Sistemas e Computação da COPPE/UFRJ.

## Visão Geral

O ContractFOL é um sistema neurossimbólico que integra Large Language Models (LLMs) com raciocínio formal baseado em Lógica de Primeira Ordem (FOL) para automatizar a validação de contratos entre instituições. O sistema detecta inconsistências contratuais e gera explicações compreensíveis para usuários não especialistas em lógica.

### Arquitetura

O sistema implementa um pipeline com cinco componentes principais:

1. **Extrator de Cláusulas** - Segmenta documentos contratuais em cláusulas individuais
2. **Classificador Deôntico** - Identifica modalidades normativas (obrigações, permissões, proibições)
3. **Tradutor NL-FOL** - Converte cláusulas para Lógica de Primeira Ordem com auto-refinamento
4. **Verificador Formal** - Verifica consistência usando solver SMT (Z3)
5. **Gerador de Explicações** - Produz relatórios compreensíveis sobre inconsistências

## Instalação

### Requisitos

- Python 3.11+
- pip

### Instalação via pip

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/contract-validate.git
cd contract-validate

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instalar dependências
pip install -e .
```

### Configuração de API Keys

Para utilizar os recursos completos do sistema, configure as chaves de API:

```bash
# OpenAI (para GPT-4)
export OPENAI_API_KEY="sua-chave-openai"

# Anthropic (para Claude)
export ANTHROPIC_API_KEY="sua-chave-anthropic"
```

## Uso

### Interface de Linha de Comando

```bash
# Validar um contrato
contractfol validate contrato.txt

# Validar com saída para arquivo
contractfol validate contrato.txt -o relatorio.txt

# Traduzir uma cláusula para FOL
contractfol translate "O PATROCINADOR obriga-se a pagar mensalmente"

# Executar demonstração
contractfol demo

# Ver ontologia disponível
contractfol ontology
```

### Como Biblioteca Python

```python
from contractfol import ContractFOLPipeline

# Criar pipeline
pipeline = ContractFOLPipeline()

# Validar contrato
report = pipeline.validate_file("contrato.pdf")

# Verificar resultados
if report.has_conflicts:
    for conflict in report.conflicts:
        print(f"Conflito: {conflict.explanation}")
        print(f"Sugestão: {conflict.suggestion}")

# Processar cláusula individual
result = pipeline.process_single_clause(
    "O CONTRATADO não poderá utilizar a marca sem autorização."
)
print(f"Modalidade: {result['modality']}")
print(f"FOL: {result['fol_formula']}")
```

## Estrutura do Projeto

```
contract-validate/
├── src/contractfol/
│   ├── __init__.py           # Módulo principal
│   ├── models.py             # Modelos de dados
│   ├── ontology.py           # Ontologia de domínio (predicados FOL)
│   ├── pipeline.py           # Pipeline principal
│   ├── cli.py                # Interface de linha de comando
│   ├── extractors/           # Extração de cláusulas
│   ├── classifiers/          # Classificação deôntica
│   ├── translators/          # Tradução NL-FOL
│   ├── verifiers/            # Verificação formal (Z3)
│   ├── generators/           # Geração de explicações
│   ├── evaluation/           # Avaliação experimental
│   └── utils/                # Utilitários
├── data/
│   ├── contracts/            # Contratos de exemplo
│   ├── clauses/              # Cláusulas anotadas
│   └── results/              # Resultados de experimentos
├── scripts/
│   └── run_experiment.py     # Script de avaliação
├── config/
│   └── default.yaml          # Configurações
└── tests/                    # Testes automatizados
```

## Ontologia de Domínio

O sistema utiliza uma ontologia de predicados FOL para representação de contratos:

| Predicado | Descrição |
|-----------|-----------|
| `Obrigacao(a, p, t)` | Agente a é obrigado a realizar p até tempo t |
| `Permissao(a, p)` | Agente a tem permissão para p |
| `Proibicao(a, p)` | Agente a é proibido de realizar p |
| `Parte(x, c)` | Entidade x é parte do contrato c |
| `Prazo(c, d1, d2)` | Contrato c tem vigência de d1 a d2 |
| `Condicao(p, q)` | Condição p implica consequência q |

## Avaliação Experimental

Para executar o experimento de avaliação conforme descrito na dissertação:

```bash
# Executar todos os métodos
python scripts/run_experiment.py

# Especificar métodos
python scripts/run_experiment.py --methods contractfol baseline

# Com API keys
python scripts/run_experiment.py --openai-key $OPENAI_API_KEY
```

### Métricas

O experimento avalia:
- **Precisão**: TP / (TP + FP)
- **Recall**: TP / (TP + FN)
- **F1-Score**: 2 × (P × R) / (P + R)
- **Tempo de processamento**

## Referências

Este trabalho é baseado na dissertação:

> REZENDE, Anderson. **Validação Automatizada de Contratos Inter-Institucionais Utilizando Large Language Models e Lógica de Primeira Ordem: Uma Abordagem Design Science Research**. Dissertação de Mestrado - COPPE/UFRJ, 2025.

### Trabalhos Relacionados

- PAN et al. (2023). Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning
- OLAUSSON et al. (2023). LINC: A Neurosymbolic Approach for Logical Reasoning
- RYU et al. (2024). CLOVER: Closed-Loop Verifiable Code Generation

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## Contato

Anderson Rezende - COPPE/UFRJ
Orientador: Prof. Geraldo Xexéo
