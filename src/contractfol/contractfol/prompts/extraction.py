"""Prompts para E2 — Extração estruturada de cláusulas."""

import json
from typing import Tuple

# Exemplos few-shot do domínio contratual brasileiro
FEW_SHOT_EXAMPLES = [
    {
        "clausula": "O COB deverá repassar os recursos financeiros em até 30 dias após a aprovação da prestação de contas parcial.",
        "json": {
            "tipo_deontico": "obrigacao",
            "agente": "COB",
            "acao": "repassar recursos financeiros",
            "objeto": "à Confederação",
            "condicao": "após aprovação da prestação de contas parcial",
            "prazo": {
                "valor": 30,
                "unidade": "dias",
                "referencia": "aprovação prestação de contas"
            },
            "valor": None,
            "penalidade_ref": None,
            "formula_fol": "∀x [PCAprovada(x) → Obrigacao(COB, Repassar(x)) ∧ Prazo(Repassar, 30dias)]",
            "codigo_z3": "obrigacao_cob_repassar = Bool('ob_cob_repassar')\nprazo_repassar = Int('pz_repassar')\ns.add(obrigacao_cob_repassar == True)\ns.add(prazo_repassar == 30)",
            "confianca": 0.95,
            "ambiguidades": []
        }
    },
    {
        "clausula": "É vedado à Confederação utilizar os recursos do convênio para pagamento de despesas com pessoal permanente.",
        "json": {
            "tipo_deontico": "proibicao",
            "agente": "Confederação",
            "acao": "pagar despesas com pessoal permanente",
            "objeto": "com recursos do convênio",
            "condicao": None,
            "prazo": None,
            "valor": None,
            "penalidade_ref": None,
            "formula_fol": "∀r [RecursoConvenio(r) → ¬Proibicao(Confederacao, PagarPessoalPermanente(r))]",
            "codigo_z3": "proib_conf_pessoal_perm = Bool('pr_conf_pessoal_perm')\ns.add(proib_conf_pessoal_perm == True)",
            "confianca": 0.94,
            "ambiguidades": []
        }
    },
    {
        "clausula": "A Confederação deverá apresentar prestação de contas parcial a cada 90 dias.",
        "json": {
            "tipo_deontico": "obrigacao",
            "agente": "Confederação",
            "acao": "apresentar prestação de contas parcial",
            "objeto": "ao COB",
            "condicao": None,
            "prazo": {
                "valor": 90,
                "unidade": "dias",
                "referencia": "periodicidade"
            },
            "valor": None,
            "penalidade_ref": None,
            "formula_fol": "∀t [Obrigacao(Confederacao, ApresentarPC(t)) ∧ Periodo(PC, 90dias)]",
            "codigo_z3": "obrigacao_conf_pc = Bool('ob_conf_pc')\nperiodo_pc = Int('pd_pc')\ns.add(obrigacao_conf_pc == True)\ns.add(periodo_pc == 90)",
            "confianca": 0.93,
            "ambiguidades": []
        }
    }
]

SYSTEM_PROMPT = """Você é um especialista em análise contratual e lógica formal.

Sua tarefa é ESTRUTURAR uma cláusula contratual em JSON com os seguintes campos:

- tipo_deontico: obrigacao | proibicao | permissao | direito | condicao | penalidade | definicao
- agente: quem age (ex: COB, Confederação)
- acao: o quê (ex: repassar recursos, apresentar contas)
- objeto: sobre o quê (ex: ao COB, para pessoal permanente) [opcional]
- condicao: se, quando, caso (ex: após aprovação) [opcional]
- prazo: {valor: int, unidade: str, referencia: str} [opcional]
- valor: {montante: float, descricao: str} [opcional]
- penalidade_ref: ID da cláusula de penalidade se aplicável [opcional]
- formula_fol: fórmula em notação FOL legível (ex: ∀x [P(x) → Q(x)])
- codigo_z3: código Z3 auto-contido que declara variáveis e adiciona restrições
- confianca: float 0-1 (0.9+ claro, 0.7-0.9 razoável, <0.7 ambíguo)
- ambiguidades: lista de ambiguidades detectadas

Regras de mapeamento:
- "deverá", "deve", "fica obrigado" → obrigacao
- "é vedado", "não poderá", "fica proibido" → proibicao
- "poderá", "é facultado", "tem a faculdade" → permissao
- "tem direito", "faz jus a" → direito

O codigo_z3 deve ser Python puro: declara Bool() e Int() para variáveis, e s.add() para restrições.

Responda APENAS em JSON válido, sem texto adicional."""


def build_prompt_extracao(clausula_texto: str) -> Tuple[str, str]:
    """Constrói prompts para E2."""
    exemplos = "\n\n".join(
        f"Exemplo {i+1}:\n"
        f"Cláusula: \"{ex['clausula']}\"\n"
        f"JSON:\n{json.dumps(ex['json'], ensure_ascii=False, indent=2)}"
        for i, ex in enumerate(FEW_SHOT_EXAMPLES)
    )

    system = SYSTEM_PROMPT + f"\n\n## Exemplos Few-Shot:\n{exemplos}"
    user = f"""Estruture esta cláusula em JSON:

\"\"\"{clausula_texto}\"\"\"

Responda com JSON válido apenas."""

    return system, user
