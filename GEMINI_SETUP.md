# Configuração ContractFOL V3 com Google Gemini

## 🚀 Início Rápido

### 1. Configurar Chave da API do Gemini

Opção A: Arquivo `.env` (Recomendado para desenvolvimento)
```bash
# Criar arquivo .env na raiz do projeto
cat > .env << 'EOF'
CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA
CONTRACTFOL_LLM=google
CONTRACTFOL_MODEL=gemini-2.0-flash
CONTRACTFOL_TEMPERATURE=0.7
CONTRACTFOL_MAX_TOKENS=4096
EOF
```

Opção B: Variável de Ambiente
```bash
# Windows (cmd)
set CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA
set CONTRACTFOL_LLM=google
set CONTRACTFOL_MODEL=gemini-2.0-flash

# Windows (PowerShell)
$env:CONTRACTFOL_API_KEY="AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA"
$env:CONTRACTFOL_LLM="google"
$env:CONTRACTFOL_MODEL="gemini-2.0-flash"

# Linux/Mac
export CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA
export CONTRACTFOL_LLM=google
export CONTRACTFOL_MODEL=gemini-2.0-flash
```

### 2. Instalar Dependências

```bash
pip install google-generativeai python-dotenv
```

### 3. Colocar Contratos para Validar

Coloque os arquivos de contrato em:
```
src/contractfol/contractfol/data/input/
```

Formatos suportados:
- `.txt` — Arquivos de texto simples
- `.docx` — Documentos Word
- `.pdf` — Arquivos PDF

### 4. Executar o Pipeline

```bash
python -m contractfol.contractfol.main
```

## 📊 Estrutura de Saídas

O pipeline gera os seguintes arquivos em `src/contractfol/contractfol/data/output/`:

```
output/
├── E1/                    # Cláusulas extraídas (JSON)
├── E2/                    # Estrutura deôntica (JSON)
├── E3/                    # Compilação Z3 (JSON)
├── E4/                    # Problemas detectados (JSON)
├── E5/                    # Relatórios Markdown
├── MAPA_DEONTICO/         # Mapeamento deôntico com rastreabilidade
├── FOL/                   # Fórmulas em lógica de primeira ordem
├── INDICE_GERAL.json      # Resumo de todos os contratos
└── README.md              # Documentação
```

## 🔍 Exemplo de Uso

### Comando Simples
```bash
python -m contractfol.contractfol.main
```

### Em Debug (VSCode)
```json
{
  "name": "ContractFOL Pipeline",
  "type": "python",
  "request": "launch",
  "program": "${workspaceFolder}/src/contractfol/contractfol/main.py",
  "console": "integratedTerminal",
  "justMyCode": true,
  "env": {
    "PYTHONPATH": "${workspaceFolder}/src",
    "CONTRACTFOL_API_KEY": "AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA",
    "CONTRACTFOL_LLM": "google",
    "CONTRACTFOL_MODEL": "gemini-2.0-flash"
  }
}
```

## ⚙️ Configuração Avançada

### Modelos Disponíveis do Gemini

| Modelo | Latência | Custo | Tokens |
|--------|----------|-------|--------|
| `gemini-2.0-flash` | ⚡ Muito rápido | $ Barato | 1M |
| `gemini-1.5-pro` | 🔷 Médio | $$ Moderado | 2M |
| `gemini-1.5-flash` | ⚡ Rápido | $ Barato | 1M |

### Variáveis de Ambiente

```bash
# LLM Provider
CONTRACTFOL_LLM=google              # Usar Google Gemini
CONTRACTFOL_MODEL=gemini-2.0-flash  # Modelo específico
CONTRACTFOL_API_KEY=...             # Chave da API

# Parâmetros de Geração
CONTRACTFOL_TEMPERATURE=0.7         # Criatividade (0.0-1.0)
CONTRACTFOL_MAX_TOKENS=4096         # Tamanho máximo de resposta

# Z3 Solver
Z3_TIMEOUT_MS=30000                 # Timeout para resolução
Z3_MAX_MEMORY_MB=4096               # Memória máxima

# Pipeline
CONFIDENCE_THRESHOLD=0.7            # Confiança mínima
MIN_OBRIGACOES_COM_PENALIDADE=0.5   # % mínima de penalidades
```

## 🛡️ Segurança

⚠️ **IMPORTANTE:** Nunca committe o arquivo `.env` com sua chave!

```bash
# Adicionar ao .gitignore
echo ".env" >> .gitignore
echo "*.local.json" >> .gitignore
```

## 🔧 Troubleshooting

### Erro: "Chave API inválida"
```
Solução: Verifique a chave em .env ou variável de ambiente
CONTRACTFOL_API_KEY=AIzaSyCApJ6f7PVLi5HKNknBHHi61FFyTfll8IA
```

### Erro: "Módulo google.generativeai não encontrado"
```bash
pip install --upgrade google-generativeai
```

### Erro em Debug VSCode
- Use variáveis de ambiente em vez de argumentos CLI
- Verifique se PYTHONPATH inclui `src/`
- Reinicie o VSCode após mudar .env

## 📚 Saídas do Pipeline

### E1 — Pré-processamento
- Extrai cláusulas do contrato
- Identifica contratante e contratado
- Arquivo: `contrato_E1_{nome}.json`

### E2 — Extração Estruturada
- Classifica cláusulas (obrigação, proibição, permissão, etc.)
- Extrai agentes, ações, prazos, valores
- Arquivo: `contrato_E2_{nome}.json`

### MAPA_DEONTICO — Rastreabilidade
- Mapeia sentenças deônticas às cláusulas originais
- Permite auditoria completa
- Arquivo: `mapa_deontico_{nome}.json`

### FOL — Fórmulas Lógicas
- Traduz para Lógica de Primeira Ordem
- Inclui código Z3 para verificação
- Arquivo: `formulas_fol_{nome}.json`

### E4 — Análise Formal
- 6 verificações formais (SAT/UNSAT, contradições, prazos, etc.)
- Detecta problemas estruturais
- Arquivo: `contrato_E4_{nome}.json`

### E5 — Relatório
- Relatório humanizado em Markdown
- Notação deôntica + FOL para problemas
- Arquivo: `relatorio_{timestamp}.md`

## 🎯 Casos de Uso

### 1. Validar um Contrato
```bash
# Colocar em data/input/meu_contrato.docx
python -m contractfol.contractfol.main
# Saída em data/output/
```

### 2. Validar Lote de Contratos
```bash
# Colocar vários arquivos em data/input/
# contratos_1.txt
# contratos_2.docx
# contratos_3.pdf
python -m contractfol.contractfol.main
# Saída em data/output/ com um relatório para cada
```

### 3. Integração com Seu Sistema
```python
from contractfol.contractfol.main import processar_contratos

# Processa todos os contratos e retorna resultados
processar_contratos()
```

## 📝 Exemplo de Output

```markdown
## Resumo de Contratos Processados

| Contrato | Contratante | Contratado | Cláusulas | Confiança | Problemas | Status |
|----------|-------------|-----------|-----------|-----------|-----------|--------|
| contrato_1.txt | Empresa A | Empresa B | 15 | 92% | 2 | ✅ |
| contrato_2.docx | Org X | Org Y | 12 | 88% | 0 | ✅ |

📁 Saídas salvas em: data/output/
   ├── E1/ (cláusulas extraídas)
   ├── E2/ (estrutura deôntica)
   ├── E3/ (compilação Z3)
   ├── E4/ (análise formal)
   ├── E5/ (relatórios markdown)
   ├── MAPA_DEONTICO/ (rastreabilidade)
   ├── FOL/ (fórmulas lógicas)
   └── INDICE_GERAL.json
```

## 🤝 Próximos Passos

1. ✅ Testar com contratos reais
2. ⏳ Refinar prompts do LLM baseado em feedback
3. 📊 Gerar análises agregadas de múltiplos contratos
4. 🔗 Integrar com seu sistema existente
5. 📈 Implementar métricas de qualidade
