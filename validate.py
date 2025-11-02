import os
import glob
from typing import List, Dict, Tuple
from PyPDF2 import PdfReader
import anthropic
import json

class VerusLMKnowledgeBaseGenerator:
    """
    Gera uma base de conhecimento no formato FO(·) (IDP-Z3) compatível com VERUS-LM
    a partir de documentos PDF, utilizando um LLM para extrair símbolos e fórmulas.
    """
    
    def __init__(self, 
                 documents_folder: str = "documentos",
                 output_file: str = "knowledge_base.idp",
                 api_key: str = None):
        """
        Inicializa o gerador de base de conhecimento.
        
        Args:
            documents_folder: Pasta contendo os arquivos PDF
            output_file: Nome do arquivo de saída com a base de conhecimento
            api_key: Chave API para o modelo de linguagem (Claude/Anthropic)
        """
        self.documents_folder = documents_folder
        self.output_file = output_file
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.domain_knowledge = ""
        
    def extract_text_from_pdfs(self) -> str:
        """
        Extrai texto de todos os PDFs na pasta de documentos.
        
        Returns:
            String com todo o texto concatenado dos PDFs
        """
        # Verificar se a pasta existe
        if not os.path.exists(self.documents_folder):
            print(f"Criando pasta '{self.documents_folder}'...")
            os.makedirs(self.documents_folder)
            print(f"Pasta criada. Por favor, adicione arquivos PDF à pasta '{self.documents_folder}'.")
            return ""
        
        # Encontrar todos os arquivos PDF
        pdf_files = glob.glob(os.path.join(self.documents_folder, "*.pdf"))
        
        if not pdf_files:
            print(f"Nenhum arquivo PDF encontrado em '{self.documents_folder}'.")
            return ""
        
        print(f"\nEncontrados {len(pdf_files)} arquivo(s) PDF.")
        print("Extraindo texto dos documentos...\n")
        
        all_text = []
        
        # Processar cada PDF
        for pdf_file in pdf_files:
            print(f"Processando: {os.path.basename(pdf_file)}")
            try:
                reader = PdfReader(pdf_file)
                pdf_text = []
                
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        pdf_text.append(text.strip())
                
                combined_text = "\n".join(pdf_text)
                all_text.append(f"=== Document: {os.path.basename(pdf_file)} ===\n{combined_text}\n")
                print(f"  ✓ {len(reader.pages)} páginas processadas")
                
            except Exception as e:
                print(f"  ✗ Erro ao processar: {str(e)}")
        
        self.domain_knowledge = "\n\n".join(all_text)
        return self.domain_knowledge
    
    def extract_symbols_with_llm(self, domain_text: str) -> Dict[str, List]:
        """
        Usa um LLM para extrair tipos, predicados e funções do domínio.
        Segue a fase de "Symbol Extraction" do VERUS-LM.
        
        Args:
            domain_text: Texto descrevendo o domínio do problema
            
        Returns:
            Dicionário com tipos, predicados e funções extraídos
        """
        print("\n=== FASE 1: EXTRAÇÃO DE SÍMBOLOS ===\n")
        
        prompt = f"""You are an expert in formal logic and knowledge representation. Your task is to extract the vocabulary (types, predicates, and functions) from a domain description to create a knowledge base in FO(·) logic for the IDP-Z3 reasoning engine.

Given the following domain description, identify:

1. TYPES: Custom types that represent categories or sets of entities in the domain
   - Use capitalized names (e.g., Person, Car, BMILevel)
   - Can be defined as enumerations or ranges
   - Include built-in types when needed: Bool (𝔹), Int (ℤ), Real (ℝ)

2. PREDICATES: Boolean-valued relations between entities
   - Use lowercase names (e.g., applicant, symmetric)
   - Specify argument types
   - Format: predicate_name : Type1 × Type2 × ... → Bool

3. FUNCTIONS: Mappings from entities to values
   - Use lowercase names (e.g., age, weight, bmi)
   - Specify input and output types
   - Format: function_name : Type1 × Type2 × ... → OutputType
   - Constants are 0-ary functions: constant_name : () → Type

For each symbol, provide:
- The symbol declaration
- An informal meaning/description

DOMAIN DESCRIPTION:
{domain_text[:3000]}

Please extract the vocabulary in the following JSON format:
{{
  "types": [
    {{"name": "TypeName", "definition": "{{value1, value2, ...}}", "meaning": "Informal description"}},
    ...
  ],
  "predicates": [
    {{"name": "predicate_name", "signature": "Type1 × Type2 → Bool", "meaning": "Informal description"}},
    ...
  ],
  "functions": [
    {{"name": "function_name", "signature": "Type1 × Type2 → OutputType", "meaning": "Informal description"}},
    ...
  ]
}}

Respond ONLY with valid JSON."""

        if self.client:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            # Extrair JSON da resposta
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            json_str = result_text[start_idx:end_idx]
            symbols = json.loads(json_str)
        else:
            # Fallback: retornar estrutura vazia se não houver API
            print("AVISO: Nenhuma API key fornecida. Usando extração manual.")
            symbols = {
                "types": [],
                "predicates": [],
                "functions": []
            }
        
        print(f"✓ Extraídos: {len(symbols['types'])} tipos, {len(symbols['predicates'])} predicados, {len(symbols['functions'])} funções")
        return symbols
    
    def extract_formulas_with_llm(self, domain_text: str, symbols: Dict) -> List[str]:
        """
        Usa um LLM para gerar fórmulas FO(·) que representam o conhecimento do domínio.
        Segue a fase de "Formula Extraction" do VERUS-LM.
        
        Args:
            domain_text: Texto descrevendo o domínio do problema
            symbols: Símbolos extraídos (tipos, predicados, funções)
            
        Returns:
            Lista de fórmulas FO(·)
        """
        print("\n=== FASE 2: EXTRAÇÃO DE FÓRMULAS ===\n")
        
        symbols_str = json.dumps(symbols, indent=2)
        
        prompt = f"""You are an expert in translating natural language domain knowledge into First-Order Logic with extensions (FO(·)) for the IDP-Z3 reasoning engine.

VOCABULARY (already extracted):
{symbols_str}

FO(·) SYNTAX OVERVIEW:
- Logical connectives: ∧ (and), ∨ (or), ¬ (not), ⇒ (implies), ⇔ (iff), ⇐ (implied by)
- Quantifiers: ∀x in Type: φ (for all), ∃x in Type: φ (exists)
- Comparisons: <, ≤, =, ≥, >, ≠
- Arithmetic: +, -, *, /, ^, %
- Aggregates: #{x in Type: φ} (cardinality), sum{{x in Type: φ : term}}
- Definitions use rules: head ← body (or <- in ASCII)
- Constraints end with '.'

DOMAIN DESCRIPTION:
{domain_text[:4000]}

Your task is to generate FO(·) formulas that capture the knowledge in this domain. Consider:
1. Constraints (axioms): Universal truths that must hold
2. Definitions: Rules that define predicates/functions in terms of others
3. Implicit knowledge: Common sense facts that should be made explicit
4. Conditional logic: If-then relationships

Generate formulas in the following categories:

CONSTRAINTS (axioms that must be satisfied):
- Format: ∀x in Type, y in Type: condition ⇒ conclusion.
- Example: ∀x in Person: age(x) >= 0.

DEFINITIONS (inductive/recursive definitions):
- Format: {{ symbol(args) ← condition. }}
- Example: {{ ∀x: adult(x) ← age(x) >= 18. }}

Provide your answer as a JSON object:
{{
  "constraints": ["formula1.", "formula2.", ...],
  "definitions": ["{{ rule1 }}", "{{ rule2 }}", ...]
}}

Respond ONLY with valid JSON."""

        if self.client:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            # Extrair JSON da resposta
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            json_str = result_text[start_idx:end_idx]
            formulas_dict = json.loads(json_str)
            
            all_formulas = formulas_dict.get("constraints", []) + formulas_dict.get("definitions", [])
        else:
            print("AVISO: Nenhuma API key fornecida. Usando extração manual.")
            all_formulas = []
        
        print(f"✓ Extraídas {len(all_formulas)} fórmulas")
        return all_formulas
    
    def generate_idp_knowledge_base(self, symbols: Dict, formulas: List[str]) -> str:
        """
        Gera o código IDP-Z3 completo no formato FO(·).
        
        Args:
            symbols: Dicionário com tipos, predicados e funções
            formulas: Lista de fórmulas lógicas
            
        Returns:
            String com o código IDP-Z3 completo
        """
        print("\n=== FASE 3: GERAÇÃO DA BASE DE CONHECIMENTO ===\n")
        
        kb_lines = []
        
        # Cabeçalho
        kb_lines.append("// Knowledge Base generated from PDF documents")
        kb_lines.append("// Compatible with IDP-Z3 and VERUS-LM framework")
        kb_lines.append("// Format: FO(·) - First-Order Logic with extensions\n")
        
        # Vocabulary block
        kb_lines.append("vocabulary V {")
        kb_lines.append("    // Types")
        
        for type_def in symbols.get("types", []):
            if "definition" in type_def and type_def["definition"]:
                kb_lines.append(f"    type {type_def['name']} := {type_def['definition']}")
            else:
                kb_lines.append(f"    type {type_def['name']}")
            kb_lines.append(f"    // {type_def.get('meaning', '')}")
        
        kb_lines.append("\n    // Predicates")
        for pred in symbols.get("predicates", []):
            kb_lines.append(f"    {pred['name']} : {pred['signature']}")
            kb_lines.append(f"    // {pred.get('meaning', '')}")
        
        kb_lines.append("\n    // Functions and Constants")
        for func in symbols.get("functions", []):
            kb_lines.append(f"    {func['name']} : {func['signature']}")
            kb_lines.append(f"    // {func.get('meaning', '')}")
        
        kb_lines.append("}\n")
        
        # Theory block
        kb_lines.append("theory T:V {")
        kb_lines.append("    // Domain knowledge formalized as FO(·) formulas\n")
        
        for formula in formulas:
            kb_lines.append(f"    {formula}")
        
        kb_lines.append("}\n")
        
        # Structure block (optional - for initial facts)
        kb_lines.append("structure S:V {")
        kb_lines.append("    // Initial facts and interpretations can be specified here")
        kb_lines.append("    // Example: person := {john, mary}")
        kb_lines.append("}\n")
        
        # Display block (for Interactive Consultant)
        kb_lines.append("display {")
        kb_lines.append("    // Configuration for the user interface")
        kb_lines.append("}\n")
        
        # Main block (optional - for execution)
        kb_lines.append("procedure main() {")
        kb_lines.append("    // Inference procedures")
        kb_lines.append("    // print(model_expand(T, S))")
        kb_lines.append("    // print(model_propagate(T, S))")
        kb_lines.append("}")
        
        return "\n".join(kb_lines)
    
    def generate_from_example(self, example_text: str) -> str:
        """
        Gera uma base de conhecimento a partir de um exemplo em linguagem natural
        (como o exemplo de BMI fornecido pelo usuário).
        
        Args:
            example_text: Texto em linguagem natural descrevendo o domínio
            
        Returns:
            String com o código IDP-Z3 completo
        """
        print("\n" + "="*80)
        print("GERANDO BASE DE CONHECIMENTO NO FORMATO VERUS-LM (FO(·))")
        print("="*80)
        
        # Extrair símbolos
        symbols = self.extract_symbols_with_llm(example_text)
        
        # Extrair fórmulas
        formulas = self.extract_formulas_with_llm(example_text, symbols)
        
        # Gerar base de conhecimento completa
        knowledge_base = self.generate_idp_knowledge_base(symbols, formulas)
        
        # Salvar em arquivo
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(knowledge_base)
        
        print(f"\n✓ Base de conhecimento gerada com sucesso!")
        print(f"  Arquivo: {self.output_file}")
        print(f"  Tipos: {len(symbols.get('types', []))}")
        print(f"  Predicados: {len(symbols.get('predicates', []))}")
        print(f"  Funções: {len(symbols.get('functions', []))}")
        print(f"  Fórmulas: {len(formulas)}")
        
        return knowledge_base
    
    def process_pdfs(self) -> str:
        """
        Processa todos os PDFs na pasta e gera a base de conhecimento.
        
        Returns:
            String com o código IDP-Z3 completo
        """
        # Extrair texto dos PDFs
        domain_text = self.extract_text_from_pdfs()
        
        if not domain_text:
            print("Nenhum conteúdo extraído. Encerrando.")
            return ""
        
        # Gerar base de conhecimento
        return self.generate_from_example(domain_text)


def create_bmi_knowledge_base_manual() -> str:
    """
    Cria manualmente uma base de conhecimento para o exemplo de BMI fornecido pelo usuário,
    seguindo o formato FO(·) do IDP-Z3.
    
    Returns:
        String com o código IDP-Z3 completo
    """
    kb = """// Knowledge Base: BMI Health Risk Assessment
// This knowledge base uses BMI calculated using the general formula (weight / height * height).
// Compatible with IDP-Z3 and VERUS-LM framework

vocabulary V {
    // Types
    type Sex := {male, female}
    // The biological sex of a person
    
    type BMILevel := {severely_underweight, underweight, normal, overweight, obese_I, obese_II, extreme_obesity}
    // Categories of Body Mass Index
    
    type RiskLevel := {low, increased, high, very_high, extremely_high}
    // Health risk levels associated with BMI and waist measurements
    
    type Person
    // A person being assessed for health risks
    
    // Functions and Constants
    weight : Person -> Real
    // The weight of a person in kilograms (kg)
    
    height : Person -> Real
    // The height of a person in meters (m)
    
    waist : Person -> Real
    // The waist circumference of a person in centimeters (cm)
    
    sex : Person -> Sex
    // The biological sex of a person
    
    bmi : Person -> Real
    // The Body Mass Index calculated for a person
    
    bmi_level : Person -> BMILevel
    // The BMI category classification for a person
    
    risk_level : Person -> RiskLevel
    // The health risk level for a person
}

theory T:V {
    // Domain knowledge formalized as FO(·) formulas
    
    // ========================================
    // DOMAIN CONSTRAINTS (Valid Ranges)
    // ========================================
    
    // Height must be between 0 and 3 meters
    !p in Person: height(p) > 0 & height(p) =< 3.
    
    // Weight must be between 0 and 200 kg
    !p in Person: weight(p) > 0 & weight(p) =< 200.
    
    // Waist circumference must be between 0 and 200 cm
    !p in Person: waist(p) >= 0 & waist(p) =< 200.
    
    // ========================================
    // BMI CALCULATION DEFINITION
    // ========================================
    
    {
        // BMI is calculated as weight / (height * height)
        !p in Person: bmi(p) = weight(p) / (height(p) * height(p)).
    }
    
    // ========================================
    // BMI LEVEL CLASSIFICATION RULES
    // ========================================
    
    {
        // Severely Underweight: BMI < 18.5 and male
        !p in Person: bmi_level(p) = severely_underweight <- 
            bmi(p) < 18.5 & sex(p) = male.
        
        // Underweight: (BMI < 18.5 and female) OR (BMI >= 18.5 and BMI < 25 and male)
        !p in Person: bmi_level(p) = underweight <- 
            (bmi(p) < 18.5 & sex(p) = female) | 
            (bmi(p) >= 18.5 & bmi(p) < 25 & sex(p) = male).
        
        // Normal: (BMI >= 18.5 and BMI < 25 and female) OR (BMI >= 25 and BMI < 30 and male)
        !p in Person: bmi_level(p) = normal <- 
            (bmi(p) >= 18.5 & bmi(p) < 25 & sex(p) = female) | 
            (bmi(p) >= 25 & bmi(p) < 30 & sex(p) = male).
        
        // Overweight: BMI >= 25 and BMI < 30 and female
        !p in Person: bmi_level(p) = overweight <- 
            bmi(p) >= 25 & bmi(p) < 30 & sex(p) = female.
        
        // Obese I: BMI >= 30 and BMI < 35
        !p in Person: bmi_level(p) = obese_I <- 
            bmi(p) >= 30 & bmi(p) < 35.
        
        // Obese II: BMI >= 35 and BMI < 40
        !p in Person: bmi_level(p) = obese_II <- 
            bmi(p) >= 35 & bmi(p) < 40.
        
        // Extreme Obesity: BMI >= 40
        !p in Person: bmi_level(p) = extreme_obesity <- 
            bmi(p) >= 40.
    }
    
    // ========================================
    // RISK LEVEL CLASSIFICATION RULES
    // ========================================
    
    {
        // Low Risk: No significant BMI concerns
        !p in Person: risk_level(p) = low <- 
            bmi_level(p) ~= overweight & 
            bmi_level(p) ~= obese_I & 
            bmi_level(p) ~= obese_II & 
            bmi_level(p) ~= extreme_obesity.
        
        // Increased Risk: Overweight with acceptable waist circumference
        !p in Person: risk_level(p) = increased <- 
            (bmi_level(p) = overweight & sex(p) = male & waist(p) < 102) |
            (bmi_level(p) = overweight & sex(p) = female & waist(p) =< 88).
        
        // High Risk: Overweight with high waist OR Obese I with acceptable waist
        !p in Person: risk_level(p) = high <- 
            (bmi_level(p) = overweight & sex(p) = male & waist(p) > 102) |
            (bmi_level(p) = overweight & sex(p) = female & waist(p) > 88) |
            (bmi_level(p) = obese_I & sex(p) = male & waist(p) < 102) |
            (bmi_level(p) = obese_I & sex(p) = female & waist(p) < 88).
        
        // Very High Risk: Obese I with high waist OR Obese II
        !p in Person: risk_level(p) = very_high <- 
            (bmi_level(p) = obese_I & sex(p) = male & waist(p) > 102) |
            (bmi_level(p) = obese_I & sex(p) = female & waist(p) > 88) |
            (bmi_level(p) = obese_II).
        
        // Extremely High Risk: Extreme Obesity
        !p in Person: risk_level(p) = extremely_high <- 
            bmi_level(p) = extreme_obesity.
    }
}

structure S:V {
    // Initial facts and interpretations can be specified here
    // Example structure for testing:
    // Person := {person1}
    // weight := {person1 -> 75.0}
    // height := {person1 -> 1.75}
    // sex := {person1 -> male}
    // waist := {person1 -> 95.0}
}

display {
    // Configuration for the user interface
    expand(`bmi).
    expand(`bmi_level).
    expand(`risk_level).
    relevant(`weight, `height, `waist, `sex).
    goal(`risk_level).
}

procedure main() {
    // Inference procedures
    // Uncomment to run different reasoning tasks:
    
    // Check if the theory is satisfiable
    // print(model_check(T, S))
    
    // Find models (solutions) expanding the structure
    // print(model_expand(T, S))
    
    // Propagate consequences
    // print(model_propagate(T, S))
}
"""
    return kb


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("GERADOR DE BASE DE CONHECIMENTO VERUS-LM/IDP-Z3")
    print("="*80)
    
    # Opção 1: Gerar base de conhecimento manualmente do exemplo de BMI
    print("\n[OPÇÃO 1] Gerando base de conhecimento manual do exemplo BMI...")
    bmi_kb = create_bmi_knowledge_base_manual()
    
    with open("bmi_knowledge_base.idp", 'w', encoding='utf-8') as f:
        f.write(bmi_kb)
    
    print(f"\n✓ Base de conhecimento BMI gerada: bmi_knowledge_base.idp")
    print("\nPrimeiras linhas:")
    print("-" * 80)
    print('\n'.join(bmi_kb.split('\n')[:30]))
    print("-" * 80)
    
    # Opção 2: Gerar a partir de PDFs (requer API key)
    print("\n\n[OPÇÃO 2] Geração a partir de PDFs")
    print("Para gerar a partir de PDFs, você precisa:")
    print("1. Adicionar arquivos PDF à pasta 'documentos/'")
    print("2. Fornecer uma API key do Anthropic Claude")
    print("\nExemplo de uso:")
    print("-" * 80)
    print("""
# Configurar com sua API key
kb_gen = VerusLMKnowledgeBaseGenerator(
    documents_folder="documentos",
    output_file="knowledge_base.idp",
    api_key="sua_api_key_aqui"  # Obter em: https://console.anthropic.com/
)

# Processar PDFs e gerar base de conhecimento
knowledge_base = kb_gen.process_pdfs()

# Ou gerar a partir de texto direto
example_text = \"\"\"
Seu domínio de conhecimento aqui...
\"\"\"
knowledge_base = kb_gen.generate_from_example(example_text)
""")
    print("-" * 80)
    
    print("\n✓ Processo concluído!")
    print("\nA base de conhecimento gerada pode ser usada com:")
    print("  - IDP-Z3 reasoning engine: https://docs.idp-z3.be/")
    print("  - VERUS-LM framework para raciocínio neurossimbólico")
