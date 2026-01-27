# ContractFOL: Uma Abordagem Neurosimbólica para Validação Automatizada de Contratos Inter-Institucionais

## Documentação Técnica Aprofundada

**Autor**: Anderson Rezende
**Instituição**: COPPE/UFRJ - Programa de Engenharia de Sistemas e Computação
**Ano**: 2025
**Versão**: 1.0

---

## Sumário

1. [Introdução e Motivação](#1-introdução-e-motivação)
2. [Fundamentação Teórica](#2-fundamentação-teórica)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Etapa 1: Extração de Cláusulas](#4-etapa-1-extração-de-cláusulas)
5. [Etapa 2: Classificação Deôntica](#5-etapa-2-classificação-deôntica)
6. [Etapa 3: Tradução NL-FOL](#6-etapa-3-tradução-nl-fol)
7. [Etapa 4: Verificação Formal com Z3](#7-etapa-4-verificação-formal-com-z3)
8. [Etapa 5: Geração de Explicações](#8-etapa-5-geração-de-explicações)
9. [Ontologia do Domínio Contratual](#9-ontologia-do-domínio-contratual)
10. [Avaliação Experimental](#10-avaliação-experimental)
11. [Limitações e Trabalhos Futuros](#11-limitações-e-trabalhos-futuros)
12. [Conclusão](#12-conclusão)
13. [Referências](#13-referências)

---

## 1. Introdução e Motivação

### 1.1 Contextualização do Problema

A gestão de contratos inter-institucionais representa um desafio significativo para organizações de todos os portes. Contratos de patrocínio esportivo, acordos de cooperação técnica, convênios públicos e instrumentos similares frequentemente apresentam **inconsistências lógicas** que podem resultar em disputas jurídicas, perdas financeiras e danos reputacionais.

O problema central que este trabalho aborda pode ser formalizado como:

> **Problema**: Dado um contrato $C$ composto por um conjunto de cláusulas $\{c_1, c_2, ..., c_n\}$, determinar se existe algum par $(c_i, c_j)$ tal que as obrigações, permissões ou proibições expressas em $c_i$ são logicamente incompatíveis com aquelas expressas em $c_j$.

### 1.2 Justificativa da Abordagem Neurosimbólica

A escolha de uma abordagem **neurosimbólica** — combinando Large Language Models (LLMs) com raciocínio simbólico formal — fundamenta-se em três observações empíricas:

1. **Limitações dos LLMs puros**: Embora LLMs como GPT-4 e Claude demonstrem capacidades impressionantes de compreensão de linguagem natural, eles apresentam inconsistências em tarefas que exigem raciocínio lógico rigoroso (Marcus & Davis, 2020). Em experimentos preliminares, observamos que LLMs detectam aproximadamente 67% das inconsistências contratuais, com taxa significativa de falsos positivos.

2. **Limitações dos métodos puramente simbólicos**: Abordagens baseadas exclusivamente em lógica formal enfrentam o "gargalo do conhecimento" (knowledge acquisition bottleneck), exigindo representações formais manualmente construídas por especialistas.

3. **Complementaridade neural-simbólica**: A integração permite que LLMs realizem a tradução de linguagem natural para representações formais, enquanto provadores de teoremas como Z3 garantem a corretude lógica da verificação.

### 1.3 Hipótese Central

> **Hipótese**: A combinação de Large Language Models para tradução NL→FOL com SMT solvers para verificação de consistência produz um sistema de detecção de inconsistências contratuais com precisão e recall superiores a métodos baseados exclusivamente em LLMs ou heurísticas.

### 1.4 Contribuições

Este trabalho apresenta as seguintes contribuições:

1. **ContractFOL**: Um artefato de software completo para validação automatizada de contratos
2. **Ontologia contratual**: Um vocabulário formal de 23 predicados para representação de cláusulas contratuais
3. **Pipeline de 5 etapas**: Uma arquitetura reproduzível para processamento de documentos jurídicos
4. **Mecanismo de auto-refinamento**: Uma técnica iterativa para melhoria da qualidade de tradução NL→FOL
5. **Avaliação empírica**: Experimentos comparativos com baseline e métodos alternativos

---

## 2. Fundamentação Teórica

### 2.1 Lógica Deôntica

A **lógica deôntica** é um ramo da lógica modal que formaliza conceitos normativos como obrigação, permissão e proibição. Introduzida por Georg Henrik von Wright em seu seminal artigo "Deontic Logic" (1951), esta lógica fornece o arcabouço teórico para representação formal de normas jurídicas.

#### 2.1.1 Operadores Deônticos Fundamentais

Os três operadores deônticos primitivos são:

| Operador | Símbolo | Leitura | Exemplo |
|----------|---------|---------|---------|
| Obrigação | $O(p)$ | "É obrigatório que $p$" | $O(\text{pagar\_tributo})$ |
| Permissão | $P(p)$ | "É permitido que $p$" | $P(\text{usar\_marca})$ |
| Proibição | $F(p)$ | "É proibido que $p$" | $F(\text{divulgar\_segredo})$ |

#### 2.1.2 Relações Interdefiníveis

Os operadores deônticos satisfazem as seguintes equivalências (análogas ao quadrado de oposição aristotélico):

$$O(p) \equiv \neg P(\neg p) \equiv F(\neg p)$$
$$P(p) \equiv \neg O(\neg p) \equiv \neg F(p)$$
$$F(p) \equiv O(\neg p) \equiv \neg P(p)$$

#### 2.1.3 Princípio da Não-Contradição Deôntica

Um sistema normativo é **consistente** se e somente se não existe proposição $p$ tal que:

$$O(p) \land F(p)$$

Este princípio é o fundamento teórico para a detecção de inconsistências em ContractFOL. Quando o solver Z3 encontra uma contradição entre obrigação e proibição, ele está essencialmente verificando violações deste princípio.

### 2.2 Lógica de Primeira Ordem (FOL)

A escolha da **Lógica de Primeira Ordem** como linguagem de representação justifica-se por três razões:

1. **Expressividade adequada**: FOL permite quantificação sobre indivíduos (agentes, ações, tempos), necessária para representar cláusulas como "O CONTRATADO obriga-se a entregar **todos** os relatórios até o dia 5 de **cada** mês".

2. **Decidibilidade controlada**: Embora FOL seja indecidível em geral, fragmentos relevantes para contratos (como lógica de primeira ordem com teoria de igualdade e aritmética linear) são decidíveis por SMT solvers.

3. **Suporte ferramental maduro**: Solvers como Z3, CVC5 e Yices oferecem implementações robustas e otimizadas.

#### 2.2.1 Sintaxe FOL Adotada

A gramática BNF da linguagem FOL utilizada no ContractFOL é:

```bnf
<formula> ::= <atom>
            | '¬' <formula>
            | <formula> '∧' <formula>
            | <formula> '∨' <formula>
            | <formula> '→' <formula>
            | <formula> '↔' <formula>
            | '∀' <var> '.' <formula>
            | '∃' <var> '.' <formula>

<atom>    ::= <predicate> '(' <terms> ')'
            | <term> '=' <term>

<terms>   ::= <term> | <term> ',' <terms>

<term>    ::= <constant> | <variable> | <function> '(' <terms> ')'
```

### 2.3 SMT Solvers e Z3

**Satisfiability Modulo Theories (SMT)** estende a satisfatibilidade proposicional (SAT) com teorias de domínio específico. O solver **Z3** (de Moura & Bjørner, 2008), desenvolvido pela Microsoft Research, é atualmente o solver SMT mais amplamente utilizado em verificação formal.

#### 2.3.1 Justificativa da Escolha do Z3

A seleção do Z3 como motor de inferência fundamenta-se em:

1. **Suporte a UNSAT cores**: Quando uma fórmula é insatisfatível, Z3 pode extrair um subconjunto minimal de cláusulas responsáveis pela contradição — funcionalidade essencial para identificar quais cláusulas contratuais específicas conflitam.

2. **Teorias built-in relevantes**: Z3 suporta nativamente aritmética linear (útil para valores monetários e prazos), strings (para nomes e identificadores) e datatypes algébricos (para modelar estruturas contratuais).

3. **Performance comprovada**: Em competições SMT-COMP, Z3 consistentemente figura entre os solvers de melhor desempenho.

4. **API Python madura**: A biblioteca `z3-solver` oferece integração nativa com Python, facilitando o desenvolvimento do pipeline.

### 2.4 Large Language Models

Os **Large Language Models** (LLMs) são redes neurais transformer pré-treinadas em vastos corpora textuais. Para o ContractFOL, utilizamos LLMs como "tradutores" de linguagem natural para lógica formal.

#### 2.4.1 Capacidades Relevantes dos LLMs

- **Compreensão de linguagem jurídica**: LLMs treinados em corpora que incluem textos legais demonstram capacidade de interpretar jargão jurídico.
- **Geração estruturada**: Com prompting adequado, LLMs podem gerar saídas em formatos estruturados como JSON ou fórmulas lógicas.
- **Few-shot learning**: A capacidade de aprender padrões a partir de poucos exemplos permite adaptar o modelo ao domínio contratual.

#### 2.4.2 Limitações que Motivam a Abordagem Híbrida

- **Alucinação**: LLMs podem gerar fórmulas sintaticamente incorretas ou semanticamente inadequadas.
- **Inconsistência**: Respostas podem variar entre invocações para o mesmo input.
- **Raciocínio lógico frágil**: Estudos demonstram que LLMs falham em tarefas que exigem múltiplos passos de inferência lógica (Dziri et al., 2023).

Estas limitações justificam o uso de Z3 como "verificador" das traduções produzidas pelo LLM, garantindo que a verificação de consistência seja matematicamente rigorosa.

---

## 3. Arquitetura do Sistema

### 3.1 Visão Geral do Pipeline

O ContractFOL implementa um **pipeline sequencial de 5 etapas**, onde a saída de cada etapa alimenta a entrada da próxima:

```
┌─────────────────┐
│   Documento     │
│   Contratual    │
│  (PDF/DOCX/TXT) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    ETAPA 1      │
│   Extração de   │◄──── Padrões Regex
│    Cláusulas    │      (7 níveis de prioridade)
└────────┬────────┘
         │ Contract{clauses[]}
         ▼
┌─────────────────┐
│    ETAPA 2      │
│  Classificação  │◄──── Heurísticas + LLM
│    Deôntica     │      (abordagem híbrida)
└────────┬────────┘
         │ Clause{modality}
         ▼
┌─────────────────┐
│    ETAPA 3      │
│   Tradução      │◄──── LLM + Auto-refinamento
│    NL → FOL     │      (até 3 tentativas)
└────────┬────────┘
         │ Clause{fol_formula}
         ▼
┌─────────────────┐
│    ETAPA 4      │
│   Verificação   │◄──── Z3 SMT Solver
│     Formal      │      (axiomas deônticos)
└────────┬────────┘
         │ VerificationResult{conflicts[]}
         ▼
┌─────────────────┐
│    ETAPA 5      │
│   Geração de    │◄──── Templates + LLM
│   Explicações   │      (enriquecimento)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ValidationReport│
│   - conflitos   │
│   - explicações │
│   - sugestões   │
└─────────────────┘
```

### 3.2 Justificativa da Arquitetura Pipeline

A escolha de uma arquitetura de pipeline sequencial, em contraste com abordagens end-to-end, fundamenta-se em:

1. **Modularidade**: Cada etapa pode ser desenvolvida, testada e otimizada independentemente.

2. **Interpretabilidade**: Resultados intermediários (cláusulas extraídas, modalidades classificadas, fórmulas FOL) são inspecionáveis, facilitando depuração e validação.

3. **Flexibilidade**: Componentes podem ser substituídos sem afetar o restante do sistema (e.g., trocar OpenAI por Anthropic).

4. **Reprodutibilidade científica**: Métricas podem ser coletadas em cada etapa, permitindo análise granular de desempenho.

### 3.3 Estruturas de Dados Principais

O sistema utiliza dataclasses Python para representar entidades do domínio:

```python
@dataclass
class Agent:
    """Representa uma parte contratual (CONTRATANTE, CONTRATADO, etc.)"""
    id: str
    name: str
    role: str  # papel no contrato

@dataclass
class Clause:
    """Representa uma cláusula contratual individual"""
    id: str
    text: str                           # texto original
    contract_id: str
    section: Optional[str]              # seção do contrato
    number: Optional[str]               # numeração original
    agents: list[Agent]                 # partes mencionadas
    modality: Optional[DeonticModality] # modalidade deôntica
    modality_confidence: float          # confiança da classificação
    fol_formula: Optional[str]          # fórmula FOL traduzida
    fol_parsed: bool                    # se a fórmula é válida

@dataclass
class Contract:
    """Representa um contrato completo"""
    id: str
    title: str
    parties: list[Agent]
    clauses: list[Clause]
    source_file: Optional[str]

@dataclass
class Conflict:
    """Representa uma inconsistência detectada"""
    id: str
    type: ConflictType
    clause_ids: list[str]
    formulas: list[str]
    explanation: Optional[str]
    severity: Severity
```

---

## 4. Etapa 1: Extração de Cláusulas

### 4.1 Objetivo

A primeira etapa do pipeline tem como objetivo **segmentar** o documento contratual em unidades atômicas de análise — as cláusulas individuais — e **identificar** as partes contratuais envolvidas.

### 4.2 Abordagem: Pattern Matching com Expressões Regulares

#### 4.2.1 Justificativa da Escolha

A opção por **expressões regulares** (regex) em detrimento de técnicas mais sofisticadas de NLP (como segmentação baseada em modelos neurais) fundamenta-se em:

1. **Estrutura altamente padronizada**: Contratos brasileiros seguem convenções de formatação bem estabelecidas (CLÁUSULA PRIMEIRA, Art. 1º, etc.), tornando regex suficientemente expressivas.

2. **Determinismo**: Regex produzem resultados consistentes e reproduzíveis, ao contrário de modelos probabilísticos.

3. **Performance**: Matching de padrões é computacionalmente eficiente (complexidade linear no tamanho do texto).

4. **Interpretabilidade**: Padrões são explícitos e auditáveis, facilitando manutenção e extensão.

#### 4.2.2 Limitações Reconhecidas

- Cláusulas com formatação não-padrão podem não ser detectadas
- Subdivisões implícitas (parágrafos sem marcação) requerem heurísticas adicionais

### 4.3 Padrões de Extração

O extrator implementa **7 níveis de prioridade** de padrões, aplicados em ordem decrescente de especificidade:

| Prioridade | Padrão | Exemplo | Regex |
|------------|--------|---------|-------|
| 10 | Ordinal por extenso | CLÁUSULA PRIMEIRA | `CLÁUSULA\s+(PRIMEIRA\|SEGUNDA\|...)` |
| 9 | Ordinal numeral | CLÁUSULA 1ª | `CLÁUSULA\s+\d+[ªº]` |
| 8 | Numérico simples | CLÁUSULA 1 | `CLÁUSULA\s+\d+` |
| 7 | Artigo | Art. 1º | `Art\.\s*\d+[ºª]?` |
| 6 | Numeração com ponto | 1. Objeto | `^\d+\.\s+\w` |
| 5 | Romano | I - Das Partes | `^[IVX]+\s*[-–]` |
| 4 | Parágrafo | § 1º | `§\s*\d+[ºª]?` |
| 3 | Alínea | a) texto | `^[a-z]\)` |

### 4.4 Algoritmo de Extração

```
Algoritmo: ExtractClauses
Entrada: texto T do contrato
Saída: lista de Clause

1. normalizar(T)  // remove múltiplos espaços, normaliza quebras de linha
2. matches ← []
3. PARA CADA pattern P em PATTERNS (ordenados por prioridade DESC):
4.     encontrados ← regex_findall(P, T)
5.     PARA CADA match M em encontrados:
6.         SE M.posição não sobrepõe matches existentes:
7.             matches.append(M)
8. ordenar(matches, por posição)
9. clauses ← []
10. PARA i = 0 ATÉ len(matches)-1:
11.     início ← matches[i].posição
12.     fim ← matches[i+1].posição SE i < len(matches)-1 SENÃO len(T)
13.     texto ← T[início:fim]
14.     SE 20 ≤ len(texto) ≤ 5000:  // filtro de tamanho
15.         clauses.append(Clause(texto, número=matches[i].grupo))
16. RETORNAR clauses
```

### 4.5 Identificação de Partes Contratuais

O extrator também identifica **agentes** (partes contratuais) utilizando padrões específicos do domínio de patrocínio esportivo:

```python
AGENT_PATTERNS = [
    r"\b(CONTRATANTE|CONTRATADO|PATROCINADOR|PATROCINADO)\b",
    r"\b(ATLETA|CONFEDERAÇÃO|FEDERAÇÃO|CLUBE)\b",
    r"\b(COB|CPB|TIME BRASIL)\b",  # entidades específicas
]
```

### 4.6 Métricas de Qualidade

Em avaliação com corpus de 50 contratos anotados manualmente:

| Métrica | Valor |
|---------|-------|
| Precisão de segmentação | 94.2% |
| Recall de segmentação | 91.7% |
| F1-Score | 92.9% |
| Tempo médio por contrato | 12ms |

---

## 5. Etapa 2: Classificação Deôntica

### 5.1 Objetivo

A segunda etapa visa **classificar** cada cláusula extraída em uma das **seis modalidades deônticas** definidas, determinando a natureza normativa da cláusula.

### 5.2 Taxonomia de Modalidades

Baseada na lógica deôntica de Von Wright (1951) e adaptada ao contexto contratual brasileiro:

| Modalidade | Código | Descrição | Indicadores Linguísticos |
|------------|--------|-----------|-------------------------|
| Obrigação Ativa | `OBRIGACAO_ATIVA` | Agente deve realizar ação | "obriga-se a", "deverá", "compromete-se" |
| Obrigação Passiva | `OBRIGACAO_PASSIVA` | Agente deve tolerar/permitir | "deverá permitir", "não poderá impedir" |
| Permissão | `PERMISSAO` | Agente pode realizar ação | "poderá", "é facultado", "fica autorizado" |
| Proibição | `PROIBICAO` | Agente não pode realizar ação | "é vedado", "não poderá", "fica proibido" |
| Condição | `CONDICAO` | Estabelece condição para efeitos | "caso", "desde que", "na hipótese de" |
| Definição | `DEFINICAO` | Define termos ou conceitos | "entende-se por", "considera-se", "para fins" |

### 5.3 Abordagem Híbrida: Heurísticas + LLM

#### 5.3.1 Justificativa do Modelo Híbrido

A classificação deôntica emprega uma estratégia de **duas camadas**:

1. **Camada 1 (Heurísticas)**: Classificação rápida baseada em padrões lexicais
2. **Camada 2 (LLM)**: Classificação refinada quando heurísticas são inconclusivas

Esta abordagem híbrida otimiza o trade-off entre:

- **Custo computacional**: Heurísticas são ordens de magnitude mais rápidas que chamadas de API LLM
- **Precisão**: LLMs capturam nuances linguísticas que escapam a padrões fixos
- **Latência**: Maioria das cláusulas (≈78%) são classificadas apenas por heurísticas

#### 5.3.2 Decisão de Escalamento para LLM

O sistema escala para LLM quando:

$$\text{confiança}_{\text{heurística}} < 0.7$$

O threshold de 0.7 foi determinado empiricamente através de grid search no conjunto de validação, maximizando F1-Score enquanto mantém custo de API aceitável.

### 5.4 Camada 1: Classificação por Heurísticas

#### 5.4.1 Padrões Lexicais

O classificador mantém aproximadamente **25 padrões regex** por modalidade:

```python
DEONTIC_PATTERNS = {
    DeonticModality.OBRIGACAO_ATIVA: [
        r"\b(obriga-se|obrigará|obrigam-se)\b",
        r"\b(deverá|devem|deve)\s+\w+",
        r"\b(compromete-se|comprometem-se)\s+a\b",
        r"\b(é\s+de\s+responsabilidade|cabe\s+a[o]?)\b",
        r"\b(assumirá?\s+a\s+obrigação)\b",
        # ... mais padrões
    ],
    DeonticModality.PROIBICAO: [
        r"\b(não\s+poderá|não\s+pode|não\s+deverá)\b",
        r"\b(é\s+vedado|fica\s+vedado|vedada?)\b",
        r"\b(é\s+proibid[oa]|fica\s+proibid[oa])\b",
        r"\b(abster-se-á|deverá\s+abster-se)\b",
        # ... mais padrões
    ],
    # ... demais modalidades
}
```

#### 5.4.2 Cálculo de Confiança

A confiança da classificação heurística é calculada como:

$$\text{confiança}(m) = \frac{\text{matches}(m)}{\sum_{m' \in M} \text{matches}(m') + \epsilon}$$

Onde:
- $\text{matches}(m)$ = número de padrões da modalidade $m$ encontrados
- $M$ = conjunto de todas as modalidades
- $\epsilon = 0.1$ (suavização de Laplace para evitar divisão por zero)

### 5.5 Camada 2: Classificação por LLM

Quando heurísticas são insuficientes, o sistema invoca o LLM com prompt estruturado:

```
Classifique a modalidade deôntica da seguinte cláusula contratual.

CLÁUSULA:
"{texto_da_clausula}"

MODALIDADES POSSÍVEIS:
- OBRIGACAO_ATIVA: O agente deve realizar uma ação
- OBRIGACAO_PASSIVA: O agente deve permitir/tolerar algo
- PERMISSAO: O agente pode realizar uma ação
- PROIBICAO: O agente não pode realizar uma ação
- CONDICAO: Estabelece condição para efeitos jurídicos
- DEFINICAO: Define termos ou conceitos

Responda APENAS em formato JSON:
{"modalidade": "<MODALIDADE>", "confianca": <0.0-1.0>}
```

#### 5.5.1 Configuração do LLM

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| Temperature | 0.1 | Minimiza variância nas respostas |
| Max tokens | 100 | Resposta esperada é curta (~30 tokens) |
| Top-p | 0.95 | Foco nas opções mais prováveis |

### 5.6 Avaliação da Classificação

Em conjunto de teste com 500 cláusulas anotadas por especialistas jurídicos:

| Modalidade | Precisão | Recall | F1 | Suporte |
|------------|----------|--------|-----|---------|
| OBRIGACAO_ATIVA | 0.94 | 0.91 | 0.92 | 187 |
| OBRIGACAO_PASSIVA | 0.88 | 0.82 | 0.85 | 43 |
| PERMISSAO | 0.91 | 0.89 | 0.90 | 78 |
| PROIBICAO | 0.96 | 0.93 | 0.94 | 62 |
| CONDICAO | 0.87 | 0.84 | 0.85 | 89 |
| DEFINICAO | 0.93 | 0.95 | 0.94 | 41 |
| **Macro Avg** | **0.92** | **0.89** | **0.90** | **500** |

---

## 6. Etapa 3: Tradução NL-FOL

### 6.1 Objetivo

A terceira etapa realiza a **tradução** de cláusulas em linguagem natural para **fórmulas de Lógica de Primeira Ordem**, criando representações formais que podem ser verificadas pelo solver Z3.

### 6.2 Desafio da Tradução NL→FOL

A tradução de linguagem natural para lógica formal é reconhecidamente um dos problemas mais desafiadores em Processamento de Linguagem Natural, envolvendo:

1. **Ambiguidade lexical**: Uma palavra pode mapear para múltiplos predicados
2. **Ambiguidade estrutural**: A estrutura lógica pode não ser evidente
3. **Conhecimento implícito**: Informações assumidas não estão explícitas no texto
4. **Quantificação**: Determinar escopo de quantificadores universais/existenciais

### 6.3 Abordagem: LLM com Auto-Refinamento Iterativo

#### 6.3.1 Justificativa do Auto-Refinamento

Em vez de confiar em uma única tradução do LLM, implementamos um **ciclo de refinamento iterativo** com até 3 tentativas. Esta abordagem é inspirada em trabalhos de "self-refine" (Madaan et al., 2023) e se justifica por:

1. **Redução de erros sintáticos**: ~15% das traduções iniciais contêm erros de sintaxe (parênteses desbalanceados, predicados incorretos)
2. **Melhoria incremental**: Feedback estruturado permite que o LLM corrija erros específicos
3. **Custo controlado**: Limite de 3 tentativas previne loops infinitos e custos excessivos

#### 6.3.2 Diagrama do Ciclo de Refinamento

```
┌─────────────────────────────────────────────────────────────┐
│                    CICLO DE REFINAMENTO                      │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │Tentativa │───▶│Validação │───▶│  Válido? │──SIM──▶ FIM   │
│  │    N     │    │ Sintática│    │          │               │
│  └──────────┘    └──────────┘    └────┬─────┘               │
│       ▲                               │ NÃO                  │
│       │                               ▼                      │
│       │         ┌──────────────────────────┐                │
│       │         │   N < MAX_TENTATIVAS?    │                │
│       │         └───────────┬──────────────┘                │
│       │                     │ SIM                           │
│       │                     ▼                               │
│       │         ┌──────────────────────────┐                │
│       └─────────│  Gerar prompt com        │                │
│                 │  feedback de erros       │                │
│                 └──────────────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Prompt de Tradução

O prompt principal segue princípios de few-shot prompting:

```
Você é um especialista em lógica formal e direito contratual.
Traduza a cláusula contratual para Lógica de Primeira Ordem (FOL).

ONTOLOGIA DISPONÍVEL:
- Obrigacao(agente, acao, tempo): Agente é obrigado a realizar ação até tempo
- Permissao(agente, acao): Agente tem permissão para ação
- Proibicao(agente, acao): Agente é proibido de realizar ação
- Parte(agente, contrato): Agente é parte do contrato
- Prazo(contrato, inicio, fim): Contrato vigora de início a fim
- Pagamento(valor): Ação de pagamento
- UsoMarca(marca): Ação de uso de marca
- UsoImagem(finalidade): Ação de uso de imagem
[... lista completa de 23 predicados ...]

CLÁUSULA A TRADUZIR:
"{texto_clausula}"

MODALIDADE DETECTADA: {modalidade}

EXEMPLOS:
1. "O CONTRATADO obriga-se a pagar R$ 1.000,00 mensais"
   → Obrigacao(contratado, Pagamento(1000), Mensal)

2. "É vedado ao PATROCINADOR ceder os direitos sem autorização"
   → Proibicao(patrocinador, Cessao(direitos, sem_autorizacao))

3. "Caso o ATLETA vença a competição, receberá bônus"
   → ∀c.Competicao(c) → (Vence(atleta, c) → Obrigacao(patrocinador, Pagamento(bonus), AposEvento(c)))

IMPORTANTE:
- Use APENAS predicados da ontologia fornecida
- Certifique-se de que parênteses estão balanceados
- Variáveis devem estar quantificadas (∀ ou ∃)
- Retorne APENAS a fórmula, sem explicações

FÓRMULA FOL:
```

### 6.5 Validação Sintática

O módulo `FOLSyntaxValidator` verifica três aspectos críticos:

#### 6.5.1 Balanceamento de Parênteses

```python
def _check_parentheses(formula: str) -> list[str]:
    stack = []
    for i, char in enumerate(formula):
        if char == '(':
            stack.append(i)
        elif char == ')':
            if not stack:
                return [f"Parêntese ')' sem correspondente na posição {i}"]
            stack.pop()
    if stack:
        return [f"Parêntese '(' na posição {stack[0]} sem fechamento"]
    return []
```

#### 6.5.2 Predicados Conhecidos

```python
def _check_predicates(formula: str, ontology: ContractOntology) -> list[str]:
    # Extrai todos os identificadores seguidos de '('
    predicate_pattern = r'\b([A-Z][a-zA-Z]*)\s*\('
    found_predicates = re.findall(predicate_pattern, formula)

    errors = []
    for pred in found_predicates:
        if pred not in ontology.predicate_names:
            errors.append(f"Predicado '{pred}' não existe na ontologia")
    return errors
```

#### 6.5.3 Variáveis Livres

```python
def _check_free_variables(formula: str) -> list[str]:
    # Coleta variáveis quantificadas
    quantified = set(re.findall(r'[∀∃](\w+)\.', formula))

    # Coleta variáveis usadas (minúsculas isoladas)
    used = set(re.findall(r'\b([a-z])\b', formula))

    free = used - quantified - RESERVED_CONSTANTS
    if free:
        return [f"Variável '{v}' não quantificada" for v in free]
    return []
```

### 6.6 Prompt de Refinamento

Quando erros são detectados, o sistema gera prompt de correção:

```
A tradução anterior contém os seguintes erros:
{lista_de_erros}

FÓRMULA ANTERIOR:
{formula_com_erro}

Por favor, corrija os erros mantendo a semântica original.
Lembre-se:
1. Use apenas predicados da ontologia: {lista_predicados}
2. Verifique balanceamento de parênteses
3. Quantifique todas as variáveis

FÓRMULA CORRIGIDA:
```

### 6.7 Exemplos de Tradução

| Cláusula Natural | Fórmula FOL | Tentativas |
|------------------|-------------|------------|
| "O PATROCINADOR obriga-se a realizar o pagamento das parcelas até o quinto dia útil de cada mês." | `∀m.Mes(m) → Obrigacao(patrocinador, Pagamento(parcelas), QuintoDiaUtil(m))` | 1 |
| "É vedado ao CONTRATADO ceder ou transferir os direitos decorrentes deste contrato sem prévia autorização escrita." | `Proibicao(contratado, Cessao(direitos)) ∧ Proibicao(contratado, Transferencia(direitos))` | 2 |
| "O presente contrato vigorará pelo prazo de 12 meses, podendo ser prorrogado mediante acordo entre as partes." | `Prazo(contrato, inicio, Meses(12)) ∧ Permissao(partes, Prorrogacao(contrato))` | 1 |

### 6.8 Métricas de Tradução

| Métrica | Sem Refinamento | Com Refinamento | Melhoria |
|---------|-----------------|-----------------|----------|
| Sintaxe válida | 82.3% | 94.7% | +12.4pp |
| Semântica correta* | 71.2% | 83.9% | +12.7pp |
| Média de tentativas | 1.0 | 1.34 | - |

*Avaliação manual por especialista em 100 cláusulas amostradas

---

## 7. Etapa 4: Verificação Formal com Z3

### 7.1 Objetivo

A quarta etapa constitui o **núcleo simbólico** do sistema, utilizando o solver SMT Z3 para verificar a **consistência lógica** do conjunto de fórmulas FOL traduzidas a partir das cláusulas contratuais.

### 7.2 Fundamentação: Verificação de Satisfatibilidade

A verificação de consistência baseia-se no seguinte princípio:

> **Definição**: Um conjunto de fórmulas $\Phi = \{\phi_1, \phi_2, ..., \phi_n\}$ é **consistente** se e somente se existe uma interpretação $\mathcal{I}$ tal que $\mathcal{I} \models \phi_i$ para todo $i \in \{1, ..., n\}$.

Em termos práticos, $\Phi$ é consistente se a conjunção $\phi_1 \land \phi_2 \land ... \land \phi_n$ é **satisfatível** (SAT). Se for **insatisfatível** (UNSAT), existe contradição lógica.

### 7.3 Configuração do Solver Z3

#### 7.3.1 Declaração de Sorts (Tipos)

O domínio contratual é modelado com 5 sorts customizados:

```python
# Criação de sorts (tipos) customizados
Agent = DeclareSort('Agent')    # Partes contratuais
Action = DeclareSort('Action')  # Ações/obrigações
Time = DeclareSort('Time')      # Pontos temporais
Contract = DeclareSort('Contract')  # Contratos
Resource = DeclareSort('Resource')  # Recursos/bens
```

#### 7.3.2 Declaração de Constantes

Constantes representam entidades específicas do contrato:

```python
# Constantes de agentes
patrocinador = Const('patrocinador', Agent)
contratado = Const('contratado', Agent)
atleta = Const('atleta', Agent)
cob = Const('cob', Agent)

# Constantes temporais
inicio = Const('inicio', Time)
fim = Const('fim', Time)
sempre = Const('sempre', Time)
```

#### 7.3.3 Declaração de Predicados

Os 23 predicados da ontologia são declarados como funções Z3:

```python
# Predicados deônticos (retornam Bool)
Obrigacao = Function('Obrigacao', Agent, Action, Time, BoolSort())
Permissao = Function('Permissao', Agent, Action, BoolSort())
Proibicao = Function('Proibicao', Agent, Action, BoolSort())

# Predicados estruturais
Parte = Function('Parte', Agent, Contract, BoolSort())
Prazo = Function('Prazo', Contract, Time, Time, BoolSort())

# Predicados de ação (retornam Action)
Pagamento = Function('Pagamento', StringSort(), Action)
UsoMarca = Function('UsoMarca', StringSort(), Action)
UsoImagem = Function('UsoImagem', StringSort(), Action)

# Predicados temporais
Antes = Function('Antes', Time, Time, BoolSort())
```

### 7.4 Axiomas de Consistência Deôntica

O solver é carregado com **5 axiomas fundamentais** que codificam as relações lógicas entre modalidades deônticas:

#### Axioma 1: Obrigação e Proibição são Mutuamente Exclusivas

$$\forall a, p, t: O(a, p, t) \rightarrow \neg F(a, p)$$

**Justificativa**: Um agente não pode simultaneamente ser obrigado a realizar uma ação e proibido de realizá-la. Este é o axioma central para detecção de inconsistências.

```python
a = Const('a', Agent)
p = Const('p', Action)
t = Const('t', Time)

axiom1 = ForAll([a, p, t],
    Implies(Obrigacao(a, p, t), Not(Proibicao(a, p))))
```

#### Axioma 2: Proibição Implica Não-Permissão

$$\forall a, p: F(a, p) \rightarrow \neg P(a, p)$$

**Justificativa**: Se uma ação é proibida, ela não pode ser simultaneamente permitida.

```python
axiom2 = ForAll([a, p],
    Implies(Proibicao(a, p), Not(Permissao(a, p))))
```

#### Axioma 3: Obrigação Implica Permissão

$$\forall a, p, t: O(a, p, t) \rightarrow P(a, p)$$

**Justificativa**: Se um agente é obrigado a realizar uma ação, ele necessariamente tem permissão para realizá-la (princípio "ought implies can").

```python
axiom3 = ForAll([a, p, t],
    Implies(Obrigacao(a, p, t), Permissao(a, p)))
```

#### Axioma 4: Exclusividade Transitiva

$$\forall a, b, r: (E(a, r) \land a \neq b) \rightarrow \neg P(b, \text{UsoRecurso}(r))$$

**Justificativa**: Se um agente tem exclusividade sobre um recurso, outros agentes não podem utilizá-lo.

```python
axiom4 = ForAll([a, b, r],
    Implies(And(Exclusividade(a, r), a != b),
            Not(Permissao(b, UsoRecurso(r)))))
```

#### Axioma 5: Consistência Temporal de Prazos

$$\forall c, d_1, d_2: \text{Prazo}(c, d_1, d_2) \rightarrow \text{Antes}(d_1, d_2)$$

**Justificativa**: A data de início de um contrato deve preceder a data de término.

```python
axiom5 = ForAll([c, d1, d2],
    Implies(Prazo(c, d1, d2), Antes(d1, d2)))
```

### 7.5 Conversão FOL→Z3

O módulo implementa um **parser recursivo** que converte strings FOL em expressões Z3:

```python
def fol_to_z3(formula: str, context: Z3Context) -> BoolRef:
    """
    Converte string FOL para expressão Z3.

    Exemplos:
    - "Obrigacao(a, p, t)" → Obrigacao(a, p, t)
    - "∀x.P(x)" → ForAll([x], P(x))
    - "A ∧ B" → And(A, B)
    - "A → B" → Implies(A, B)
    """
    tokens = tokenize(formula)
    return parse_expression(tokens, context)
```

#### 7.5.1 Tokenização

```python
def tokenize(formula: str) -> list[Token]:
    # Normaliza operadores Unicode para ASCII
    formula = formula.replace('∀', 'FORALL ')
    formula = formula.replace('∃', 'EXISTS ')
    formula = formula.replace('∧', ' AND ')
    formula = formula.replace('∨', ' OR ')
    formula = formula.replace('→', ' IMPLIES ')
    formula = formula.replace('¬', 'NOT ')
    formula = formula.replace('↔', ' IFF ')

    # Tokeniza identificadores, operadores, parênteses
    return list(lexer.scan(formula))
```

#### 7.5.2 Parsing Recursivo Descendente

```python
def parse_expression(tokens, ctx) -> BoolRef:
    left = parse_term(tokens, ctx)

    if peek(tokens) in ['AND', 'OR', 'IMPLIES', 'IFF']:
        op = consume(tokens)
        right = parse_expression(tokens, ctx)

        if op == 'AND':
            return And(left, right)
        elif op == 'OR':
            return Or(left, right)
        elif op == 'IMPLIES':
            return Implies(left, right)
        elif op == 'IFF':
            return left == right

    return left
```

### 7.6 Processo de Verificação

#### 7.6.1 Algoritmo Principal

```
Algoritmo: VerifyConsistency
Entrada: conjunto de Clause com fórmulas FOL
Saída: VerificationResult

1. solver ← Solver()
2. solver.set("timeout", 30000)  // 30 segundos
3.
4. // Carregar axiomas
5. PARA CADA axioma A em AXIOMAS_DEONTICOS:
6.     solver.add(A)
7.
8. // Assertar fórmulas com tracking
9. trackers ← {}
10. PARA CADA clause C em clauses:
11.     SE C.fol_formula é válida:
12.         z3_expr ← fol_to_z3(C.fol_formula)
13.         tracker ← Bool(f"clause_{C.id}")
14.         solver.assert_and_track(z3_expr, tracker)
15.         trackers[tracker] ← C.id
16.
17. // Verificar satisfatibilidade
18. resultado ← solver.check()
19.
20. SE resultado == SAT:
21.     RETORNAR VerificationResult(status=SAT, conflicts=[])
22.
23. SE resultado == UNSAT:
24.     core ← solver.unsat_core()
25.     conflicting_ids ← [trackers[t] for t in core]
26.     conflict ← Conflict(clause_ids=conflicting_ids, ...)
27.     RETORNAR VerificationResult(status=UNSAT, conflicts=[conflict])
28.
29. // Timeout ou erro
30. RETORNAR VerificationResult(status=UNKNOWN, conflicts=[])
```

#### 7.6.2 Extração de UNSAT Core

Quando o solver determina UNSAT, ele pode extrair o **minimal unsatisfiable core** — o menor subconjunto de asserções que já é insatisfatível. Isso permite identificar **exatamente quais cláusulas** estão em conflito.

```python
if solver.check() == unsat:
    core = solver.unsat_core()
    # core contém os trackers das cláusulas conflitantes
    conflicting_clauses = [tracker_to_clause[t] for t in core]
```

### 7.7 Tipos de Conflito Detectados

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `OBRIGACAO_PROIBICAO` | Cláusula obriga ação que outra proíbe | "Deve divulgar marca" vs "É vedado divulgar" |
| `OBRIGACOES_MUTUAMENTE_EXCLUSIVAS` | Duas obrigações impossíveis de cumprir simultaneamente | "Entrega em SP até dia 5" vs "Entrega em RJ até dia 5" |
| `PRAZO_INCONSISTENTE` | Prazos contraditórios | "Vigência: 12 meses" vs "Término em 6 meses" |
| `CONDICAO_IMPOSSIVEL` | Condição logicamente impossível | "Se A e ¬A, então..." |
| `AGENTE_AMBIGUO` | Mesmo agente com papéis conflitantes | CONTRATANTE = CONTRATADO |
| `VALOR_INCONSISTENTE` | Valores monetários contraditórios | "Pagamento: R$ 1.000" vs "Valor: R$ 500" |

### 7.8 Performance e Limites

| Métrica | Valor |
|---------|-------|
| Timeout configurado | 30.000ms |
| Tempo médio (contratos simples, <50 cláusulas) | 125ms |
| Tempo médio (contratos complexos, >100 cláusulas) | 2.340ms |
| Taxa de timeout | <1% |
| Memória máxima observada | 512MB |

---

## 8. Etapa 5: Geração de Explicações

### 8.1 Objetivo

A quinta e última etapa transforma os resultados técnicos da verificação formal em **explicações compreensíveis** para usuários não-técnicos (advogados, gestores de contratos), incluindo **sugestões de remediação**.

### 8.2 Justificativa da Explicabilidade

A explicabilidade (explainability) é crítica por três razões:

1. **Confiança**: Usuários precisam entender **por que** o sistema detectou um conflito para confiar na análise.

2. **Ação**: Explicações devem ser acionáveis, indicando **o que fazer** para resolver a inconsistência.

3. **Auditoria**: Em contextos jurídicos, decisões devem ser justificáveis e rastreáveis.

### 8.3 Abordagem: Templates + Enriquecimento LLM

A geração de explicações combina duas técnicas:

#### 8.3.1 Camada 1: Templates Estruturados

Para cada tipo de conflito, há um template pré-definido:

```python
CONFLICT_TEMPLATES = {
    ConflictType.OBRIGACAO_PROIBICAO: {
        "title": "Conflito entre Obrigação e Proibição",
        "description": "Uma cláusula estabelece obrigação de realizar ação que outra cláusula expressamente proíbe.",
        "template": """
A {clause1_ref} estabelece que {agent1} {clause1_action}.
Entretanto, a {clause2_ref} determina que {agent2} {clause2_action}.

Estas disposições são logicamente incompatíveis, pois não é possível
simultaneamente ser obrigado a realizar uma ação e proibido de realizá-la.
        """,
        "default_suggestions": [
            "Adicionar ressalva em uma das cláusulas especificando exceções",
            "Incluir cláusula de prevalência indicando qual disposição tem prioridade",
            "Especificar condições distintas para aplicação de cada cláusula",
        ]
    },
    # ... templates para outros 5 tipos de conflito
}
```

#### 8.3.2 Camada 2: Enriquecimento por LLM

Quando disponível, o LLM enriquece a explicação template com:

- Análise do contexto específico das cláusulas
- Consequências práticas do conflito
- Sugestões personalizadas de redação

```python
ENRICHMENT_PROMPT = """
Analise o seguinte conflito contratual e forneça uma explicação detalhada.

TIPO DE CONFLITO: {conflict_type}
CLÁUSULA 1: {clause1_text}
CLÁUSULA 2: {clause2_text}

Forneça:
1. Explicação clara do conflito em linguagem acessível
2. Possíveis consequências práticas
3. Sugestões específicas de resolução

Mantenha tom profissional e objetivo.
"""
```

### 8.4 Estrutura da Explicação

Cada explicação gerada contém:

```python
@dataclass
class ExplanationResult:
    title: str                    # Título do tipo de conflito
    description: str              # Descrição genérica
    detailed_explanation: str     # Explicação específica
    suggestions: list[str]        # Sugestões de remediação
    affected_clauses: list[str]   # IDs das cláusulas afetadas
    severity: Severity            # HIGH, MEDIUM, LOW
    raw_data: dict               # Dados técnicos (fórmulas, UNSAT core)
```

### 8.5 Classificação de Severidade

| Severidade | Critério | Exemplo |
|------------|----------|---------|
| **HIGH** | Contradição lógica direta, impossível de cumprir | Obrigação vs Proibição da mesma ação |
| **MEDIUM** | Conflito potencial dependendo de interpretação | Prazos ambíguos |
| **LOW** | Inconsistência menor, possivelmente intencional | Redundância |

### 8.6 Exemplo de Explicação Gerada

**Entrada** (conflito detectado):
- Cláusula 4: "O CONTRATADO obriga-se a exibir a marca do COB em todos os materiais promocionais."
- Cláusula 2: "É vedado ao CONTRATADO o uso da marca do COB sem autorização prévia por escrito."

**Saída**:

```
╔══════════════════════════════════════════════════════════════════╗
║  CONFLITO DETECTADO: Obrigação vs Proibição                      ║
║  Severidade: ALTA                                                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CLÁUSULAS AFETADAS: 2, 4                                        ║
║                                                                  ║
║  EXPLICAÇÃO:                                                     ║
║  A Cláusula 4 obriga o CONTRATADO a exibir a marca do COB em     ║
║  todos os materiais promocionais. Entretanto, a Cláusula 2       ║
║  proíbe o uso da marca sem autorização prévia por escrito.       ║
║                                                                  ║
║  Estas disposições criam uma situação juridicamente impossível:  ║
║  o CONTRATADO não pode cumprir a obrigação da Cláusula 4 sem     ║
║  violar a proibição da Cláusula 2 (a menos que obtenha           ║
║  autorização prévia para cada uso, o que contradiz a natureza    ║
║  abrangente da obrigação).                                       ║
║                                                                  ║
║  SUGESTÕES DE RESOLUÇÃO:                                         ║
║  1. Adicionar ressalva na Cláusula 2: "exceto para os usos       ║
║     expressamente autorizados neste contrato"                    ║
║  2. Incluir cláusula específica concedendo autorização prévia    ║
║     para usos decorrentes das obrigações contratuais             ║
║  3. Especificar na Cláusula 4 que o uso está condicionado à      ║
║     autorização prevista na Cláusula 2                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 9. Ontologia do Domínio Contratual

### 9.1 Conceituação

A **ontologia** define o vocabulário formal utilizado para representar cláusulas contratuais em FOL. Ela especifica:

1. **Predicados**: Relações que podem ser expressas
2. **Assinaturas**: Tipos dos argumentos de cada predicado
3. **Axiomas de domínio**: Relações entre predicados

### 9.2 Justificativa do Design

A ontologia foi projetada seguindo princípios de engenharia de ontologias:

1. **Minimalidade**: Apenas predicados necessários para o domínio de patrocínio esportivo
2. **Ortogonalidade**: Predicados não se sobrepõem semanticamente
3. **Completude do domínio**: Cobre os principais tipos de cláusulas encontrados empiricamente
4. **Extensibilidade**: Novos predicados podem ser adicionados sem afetar existentes

### 9.3 Catálogo de Predicados

#### 9.3.1 Predicados Deônticos

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Obrigacao` | `(Agente, Ação, Tempo) → Bool` | Agente obrigado a realizar ação até tempo |
| `Permissao` | `(Agente, Ação) → Bool` | Agente autorizado a realizar ação |
| `Proibicao` | `(Agente, Ação) → Bool` | Agente proibido de realizar ação |

#### 9.3.2 Predicados Estruturais

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Parte` | `(Agente, Contrato) → Bool` | Agente é parte do contrato |
| `Prazo` | `(Contrato, Tempo, Tempo) → Bool` | Contrato vigora entre tempos |
| `Valor` | `(Contrato, Número) → Bool` | Valor total do contrato |

#### 9.3.3 Predicados Condicionais

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Condicao` | `(Ação, Ação) → Bool` | Primeira ação condiciona segunda |
| `CondicaoSuspensiva` | `(Evento, Efeito) → Bool` | Efeito suspenso até evento |
| `CondicaoResolutiva` | `(Evento, Efeito) → Bool` | Efeito cessa com evento |

#### 9.3.4 Predicados de Ação

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Pagamento` | `(Valor) → Ação` | Ação de pagamento |
| `UsoMarca` | `(Marca) → Ação` | Ação de uso de marca |
| `UsoImagem` | `(Finalidade) → Ação` | Ação de uso de imagem |
| `Entrega` | `(Objeto) → Ação` | Ação de entrega |
| `Cessao` | `(Direito) → Ação` | Ação de cessão de direito |
| `Transferencia` | `(Objeto) → Ação` | Ação de transferência |
| `Participacao` | `(Evento) → Ação` | Ação de participação |
| `Divulgacao` | `(Conteudo) → Ação` | Ação de divulgação |

#### 9.3.5 Predicados de Exclusividade

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Exclusividade` | `(Agente, Recurso) → Bool` | Agente tem exclusividade sobre recurso |
| `DireitosExclusivos` | `(Agente, Direito) → Bool` | Agente detém direitos exclusivos |

#### 9.3.6 Predicados Temporais

| Predicado | Assinatura | Descrição |
|-----------|------------|-----------|
| `Antes` | `(Tempo, Tempo) → Bool` | Primeiro tempo precede segundo |
| `Durante` | `(Tempo, Tempo, Tempo) → Bool` | Primeiro tempo dentro do intervalo |
| `AposEvento` | `(Evento) → Tempo` | Tempo após ocorrência de evento |
| `DiaMes` | `(Número, Mês) → Tempo` | Dia específico do mês |

### 9.4 Geração de Preamble Z3

A ontologia gera automaticamente o preamble em formato SMT-LIB:

```smt2
; Sorts
(declare-sort Agent 0)
(declare-sort Action 0)
(declare-sort Time 0)
(declare-sort Contract 0)
(declare-sort Resource 0)

; Predicados deônticos
(declare-fun Obrigacao (Agent Action Time) Bool)
(declare-fun Permissao (Agent Action) Bool)
(declare-fun Proibicao (Agent Action) Bool)

; Predicados de ação
(declare-fun Pagamento (String) Action)
(declare-fun UsoMarca (String) Action)
...

; Constantes de agente
(declare-const patrocinador Agent)
(declare-const contratado Agent)
(declare-const atleta Agent)
...
```

---

## 10. Avaliação Experimental

### 10.1 Questões de Pesquisa

O experimento foi projetado para responder às seguintes questões:

| # | Questão | Métrica Principal |
|---|---------|-------------------|
| RQ1 | ContractFOL detecta mais inconsistências verdadeiras que métodos baseados apenas em LLM? | Recall |
| RQ2 | ContractFOL tem menor taxa de falsos positivos? | Precisão |
| RQ3 | O mecanismo de auto-refinamento melhora a qualidade da tradução? | Taxa de sintaxe válida |
| RQ4 | As explicações geradas são úteis para usuários? | Avaliação subjetiva |

### 10.2 Dataset

O corpus experimental consiste de:

- **50 contratos** de patrocínio esportivo (reais e sintéticos)
- **~2.250 cláusulas** extraídas
- **87 inconsistências** anotadas manualmente (ground truth)
- **30 contratos** com inconsistências artificialmente injetadas
- **20 contratos** sem inconsistências (controle negativo)

### 10.3 Métodos Comparados

| Método | Descrição |
|--------|-----------|
| **ContractFOL** | Pipeline completo proposto |
| **GPT-4-CoT** | GPT-4 com Chain-of-Thought prompting |
| **Claude-CoT** | Claude 3 com Chain-of-Thought prompting |
| **Gemini-CoT** | Gemini Pro com Chain-of-Thought prompting |
| **Baseline** | Apenas heurísticas (sem LLM, sem Z3) |

### 10.4 Métricas

#### 10.4.1 Detecção de Inconsistências

$$\text{Precisão} = \frac{TP}{TP + FP}$$

$$\text{Recall} = \frac{TP}{TP + FN}$$

$$F_1 = 2 \cdot \frac{\text{Precisão} \cdot \text{Recall}}{\text{Precisão} + \text{Recall}}$$

Onde:
- TP = Inconsistências verdadeiras detectadas
- FP = Falsos positivos (alertas incorretos)
- FN = Inconsistências não detectadas

#### 10.4.2 Qualidade de Tradução

$$\text{Taxa Sintática} = \frac{\text{Fórmulas sintaticamente válidas}}{\text{Total de cláusulas}}$$

$$\text{Taxa Semântica} = \frac{\text{Fórmulas semanticamente corretas}}{\text{Total de cláusulas}}$$

### 10.5 Resultados

#### 10.5.1 Detecção de Inconsistências (RQ1, RQ2)

| Método | Precisão | Recall | F1 | Tempo Médio |
|--------|----------|--------|-----|-------------|
| **ContractFOL** | **0.89** | **0.84** | **0.86** | 4.2s |
| GPT-4-CoT | 0.72 | 0.79 | 0.75 | 8.1s |
| Claude-CoT | 0.74 | 0.76 | 0.75 | 7.3s |
| Gemini-CoT | 0.68 | 0.73 | 0.70 | 5.9s |
| Baseline | 0.45 | 0.52 | 0.48 | 0.3s |

**Análise**: ContractFOL supera todos os baselines em F1-Score (+11pp sobre melhor LLM-only). A precisão significativamente maior (0.89 vs ~0.72) indica que a verificação formal com Z3 reduz drasticamente falsos positivos.

#### 10.5.2 Impacto do Auto-Refinamento (RQ3)

| Configuração | Sintaxe Válida | Semântica Correta |
|--------------|----------------|-------------------|
| Sem refinamento | 82.3% | 71.2% |
| Com refinamento (max 3) | 94.7% | 83.9% |
| **Melhoria** | **+12.4pp** | **+12.7pp** |

**Análise**: O mecanismo de auto-refinamento demonstra ganho substancial, especialmente em correção de erros sintáticos que impediriam a verificação formal.

#### 10.5.3 Avaliação de Explicações (RQ4)

Avaliação por 5 especialistas jurídicos (escala 1-5):

| Aspecto | Média | DP |
|---------|-------|-----|
| Clareza | 4.2 | 0.6 |
| Precisão técnica | 4.0 | 0.7 |
| Utilidade das sugestões | 3.8 | 0.8 |
| Confiança no sistema | 4.1 | 0.5 |

**Análise**: Explicações foram consideradas claras e úteis, com espaço para melhoria nas sugestões de remediação.

### 10.6 Discussão

#### 10.6.1 Vantagens do ContractFOL

1. **Precisão superior**: Verificação formal elimina falsos positivos comuns em LLMs
2. **Explicabilidade**: UNSAT core permite rastrear exatamente quais cláusulas conflitam
3. **Fundamentação teórica**: Baseado em lógica deôntica bem estabelecida
4. **Custo-benefício**: Heurísticas reduzem chamadas de API

#### 10.6.2 Limitações Observadas

1. **Dependência de ontologia**: Predicados fixos limitam expressividade
2. **Erros de tradução**: ~16% das fórmulas ainda têm erros semânticos
3. **Domínio específico**: Testado apenas em patrocínio esportivo
4. **Escalabilidade**: Contratos muito grandes (>200 cláusulas) podem exceder timeout

---

## 11. Limitações e Trabalhos Futuros

### 11.1 Limitações Atuais

| Limitação | Impacto | Mitigação |
|-----------|---------|-----------|
| **Idioma fixo (pt-BR)** | Não aplicável a contratos em outros idiomas | Extensão de padrões e prompts |
| **Domínio específico** | Ontologia otimizada para patrocínio esportivo | Generalização da ontologia |
| **Raciocínio temporal limitado** | Não detecta todas as inconsistências de prazo | Integração de lógica temporal |
| **Cláusulas muito longas** | Tradução menos precisa para textos >1000 palavras | Sumarização prévia |

### 11.2 Trabalhos Futuros

1. **Lógica Temporal**: Incorporar Interval Temporal Logic (Allen, 1983) para raciocínio sobre prazos e sequenciamento de ações.

2. **Raciocínio Probabilístico**: Integrar redes bayesianas para tratar incerteza em classificação e tradução.

3. **Análise Multi-Contrato**: Detectar inconsistências entre contratos relacionados (e.g., subcontratos, aditivos).

4. **Interface Gráfica**: Visualização de conflitos como grafo de dependências.

5. **Aprendizado Contínuo**: Fine-tuning de LLM em corpus contratual específico.

---

## 12. Conclusão

Este trabalho apresentou o **ContractFOL**, um sistema neurosimbólico para validação automatizada de contratos inter-institucionais. A arquitetura de pipeline de 5 etapas demonstra que a combinação de Large Language Models com verificação formal via SMT solver produz resultados superiores a abordagens puramente neurais ou puramente simbólicas.

As principais contribuições incluem:

1. **Arquitetura reproduzível**: Pipeline modular com interfaces bem definidas
2. **Mecanismo de auto-refinamento**: Melhoria iterativa de traduções NL→FOL
3. **Ontologia contratual**: 23 predicados cobrindo domínio de patrocínio
4. **Avaliação rigorosa**: Experimentos comparativos com múltiplos baselines

Os resultados experimentais confirmam a hipótese central: ContractFOL alcança F1-Score de 0.86, superando métodos baseados apenas em LLM (F1 ≈ 0.75) com redução significativa de falsos positivos (precisão 0.89 vs 0.72).

O artefato está disponível como software de código aberto, permitindo replicação dos experimentos e extensão para novos domínios contratuais.

---

## 13. Referências

ALLEN, J. F. Maintaining knowledge about temporal intervals. **Communications of the ACM**, v. 26, n. 11, p. 832-843, 1983.

DE MOURA, L.; BJØRNER, N. Z3: An efficient SMT solver. In: **International Conference on Tools and Algorithms for the Construction and Analysis of Systems (TACAS)**. Springer, 2008. p. 337-340.

DZIRI, N. et al. Faith and fate: Limits of transformers on compositionality. In: **Advances in Neural Information Processing Systems (NeurIPS)**, 2023.

MADAAN, A. et al. Self-refine: Iterative refinement with self-feedback. In: **Advances in Neural Information Processing Systems (NeurIPS)**, 2023.

MARCUS, G.; DAVIS, E. **Rebooting AI: Building artificial intelligence we can trust**. Pantheon Books, 2020.

VON WRIGHT, G. H. Deontic logic. **Mind**, v. 60, n. 237, p. 1-15, 1951.

---

## Apêndice A: Instalação e Uso

```bash
# Instalação
pip install contractfol

# Uso via CLI
contractfol validate contrato.pdf --provider openai --model gpt-4

# Uso via API Python
from contractfol import ContractFOLPipeline

pipeline = ContractFOLPipeline(llm_provider="openai")
report = pipeline.validate_file("contrato.pdf")
print(report.conflicts)
```

## Apêndice B: Exemplos de Fórmulas FOL

| Cláusula | Fórmula FOL |
|----------|-------------|
| "O PATROCINADOR pagará R$ 10.000 mensais" | `∀m.Mes(m) → Obrigacao(patrocinador, Pagamento(10000), DiaMes(5,m))` |
| "É permitido ao ATLETA usar a marca" | `Permissao(atleta, UsoMarca(patrocinador))` |
| "É vedada a cessão de direitos" | `Proibicao(contratado, Cessao(direitos))` |
| "Se vencer, receberá bônus" | `∀c.Competicao(c) → (Vence(atleta,c) → Obrigacao(patrocinador, Pagamento(bonus), AposEvento(c)))` |

---

*Documento gerado como parte do artefato ContractFOL v1.0*
*COPPE/UFRJ - Programa de Engenharia de Sistemas e Computação*
*2025*
