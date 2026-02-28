"""
Ontologia de Domínio ContractFOL.

Define os predicados fundamentais para representação de cláusulas contratuais
em Lógica de Primeira Ordem (FOL), conforme Tabela 5.1 da dissertação.

Predicados Fundamentais:
- Obrigacao(a, p, t): Agente a é obrigado a realizar ação/condição p até tempo t
- Permissao(a, p): Agente a é permitido realizar ação/condição p
- Proibicao(a, p): Agente a é proibido de realizar ação/condição p
- Parte(x, c): Entidade x é parte do contrato c
- Prazo(c, d1, d2): Contrato c tem vigência de d1 a d2
- Condicao(p, q): Condição p implica consequência q
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Predicate:
    """Define um predicado da ontologia."""

    name: str
    arity: int
    description: str
    argument_types: list[str]
    argument_names: list[str]
    examples: list[str] = field(default_factory=list)

    def signature(self) -> str:
        """Retorna a assinatura do predicado."""
        args = ", ".join(self.argument_names)
        return f"{self.name}({args})"

    def to_z3_declaration(self) -> str:
        """Gera declaração SMT-LIB para Z3."""
        type_map = {
            "Agente": "Agent",
            "Acao": "Action",
            "Tempo": "Time",
            "Contrato": "Contract",
            "Data": "Date",
            "Condicao": "Condition",
            "Bool": "Bool",
            "Int": "Int",
            "Real": "Real",
            "String": "String",
        }
        z3_types = [type_map.get(t, t) for t in self.argument_types]
        types_str = " ".join(z3_types)
        return f"(declare-fun {self.name} ({types_str}) Bool)"


class ContractOntology:
    """
    Ontologia de domínio para validação de contratos.

    Implementa os predicados fundamentais descritos na Seção 5.2 da dissertação
    e os axiomas de consistência para detecção de conflitos.
    """

    def __init__(self):
        self.predicates: dict[str, Predicate] = {}
        self.axioms: list[str] = []
        self.sorts: dict[str, str] = {}

        self._define_sorts()
        self._define_predicates()
        self._define_axioms()

    def _define_sorts(self):
        """Define os tipos (sorts) da ontologia."""
        self.sorts = {
            "Agent": "Representa um agente/parte contratual",
            "Action": "Representa uma ação ou condição",
            "Time": "Representa um ponto no tempo",
            "Contract": "Representa um contrato",
            "Date": "Representa uma data",
            "Value": "Representa um valor monetário",
            "Resource": "Representa um recurso (marca, imagem, etc.)",
        }

    def _define_predicates(self):
        """Define os predicados fundamentais da ontologia."""

        # Predicados Deônticos (baseados em Von Wright, 1951)
        self._add_predicate(
            "Obrigacao",
            3,
            "Agente a é obrigado a realizar ação/condição p até tempo t",
            ["Agente", "Acao", "Tempo"],
            ["agente", "acao", "prazo"],
            [
                "Obrigacao(patrocinador, Pagamento(parcelas), QuintoDiaUtil(m))",
                "Obrigacao(contratado, Entrega(relatorio), FimMes)",
            ],
        )

        self._add_predicate(
            "Permissao",
            2,
            "Agente a é permitido realizar ação/condição p",
            ["Agente", "Acao"],
            ["agente", "acao"],
            [
                "Permissao(atleta, UsoImagem(fins_comerciais))",
                "Permissao(patrocinador, Divulgacao(parceria))",
            ],
        )

        self._add_predicate(
            "Proibicao",
            2,
            "Agente a é proibido de realizar ação/condição p",
            ["Agente", "Acao"],
            ["agente", "acao"],
            [
                "Proibicao(contratado, UsoMarca(sem_autorizacao))",
                "Proibicao(atleta, ContratoConcorrente)",
            ],
        )

        # Predicados Estruturais
        self._add_predicate(
            "Parte",
            2,
            "Entidade x é parte do contrato c",
            ["Agente", "Contrato"],
            ["entidade", "contrato"],
            ["Parte(cob, contrato_patrocinio_001)", "Parte(atleta_joao, contrato_imagem_002)"],
        )

        self._add_predicate(
            "Prazo",
            3,
            "Contrato c tem vigência de d1 a d2",
            ["Contrato", "Data", "Data"],
            ["contrato", "data_inicio", "data_fim"],
            ["Prazo(contrato_001, 2024-01-01, 2024-12-31)"],
        )

        # Predicados Condicionais
        self._add_predicate(
            "Condicao",
            2,
            "Condição p implica consequência q",
            ["Acao", "Acao"],
            ["condicao", "consequencia"],
            [
                "Condicao(Inadimplencia(pagamento), Rescisao(contrato))",
                "Condicao(VitoriaOlimpica, Bonus(valor))",
            ],
        )

        self._add_predicate(
            "CondicaoSuspensiva",
            2,
            "Obrigação p só se inicia após condição q",
            ["Acao", "Acao"],
            ["obrigacao", "condicao"],
            ["CondicaoSuspensiva(Pagamento(patrocinio), Assinatura(contrato))"],
        )

        self._add_predicate(
            "CondicaoResolutiva",
            2,
            "Obrigação p se encerra com condição q",
            ["Acao", "Acao"],
            ["obrigacao", "condicao"],
            ["CondicaoResolutiva(Exclusividade, FimContrato)"],
        )

        # Predicados de Valor
        self._add_predicate(
            "Valor",
            3,
            "Ação p tem valor v associado ao contrato c",
            ["Acao", "Real", "Contrato"],
            ["acao", "valor", "contrato"],
            ["Valor(Pagamento(mensal), 50000.00, contrato_001)"],
        )

        # Predicados de Ação
        self._add_predicate(
            "Pagamento",
            1,
            "Representa uma ação de pagamento",
            ["String"],
            ["descricao"],
            ["Pagamento(parcela_mensal)", "Pagamento(bonus)"],
        )

        self._add_predicate(
            "UsoMarca",
            1,
            "Representa uso de marca",
            ["String"],
            ["modalidade"],
            ["UsoMarca(materiais_promocionais)", "UsoMarca(redes_sociais)"],
        )

        self._add_predicate(
            "UsoImagem",
            1,
            "Representa uso de imagem",
            ["String"],
            ["finalidade"],
            ["UsoImagem(publicidade)", "UsoImagem(documentario)"],
        )

        self._add_predicate(
            "Entrega",
            1,
            "Representa entrega de algo",
            ["String"],
            ["objeto"],
            ["Entrega(relatorio)", "Entrega(produto)"],
        )

        self._add_predicate(
            "Exclusividade",
            2,
            "Agente tem exclusividade sobre recurso",
            ["Agente", "Resource"],
            ["agente", "recurso"],
            ["Exclusividade(patrocinador, categoria_bebidas)"],
        )

        # Predicados Temporais
        self._add_predicate(
            "Antes",
            2,
            "Tempo t1 é anterior a tempo t2",
            ["Tempo", "Tempo"],
            ["t1", "t2"],
            ["Antes(data_assinatura, data_inicio)"],
        )

        self._add_predicate(
            "Durante",
            3,
            "Tempo t está entre t1 e t2",
            ["Tempo", "Tempo", "Tempo"],
            ["t", "t1", "t2"],
            ["Durante(data_evento, data_inicio, data_fim)"],
        )

        self._add_predicate(
            "AposEvento",
            2,
            "Tempo t é após evento e",
            ["Tempo", "Acao"],
            ["tempo", "evento"],
            ["AposEvento(prazo_pagamento, Entrega(produto))"],
        )

        # Predicados para Detecção de Cláusulas Abusivas
        self._add_predicate(
            "Rescisao",
            2,
            "Agente a rescinde contrato c",
            ["Agente", "Contrato"],
            ["agente", "contrato"],
            ["Rescisao(contratante, contrato_001)"],
        )

        self._add_predicate(
            "Multa",
            2,
            "Multa/penalidade imposta ao agente com valor percentual",
            ["Agente", "Real"],
            ["agente", "valor_percentual"],
            ["Multa(contratado, 10.0)"],
        )

        self._add_predicate(
            "RenunciaDir",
            2,
            "Agente a renuncia ao direito d",
            ["Agente", "Acao"],
            ["agente", "direito"],
            ["RenunciaDir(contratado, direito_reclamacao)"],
        )

        self._add_predicate(
            "ModificacaoUnilateral",
            2,
            "Agente a modifica unilateralmente objeto o",
            ["Agente", "Acao"],
            ["agente", "objeto"],
            ["ModificacaoUnilateral(contratante, condicoes_contrato)"],
        )

        self._add_predicate(
            "ExclusaoResp",
            2,
            "Exclusão de responsabilidade do agente a no contrato c",
            ["Agente", "Contrato"],
            ["agente", "contrato"],
            ["ExclusaoResp(contratante, contrato_001)"],
        )

        self._add_predicate(
            "ContratoAdesao",
            1,
            "Contrato c é um contrato de adesão",
            ["Contrato"],
            ["contrato"],
            ["ContratoAdesao(contrato_001)"],
        )

    def _add_predicate(
        self,
        name: str,
        arity: int,
        description: str,
        argument_types: list[str],
        argument_names: list[str],
        examples: list[str] | None = None,
    ):
        """Adiciona um predicado à ontologia."""
        self.predicates[name] = Predicate(
            name=name,
            arity=arity,
            description=description,
            argument_types=argument_types,
            argument_names=argument_names,
            examples=examples or [],
        )

    def _define_axioms(self):
        """
        Define os axiomas de consistência da ontologia.

        Estes axiomas são utilizados pelo solver Z3 para detectar conflitos.
        """

        # Axioma 1: Obrigação e Proibição são mutuamente exclusivas
        # ∀a,p: Obrigacao(a,p,_) → ¬Proibicao(a,p)
        self.axioms.append(
            "(assert (forall ((a Agent) (p Action) (t Time)) "
            "(=> (Obrigacao a p t) (not (Proibicao a p)))))"
        )

        # Axioma 2: Proibição implica não-permissão
        # ∀a,p: Proibicao(a,p) → ¬Permissao(a,p)
        self.axioms.append(
            "(assert (forall ((a Agent) (p Action)) "
            "(=> (Proibicao a p) (not (Permissao a p)))))"
        )

        # Axioma 3: Obrigação implica Permissão
        # ∀a,p,t: Obrigacao(a,p,t) → Permissao(a,p)
        self.axioms.append(
            "(assert (forall ((a Agent) (p Action) (t Time)) "
            "(=> (Obrigacao a p t) (Permissao a p))))"
        )

        # Axioma 4: Exclusividade é transitiva sobre agentes
        # Se a tem exclusividade sobre r, então ¬Permissao(b, uso(r)) para b ≠ a
        self.axioms.append(
            "(assert (forall ((a Agent) (b Agent) (r Resource)) "
            "(=> (and (Exclusividade a r) (not (= a b))) "
            "(not (Permissao b (UsoRecurso r))))))"
        )

        # Axioma 5: Prazos devem ser consistentes
        # ∀c,d1,d2: Prazo(c,d1,d2) → Antes(d1,d2)
        self.axioms.append(
            "(assert (forall ((c Contract) (d1 Date) (d2 Date)) "
            "(=> (Prazo c d1 d2) (Antes d1 d2))))"
        )

        # --- Axiomas para Detecção de Cláusulas Abusivas ---

        # Axioma 6: Simetria de rescisão (CC Art. 473)
        # ∀a,b,c: Permissao(a, Rescisao(c)) ∧ Parte(b,c) ∧ ¬(a=b)
        #          → Permissao(b, Rescisao(c))
        self.axioms.append(
            "(assert (forall ((a Agent) (b Agent) (c Contract)) "
            "(=> (and (Permissao a (Rescisao a c)) (Parte b c) (not (= a b))) "
            "(Permissao b (Rescisao b c)))))"
        )

        # Axioma 7: Exclusão de responsabilidade em contrato de adesão é nula
        # (CC Art. 424)
        # ∀a,c: ExclusaoResp(a,c) ∧ ContratoAdesao(c) → ⊥ (insatisfatível)
        self.axioms.append(
            "(assert (forall ((a Agent) (c Contract)) "
            "(not (and (ExclusaoResp a c) (ContratoAdesao c)))))"
        )

        # Axioma 8: Modificação unilateral viola boa-fé (CC Art. 422)
        # ∀a,o: ModificacaoUnilateral(a,o) → ¬Permissao(a, o)
        self.axioms.append(
            "(assert (forall ((a Agent) (o Action)) "
            "(=> (ModificacaoUnilateral a o) (not (Permissao a o)))))"
        )

    def get_predicate(self, name: str) -> Predicate | None:
        """Retorna um predicado pelo nome."""
        return self.predicates.get(name)

    def list_predicates(self) -> list[str]:
        """Lista todos os predicados disponíveis."""
        return list(self.predicates.keys())

    def get_predicate_signatures(self) -> list[str]:
        """Retorna as assinaturas de todos os predicados."""
        return [p.signature() for p in self.predicates.values()]

    def get_z3_preamble(self) -> str:
        """
        Gera o preâmbulo SMT-LIB com declarações de tipos e predicados.

        Este preâmbulo é usado para inicializar o solver Z3.
        """
        lines = [
            "; ContractFOL Ontology - SMT-LIB2 Preamble",
            "; Generated automatically",
            "",
            "; Sort declarations",
        ]

        # Declarar sorts
        for sort_name, description in self.sorts.items():
            lines.append(f"(declare-sort {sort_name} 0)  ; {description}")

        lines.append("")
        lines.append("; Predicate declarations")

        # Declarar predicados
        for pred in self.predicates.values():
            lines.append(pred.to_z3_declaration())

        lines.append("")
        lines.append("; Axioms")

        # Adicionar axiomas
        for axiom in self.axioms:
            lines.append(axiom)

        return "\n".join(lines)

    def get_ontology_description(self) -> str:
        """
        Retorna descrição textual da ontologia para uso em prompts.
        """
        lines = [
            "# Ontologia ContractFOL",
            "",
            "## Predicados Disponíveis:",
            "",
        ]

        for pred in self.predicates.values():
            lines.append(f"### {pred.signature()}")
            lines.append(f"**Descrição:** {pred.description}")
            lines.append(f"**Argumentos:**")
            for name, typ in zip(pred.argument_names, pred.argument_types):
                lines.append(f"  - `{name}`: {typ}")
            if pred.examples:
                lines.append(f"**Exemplos:**")
                for ex in pred.examples:
                    lines.append(f"  - `{ex}`")
            lines.append("")

        return "\n".join(lines)

    def validate_formula_predicates(self, formula: str) -> tuple[bool, list[str]]:
        """
        Verifica se todos os predicados usados na fórmula são válidos.

        Returns:
            Tuple (is_valid, list of unknown predicates)
        """
        import re

        # Extrair nomes de predicados da fórmula
        # Pattern: nome seguido de parêntese
        pattern = r"\b([A-Z][a-zA-Z]*)\s*\("
        used_predicates = set(re.findall(pattern, formula))

        # Predicados especiais que não precisam estar na ontologia
        special_predicates = {"Forall", "Exists", "And", "Or", "Not", "Implies", "Iff"}

        unknown = []
        for pred in used_predicates:
            if pred not in self.predicates and pred not in special_predicates:
                unknown.append(pred)

        return len(unknown) == 0, unknown


# Instância global da ontologia
DEFAULT_ONTOLOGY = ContractOntology()


def get_ontology() -> ContractOntology:
    """Retorna a ontologia padrão."""
    return DEFAULT_ONTOLOGY
