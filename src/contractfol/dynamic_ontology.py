"""
Ontologia Dinâmica ContractFOL.

Extensão da ontologia base que permite adicionar predicados dinamicamente
a partir da análise do texto do contrato.

A ontologia dinâmica permite:
- Descoberta automática de novos predicados baseada no contexto
- Extensão incremental da base de conhecimento
- Persistência de predicados aprendidos
- Validação semântica de novos predicados

Predicados Base (sempre presentes):
- Obrigacao(a, p, t): Agente a é obrigado a realizar p até tempo t
- Permissao(a, p): Agente a tem permissão para p
- Proibicao(a, p): Agente a é proibido de realizar p
- Parte(x, c): Entidade x é parte do contrato c
- Prazo(c, d1, d2): Contrato c tem vigência de d1 a d2
- Condicao(p, q): Condição p implica consequência q
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from contractfol.ontology import ContractOntology, Predicate


@dataclass
class PredicateMetadata:
    """Metadados adicionais para predicados dinâmicos."""

    created_at: str = ""
    source_clause: str = ""
    confidence: float = 0.0
    usage_count: int = 0
    is_core: bool = False  # True para predicados da ontologia base
    domain: str = "geral"  # Domínio do predicado (contratos, temporal, etc.)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PredicateMetadata":
        return cls(**data)


@dataclass
class DynamicPredicate(Predicate):
    """Predicado com metadados de descoberta dinâmica."""

    metadata: PredicateMetadata = field(default_factory=PredicateMetadata)
    semantic_tags: list[str] = field(default_factory=list)
    related_predicates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arity": self.arity,
            "description": self.description,
            "argument_types": self.argument_types,
            "argument_names": self.argument_names,
            "examples": self.examples,
            "metadata": self.metadata.to_dict(),
            "semantic_tags": self.semantic_tags,
            "related_predicates": self.related_predicates,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DynamicPredicate":
        metadata = PredicateMetadata.from_dict(data.get("metadata", {}))
        return cls(
            name=data["name"],
            arity=data["arity"],
            description=data["description"],
            argument_types=data["argument_types"],
            argument_names=data["argument_names"],
            examples=data.get("examples", []),
            metadata=metadata,
            semantic_tags=data.get("semantic_tags", []),
            related_predicates=data.get("related_predicates", []),
        )

    @classmethod
    def from_predicate(cls, pred: Predicate, is_core: bool = False) -> "DynamicPredicate":
        """Converte um Predicate base para DynamicPredicate."""
        return cls(
            name=pred.name,
            arity=pred.arity,
            description=pred.description,
            argument_types=pred.argument_types,
            argument_names=pred.argument_names,
            examples=pred.examples,
            metadata=PredicateMetadata(
                created_at=datetime.now().isoformat(),
                is_core=is_core,
            ),
        )


class DynamicOntology(ContractOntology):
    """
    Ontologia extensível que permite adicionar predicados dinamicamente.

    Herda da ContractOntology base e adiciona:
    - Registro de predicados dinâmicos com metadados
    - Persistência em arquivo JSON
    - Categorização semântica
    - Validação de novos predicados
    """

    # Categorias semânticas para predicados
    SEMANTIC_CATEGORIES = {
        "deontico": "Predicados deônticos (obrigação, permissão, proibição)",
        "estrutural": "Predicados estruturais (partes, prazos, contratos)",
        "condicional": "Predicados condicionais (se-então, triggers)",
        "temporal": "Predicados temporais (antes, depois, durante)",
        "acao": "Predicados de ação (pagamento, entrega, uso)",
        "valor": "Predicados de valor (monetário, quantitativo)",
        "relacional": "Predicados relacionais (entre partes, objetos)",
        "qualificador": "Predicados qualificadores (exclusivo, parcial)",
    }

    def __init__(self, persistence_path: str | None = None):
        """
        Inicializa a ontologia dinâmica.

        Args:
            persistence_path: Caminho para arquivo de persistência JSON.
                            Se None, não persiste predicados.
        """
        super().__init__()

        self.dynamic_predicates: dict[str, DynamicPredicate] = {}
        self.persistence_path = persistence_path
        self._custom_axioms: list[str] = []

        # Converter predicados base para dinâmicos
        self._convert_core_predicates()

        # Carregar predicados persistidos
        if persistence_path:
            self._load_from_file()

    def _convert_core_predicates(self):
        """Converte predicados da ontologia base para dinâmicos."""
        for name, pred in self.predicates.items():
            self.dynamic_predicates[name] = DynamicPredicate.from_predicate(
                pred, is_core=True
            )
            self.dynamic_predicates[name].metadata.domain = self._infer_domain(name)

    def _infer_domain(self, predicate_name: str) -> str:
        """Infere o domínio semântico de um predicado."""
        deontic = {"Obrigacao", "Permissao", "Proibicao"}
        structural = {"Parte", "Prazo", "Contrato"}
        conditional = {"Condicao", "CondicaoSuspensiva", "CondicaoResolutiva"}
        temporal = {"Antes", "Durante", "AposEvento"}
        action = {"Pagamento", "UsoMarca", "UsoImagem", "Entrega"}
        value = {"Valor", "Exclusividade"}

        if predicate_name in deontic:
            return "deontico"
        elif predicate_name in structural:
            return "estrutural"
        elif predicate_name in conditional:
            return "condicional"
        elif predicate_name in temporal:
            return "temporal"
        elif predicate_name in action:
            return "acao"
        elif predicate_name in value:
            return "valor"
        return "geral"

    def add_predicate(
        self,
        name: str,
        arity: int,
        description: str,
        argument_types: list[str],
        argument_names: list[str],
        examples: list[str] | None = None,
        source_clause: str = "",
        confidence: float = 0.8,
        semantic_tags: list[str] | None = None,
        related_predicates: list[str] | None = None,
    ) -> DynamicPredicate:
        """
        Adiciona um novo predicado à ontologia.

        Args:
            name: Nome do predicado (PascalCase)
            arity: Número de argumentos
            description: Descrição em português
            argument_types: Tipos dos argumentos
            argument_names: Nomes dos argumentos
            examples: Exemplos de uso
            source_clause: Cláusula que originou o predicado
            confidence: Confiança na definição (0.0 a 1.0)
            semantic_tags: Tags semânticas para categorização
            related_predicates: Predicados relacionados

        Returns:
            O predicado criado

        Raises:
            ValueError: Se o predicado já existe ou é inválido
        """
        # Validar nome
        if not self._validate_predicate_name(name):
            raise ValueError(
                f"Nome de predicado inválido: {name}. "
                "Use PascalCase (ex: NomePredicado)"
            )

        # Verificar se já existe
        if name in self.dynamic_predicates and self.dynamic_predicates[name].metadata.is_core:
            raise ValueError(f"Não é possível sobrescrever predicado core: {name}")

        # Validar aridade e argumentos
        if len(argument_types) != arity or len(argument_names) != arity:
            raise ValueError(
                f"Aridade ({arity}) não corresponde ao número de argumentos"
            )

        # Criar predicado dinâmico
        pred = DynamicPredicate(
            name=name,
            arity=arity,
            description=description,
            argument_types=argument_types,
            argument_names=argument_names,
            examples=examples or [],
            metadata=PredicateMetadata(
                created_at=datetime.now().isoformat(),
                source_clause=source_clause,
                confidence=confidence,
                usage_count=0,
                is_core=False,
                domain=self._infer_domain_from_description(description),
            ),
            semantic_tags=semantic_tags or [],
            related_predicates=related_predicates or [],
        )

        # Adicionar às estruturas
        self.dynamic_predicates[name] = pred
        self.predicates[name] = pred  # Compatibilidade com ontologia base

        # Persistir
        if self.persistence_path:
            self._save_to_file()

        return pred

    def _validate_predicate_name(self, name: str) -> bool:
        """Valida se o nome segue PascalCase."""
        return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))

    def _infer_domain_from_description(self, description: str) -> str:
        """Infere domínio a partir da descrição."""
        desc_lower = description.lower()

        if any(w in desc_lower for w in ["obriga", "deve", "dever"]):
            return "deontico"
        elif any(w in desc_lower for w in ["permite", "pode", "autoriza"]):
            return "deontico"
        elif any(w in desc_lower for w in ["proib", "veda", "impede"]):
            return "deontico"
        elif any(w in desc_lower for w in ["prazo", "período", "vigência"]):
            return "temporal"
        elif any(w in desc_lower for w in ["valor", "preço", "custo", "quantia"]):
            return "valor"
        elif any(w in desc_lower for w in ["paga", "entrega", "fornece"]):
            return "acao"
        elif any(w in desc_lower for w in ["condição", "se ", "caso", "quando"]):
            return "condicional"
        elif any(w in desc_lower for w in ["parte", "contrat", "assin"]):
            return "estrutural"

        return "geral"

    def remove_predicate(self, name: str) -> bool:
        """
        Remove um predicado dinâmico (não-core).

        Returns:
            True se removido, False se não encontrado ou é core
        """
        if name not in self.dynamic_predicates:
            return False

        if self.dynamic_predicates[name].metadata.is_core:
            return False

        del self.dynamic_predicates[name]
        if name in self.predicates:
            del self.predicates[name]

        if self.persistence_path:
            self._save_to_file()

        return True

    def increment_usage(self, name: str):
        """Incrementa contador de uso de um predicado."""
        if name in self.dynamic_predicates:
            self.dynamic_predicates[name].metadata.usage_count += 1
            if self.persistence_path:
                self._save_to_file()

    def get_predicates_by_domain(self, domain: str) -> list[DynamicPredicate]:
        """Retorna predicados de um domínio específico."""
        return [
            p for p in self.dynamic_predicates.values()
            if p.metadata.domain == domain
        ]

    def get_dynamic_predicates(self) -> list[DynamicPredicate]:
        """Retorna apenas predicados não-core (descobertos)."""
        return [
            p for p in self.dynamic_predicates.values()
            if not p.metadata.is_core
        ]

    def get_core_predicates(self) -> list[DynamicPredicate]:
        """Retorna apenas predicados core (base)."""
        return [
            p for p in self.dynamic_predicates.values()
            if p.metadata.is_core
        ]

    def add_custom_axiom(self, axiom: str, description: str = ""):
        """
        Adiciona um axioma customizado.

        Args:
            axiom: Fórmula SMT-LIB do axioma
            description: Descrição do axioma
        """
        if description:
            self._custom_axioms.append(f"; {description}")
        self._custom_axioms.append(axiom)
        self.axioms.append(axiom)

    def get_extended_z3_preamble(self) -> str:
        """
        Gera preâmbulo Z3 estendido com predicados dinâmicos.
        """
        base_preamble = self.get_z3_preamble()

        # Adicionar declarações de predicados dinâmicos
        dynamic_declarations = []
        for pred in self.get_dynamic_predicates():
            dynamic_declarations.append(pred.to_z3_declaration())

        if dynamic_declarations:
            dynamic_section = "\n\n; Dynamic predicates\n" + "\n".join(dynamic_declarations)
            return base_preamble + dynamic_section

        return base_preamble

    def get_extended_ontology_description(self) -> str:
        """
        Gera descrição estendida incluindo predicados dinâmicos.
        """
        lines = [
            "# Ontologia ContractFOL Dinâmica",
            "",
            "## Predicados Base (Core):",
            "",
        ]

        # Predicados core agrupados por domínio
        for domain in ["deontico", "estrutural", "condicional", "temporal", "acao", "valor"]:
            domain_preds = [
                p for p in self.get_core_predicates()
                if p.metadata.domain == domain
            ]
            if domain_preds:
                lines.append(f"### {domain.title()}")
                for pred in domain_preds:
                    lines.append(f"- **{pred.signature()}**: {pred.description}")
                lines.append("")

        # Predicados dinâmicos
        dynamic = self.get_dynamic_predicates()
        if dynamic:
            lines.append("## Predicados Descobertos (Dinâmicos):")
            lines.append("")
            for pred in dynamic:
                lines.append(f"### {pred.signature()}")
                lines.append(f"**Descrição:** {pred.description}")
                lines.append(f"**Confiança:** {pred.metadata.confidence:.0%}")
                lines.append(f"**Usos:** {pred.metadata.usage_count}")
                if pred.examples:
                    lines.append("**Exemplos:**")
                    for ex in pred.examples:
                        lines.append(f"  - `{ex}`")
                lines.append("")

        return "\n".join(lines)

    def validate_formula_predicates(self, formula: str) -> tuple[bool, list[str]]:
        """
        Valida predicados na fórmula e incrementa uso.

        Override do método base para incluir predicados dinâmicos.
        """
        pattern = r"\b([A-Z][a-zA-Z]*)\s*\("
        used_predicates = set(re.findall(pattern, formula))

        special_predicates = {"Forall", "Exists", "And", "Or", "Not", "Implies", "Iff"}

        unknown = []
        for pred in used_predicates:
            if pred in self.dynamic_predicates:
                self.increment_usage(pred)
            elif pred not in special_predicates:
                unknown.append(pred)

        return len(unknown) == 0, unknown

    def suggest_predicates(self, text: str) -> list[DynamicPredicate]:
        """
        Sugere predicados relevantes baseado no texto.

        Args:
            text: Texto da cláusula

        Returns:
            Lista de predicados potencialmente relevantes
        """
        text_lower = text.lower()
        suggestions = []

        # Palavras-chave por domínio
        domain_keywords = {
            "deontico": ["obriga", "deve", "dever", "permite", "pode", "proíb", "veda"],
            "temporal": ["prazo", "até", "antes", "após", "durante", "período"],
            "valor": ["valor", "preço", "r$", "reais", "pagamento", "quantia"],
            "acao": ["pagar", "entregar", "fornecer", "realizar", "executar"],
            "condicional": ["se ", "caso", "quando", "desde que", "condição"],
        }

        # Encontrar domínios relevantes
        relevant_domains = set()
        for domain, keywords in domain_keywords.items():
            if any(kw in text_lower for kw in keywords):
                relevant_domains.add(domain)

        # Sugerir predicados dos domínios relevantes
        for pred in self.dynamic_predicates.values():
            if pred.metadata.domain in relevant_domains:
                suggestions.append(pred)

        # Ordenar por uso (mais usados primeiro)
        suggestions.sort(key=lambda p: p.metadata.usage_count, reverse=True)

        return suggestions[:10]  # Top 10

    def _save_to_file(self):
        """Salva predicados dinâmicos em arquivo JSON."""
        if not self.persistence_path:
            return

        path = Path(self.persistence_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "predicates": [
                pred.to_dict()
                for pred in self.dynamic_predicates.values()
                if not pred.metadata.is_core
            ],
            "custom_axioms": self._custom_axioms,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_file(self):
        """Carrega predicados dinâmicos de arquivo JSON."""
        if not self.persistence_path:
            return

        path = Path(self.persistence_path)
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for pred_data in data.get("predicates", []):
                pred = DynamicPredicate.from_dict(pred_data)
                self.dynamic_predicates[pred.name] = pred
                self.predicates[pred.name] = pred

            for axiom in data.get("custom_axioms", []):
                if not axiom.startswith(";"):
                    self.axioms.append(axiom)
                self._custom_axioms.append(axiom)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Aviso: Erro ao carregar ontologia dinâmica: {e}")

    def export_statistics(self) -> dict[str, Any]:
        """Exporta estatísticas da ontologia."""
        core = self.get_core_predicates()
        dynamic = self.get_dynamic_predicates()

        return {
            "total_predicates": len(self.dynamic_predicates),
            "core_predicates": len(core),
            "dynamic_predicates": len(dynamic),
            "domains": {
                domain: len(self.get_predicates_by_domain(domain))
                for domain in self.SEMANTIC_CATEGORIES
            },
            "total_usage": sum(p.metadata.usage_count for p in self.dynamic_predicates.values()),
            "avg_confidence": (
                sum(p.metadata.confidence for p in dynamic) / len(dynamic)
                if dynamic else 0.0
            ),
        }


# Instância global da ontologia dinâmica
_dynamic_ontology: DynamicOntology | None = None


def get_dynamic_ontology(persistence_path: str | None = None) -> DynamicOntology:
    """
    Retorna a instância global da ontologia dinâmica.

    Args:
        persistence_path: Caminho para persistência. Se fornecido na primeira
                        chamada, será usado. Chamadas subsequentes ignoram.
    """
    global _dynamic_ontology

    if _dynamic_ontology is None:
        _dynamic_ontology = DynamicOntology(persistence_path)

    return _dynamic_ontology


def reset_dynamic_ontology():
    """Reseta a instância global (útil para testes)."""
    global _dynamic_ontology
    _dynamic_ontology = None
