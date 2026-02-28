"""
Base de Regras Legais para Detecção de Cláusulas Abusivas.

Codifica regras do Código Civil brasileiro e CDC (por analogia) para
identificação de cláusulas potencialmente abusivas em contratos B2B
inter-institucionais.

Referências:
- Código Civil Brasileiro (Lei 10.406/2002)
- Código de Defesa do Consumidor (Lei 8.078/1990) - por analogia
"""

import re
from dataclasses import dataclass, field

from contractfol.models import AbusiveClauseType


@dataclass
class LegalRule:
    """Representa uma regra legal para detecção de abusividade."""

    id: str
    name: str
    legal_basis: str
    description: str
    heuristic_patterns: list[str]  # Regex patterns para Camada 1
    fol_template: str | None  # Template FOL para Camada 2
    llm_prompt_hint: str  # Hint para Camada 3
    severity: str  # HIGH, MEDIUM, LOW
    violation_type: AbusiveClauseType

    _compiled_patterns: list[re.Pattern] = field(
        default_factory=list, repr=False, compare=False
    )

    def get_compiled_patterns(self) -> list[re.Pattern]:
        """Retorna os padrões regex compilados (com cache)."""
        if not self._compiled_patterns:
            self._compiled_patterns = [
                re.compile(p, re.IGNORECASE) for p in self.heuristic_patterns
            ]
        return self._compiled_patterns

    def matches_heuristic(self, text: str) -> tuple[bool, float]:
        """
        Verifica se o texto casa com os padrões heurísticos desta regra.

        Returns:
            Tupla (matched, confidence)
        """
        patterns = self.get_compiled_patterns()
        match_count = sum(1 for p in patterns if p.search(text))

        if match_count == 0:
            return False, 0.0

        # Confiança baseada na proporção de padrões que casaram
        confidence = min(0.5 + (match_count / len(patterns)) * 0.4, 0.9)
        return True, confidence


# ============================================================================
# REGRAS DO CÓDIGO CIVIL BRASILEIRO
# ============================================================================

LEGAL_RULES: list[LegalRule] = [
    # ---- CC Art. 424 / 393: Exclusão de Responsabilidade ----
    LegalRule(
        id="CC_424_EXCLUSAO_RESP",
        name="Exclusão de Responsabilidade",
        legal_basis="CC, Art. 424 c/c Art. 393",
        description=(
            "Nos contratos de adesão, são nulas as cláusulas que estipulem a "
            "renúncia antecipada do aderente a direito resultante da natureza "
            "do negócio. A exclusão total de responsabilidade por danos pode "
            "configurar abusividade, especialmente em contratos de adesão (CC Art. 424)."
        ),
        heuristic_patterns=[
            r"(?:isent[ao]|exonera[r]?|exclui[r]?|exime[r]?)\s+(?:de\s+)?(?:toda|qualquer|"
            r"inteira)\s+responsabilidade",
            r"(?:não|nao)\s+(?:será|sera|serão|serao)\s+responsabilizad[ao]",
            r"(?:sem|isent[ao]\s+de)\s+(?:qualquer|nenhuma)\s+responsabilidade",
            r"exonera(?:r|ção|cao)\s+(?:total|completa)\s+de\s+responsabilidade",
            r"renuncia(?:r|ndo)?\s+(?:a|ao)\s+direito\s+de\s+(?:indenização|reparação|ressarcimento)",
        ],
        fol_template="ExclusaoResp({agente}, {contrato})",
        llm_prompt_hint=(
            "Verifique se a cláusula exclui ou limita totalmente a responsabilidade "
            "de uma das partes por danos, vícios ou inadimplemento. Conforme CC Art. 424, "
            "em contratos de adesão é nula a renúncia antecipada de direito."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.EXCLUSAO_RESPONSABILIDADE,
    ),
    # ---- CC Art. 473: Rescisão Unilateral ----
    LegalRule(
        id="CC_473_RESCISAO_UNILATERAL",
        name="Rescisão Unilateral sem Reciprocidade",
        legal_basis="CC, Art. 473",
        description=(
            "A resilição unilateral nos contratos de execução continuada ou diferida "
            "exige aviso prévio compatível com a natureza e vulto dos investimentos. "
            "Cláusula que permita rescisão unilateral sem aviso prévio ou sem "
            "reciprocidade é potencialmente abusiva."
        ),
        heuristic_patterns=[
            r"(?:rescind|resolv|resilir|denunci)(?:ir|er|ar)\s+(?:o\s+)?(?:presente\s+)?"
            r"(?:contrato|instrumento|termo)\s+(?:a\s+)?(?:qualquer|seu)\s+"
            r"(?:tempo|momento|critério)",
            r"rescis(?:ão|ao)\s+(?:unilateral|imotivada)\s+(?:sem|independente)",
            r"(?:poderá|podera|pode)\s+(?:ser\s+)?rescind(?:ir|ido)\s+"
            r"(?:unilateralmente|a\s+qualquer\s+(?:tempo|momento))",
            r"(?:denúncia|denuncia)\s+(?:imotivada|unilateral)\s+(?:sem|independente\s+de)\s+"
            r"(?:aviso|notificação|prazo)",
        ],
        fol_template="Permissao({agente}, Rescisao({contrato}))",
        llm_prompt_hint=(
            "Verifique se a cláusula permite que apenas uma das partes rescinda "
            "unilateralmente o contrato, especialmente sem aviso prévio ou sem "
            "garantir o mesmo direito à outra parte. Conforme CC Art. 473, a "
            "resilição requer aviso prévio compatível com investimentos realizados."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.RESCISAO_UNILATERAL,
    ),
    # ---- CC Art. 421/422: Modificação Unilateral ----
    LegalRule(
        id="CC_421_MODIF_UNILATERAL",
        name="Modificação Unilateral do Contrato",
        legal_basis="CC, Art. 421 c/c Art. 422",
        description=(
            "A liberdade contratual será exercida nos limites da função social "
            "do contrato (Art. 421). Os contratantes são obrigados a guardar "
            "os princípios de probidade e boa-fé (Art. 422). Modificação "
            "unilateral viola esses princípios."
        ),
        heuristic_patterns=[
            r"(?:reserva|direito)\s+(?:de\s+)?(?:alterar|modificar|mudar)\s+unilateralmente",
            r"(?:poderá|podera|pode)\s+(?:alterar|modificar|mudar)\s+(?:as\s+)?"
            r"(?:condições|condicoes|termos|cláusulas|clausulas)\s+(?:deste|do|desse)",
            r"(?:modificação|modificacao|alteração|alteracao)\s+(?:unilateral|a\s+seu\s+critério)",
            r"(?:alterar|modificar)\s+(?:livremente|a\s+qualquer\s+(?:tempo|momento))\s+"
            r"(?:as\s+)?(?:condições|termos)",
        ],
        fol_template="ModificacaoUnilateral({agente}, {objeto})",
        llm_prompt_hint=(
            "Verifique se a cláusula permite que uma das partes modifique "
            "unilateralmente as condições do contrato sem consentimento da "
            "outra parte. Isso viola o princípio da boa-fé objetiva (CC Art. 422) "
            "e a função social do contrato (CC Art. 421)."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.MODIFICACAO_UNILATERAL,
    ),
    # ---- CC Art. 412/413: Multa Excessiva ----
    LegalRule(
        id="CC_413_MULTA_EXCESSIVA",
        name="Cláusula Penal Excessiva",
        legal_basis="CC, Art. 412 c/c Art. 413",
        description=(
            "O valor da cominação imposta na cláusula penal não pode exceder "
            "o da obrigação principal (Art. 412). A penalidade deve ser reduzida "
            "equitativamente se manifestamente excessiva (Art. 413)."
        ),
        heuristic_patterns=[
            r"multa\s+(?:de\s+)?(\d+)\s*%",
            r"(?:penalidade|pena)\s+(?:de\s+)?(\d+)\s*%",
            r"multa\s+(?:equivalente|correspondente|no\s+valor)\s+(?:a\s+)?(\d+)\s*%",
            r"(?:cláusula|clausula)\s+penal\s+(?:de|no\s+valor\s+de)\s+(\d+)\s*%",
        ],
        fol_template="Multa({agente}, {valor_percentual})",
        llm_prompt_hint=(
            "Verifique se a cláusula penal/multa é excessiva ou desproporcional. "
            "Conforme CC Art. 412, não pode exceder o valor da obrigação principal. "
            "Art. 413 determina redução equitativa se manifestamente excessiva. "
            "Multas acima de 10% do valor do contrato são tipicamente consideradas excessivas."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.MULTA_EXCESSIVA,
    ),
    # ---- CC Art. 424: Renúncia de Direito ----
    LegalRule(
        id="CC_424_RENUNCIA",
        name="Renúncia Antecipada de Direito",
        legal_basis="CC, Art. 424",
        description=(
            "Nos contratos de adesão, são nulas as cláusulas que estipulem "
            "a renúncia antecipada do aderente a direito resultante da "
            "natureza do negócio."
        ),
        heuristic_patterns=[
            r"renuncia(?:r|ndo)?\s+(?:irrevogavelmente|expressamente|antecipadamente)",
            r"renuncia(?:r|ndo)?\s+(?:a\s+)?(?:todo|qualquer|quaisquer)\s+"
            r"(?:direito|pretensão|reclamação)",
            r"(?:abre|abrir)\s+mão\s+(?:de\s+)?(?:todo|qualquer|quaisquer)\s+direito",
            r"(?:desistir|desiste)\s+(?:de\s+)?(?:todo|qualquer)\s+"
            r"(?:direito|ação|pretensão)",
        ],
        fol_template="RenunciaDir({agente}, {direito})",
        llm_prompt_hint=(
            "Verifique se a cláusula impõe renúncia antecipada e irrevogável "
            "a direitos fundamentais do contratante. Conforme CC Art. 424, "
            "em contratos de adesão é nula a renúncia antecipada a direito "
            "resultante da natureza do negócio."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.RENUNCIA_DIREITO,
    ),
    # ---- CC Art. 157: Lesão / Desvantagem Exagerada ----
    LegalRule(
        id="CC_157_DESVANTAGEM",
        name="Lesão - Desvantagem Exagerada",
        legal_basis="CC, Art. 157",
        description=(
            "Ocorre lesão quando uma pessoa, sob premente necessidade ou por "
            "inexperiência, se obriga a prestação manifestamente desproporcional "
            "ao valor da prestação oposta."
        ),
        heuristic_patterns=[
            r"(?:todos?\s+)?(?:os\s+)?(?:benefícios|beneficios|lucros|ganhos)\s+"
            r"(?:decorrentes|oriundos|resultantes|advindos)?\s*(?:da|do|de)?\s*"
            r"(?:parceria|contrato|negócio|acordo)?\s*(?:serão|serao|são|sao|ficam)\s+"
            r"(?:de\s+)?(?:propriedade|titularidade)\s+(?:exclusiv[ao]|integral)",
            r"(?:benefício|beneficio|benefícios|beneficios)\s+(?:serão|serao)?\s*(?:de\s+)?"
            r"(?:propriedade\s+)?exclusiv[ao]s?\s+(?:de|da|do)",
            r"(?:todo|qualquer)\s+(?:resultado|fruto|rendimento)\s+(?:pertencerá|pertencera)\s+"
            r"(?:exclusivamente|somente)\s+(?:à|a|ao)",
            r"(?:sem|nenhum|nenhuma)\s+(?:direito\s+a\s+)?(?:contrapartida|compensação|"
            r"remuneração|retribuição)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula cria uma desproporção manifesta entre as "
            "obrigações/benefícios das partes, configurando lesão (CC Art. 157). "
            "Analise se todos os benefícios são direcionados a apenas uma das "
            "partes sem contrapartida adequada."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.DESVANTAGEM_EXAGERADA,
    ),
    # ---- CC Art. 478-480: Onerosidade Excessiva ----
    LegalRule(
        id="CC_478_ONEROSIDADE",
        name="Onerosidade Excessiva",
        legal_basis="CC, Art. 478 a 480",
        description=(
            "Nos contratos de execução continuada, se a prestação tornar-se "
            "excessivamente onerosa por acontecimentos extraordinários e "
            "imprevisíveis, o devedor poderá pedir resolução do contrato."
        ),
        heuristic_patterns=[
            r"(?:independentemente|mesmo\s+em\s+caso)\s+(?:de\s+)?"
            r"(?:caso\s+fortuito|força\s+maior|evento\s+extraordinário)",
            r"(?:ainda\s+que|mesmo\s+que)\s+(?:haja|ocorra)\s+"
            r"(?:alteração|mudança)\s+(?:nas\s+)?(?:circunstâncias|condições)",
            r"(?:não|nao)\s+(?:poderá|podera)\s+(?:alegar|invocar)\s+"
            r"(?:onerosidade|desequilíbrio|desequilibrio|caso\s+fortuito|força\s+maior)",
            r"(?:assume|assumir)\s+(?:todos?\s+)?(?:os\s+)?riscos?\s+"
            r"(?:do\s+negócio|contratua(?:is|l))",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula impede que a parte invoque onerosidade "
            "excessiva, caso fortuito ou força maior para revisão ou "
            "resolução do contrato. Conforme CC Art. 478, a onerosidade "
            "excessiva por fatos extraordinários autoriza a resolução contratual."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.ONEROSIDADE_EXCESSIVA,
    ),
    # ---- CC Art. 113/422: Violação da Boa-Fé ----
    LegalRule(
        id="CC_422_BOA_FE",
        name="Violação do Princípio da Boa-Fé Objetiva",
        legal_basis="CC, Art. 113 c/c Art. 422",
        description=(
            "Os negócios jurídicos devem ser interpretados conforme a boa-fé "
            "e os usos do lugar (Art. 113). Os contratantes são obrigados a "
            "guardar os princípios de probidade e boa-fé (Art. 422)."
        ),
        heuristic_patterns=[
            r"(?:sem\s+necessidade\s+de)\s+(?:justificativa|motivação|fundamentação)",
            r"a\s+(?:seu|sua)\s+(?:exclusivo|livre|único)\s+(?:critério|arbítrio|juízo)",
            r"(?:discricionari|arbitrári)(?:amente|a|o)",
            r"(?:sem\s+(?:direito\s+a?\s*)?(?:qualquer|nenhum[a]?)\s+"
            r"(?:explicação|justificativa|questionamento|recurso))",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula confere poder discricionário excessivo "
            "a uma das partes, sem controle ou justificativa, violando o "
            "princípio da boa-fé objetiva (CC Art. 422) e o dever de "
            "transparência e lealdade contratual."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.BOA_FE_VIOLACAO,
    ),
    # ---- CC Art. 1.008: Cláusula Leonina ----
    LegalRule(
        id="CC_1008_LEONINA",
        name="Cláusula Leonina",
        legal_basis="CC, Art. 1.008",
        description=(
            "É nula a estipulação contratual que exclua qualquer sócio de "
            "participar dos lucros e das perdas. Por analogia, aplica-se "
            "a contratos de parceria/cooperação onde uma parte é excluída "
            "dos benefícios ou assume todas as perdas."
        ),
        heuristic_patterns=[
            r"(?:exclusão|exclusao|excluí[dr]|exclui[dr])\s+(?:de\s+)?(?:participação|participacao)\s+"
            r"(?:nos?\s+)?(?:lucros|resultados|benefícios|beneficios)",
            r"(?:todas?\s+)?(?:as\s+)?(?:perdas|prejuízos|prejuizos)\s+"
            r"(?:serão|serao|são|ficam)\s+(?:por\s+conta|de\s+responsabilidade)\s+"
            r"(?:exclusiv[ao]|somente|apenas)\s+(?:d[aeo])",
            r"(?:não|nao)\s+(?:terá|tera|fará|fara)\s+(?:jus|direito)\s+(?:a\s+)?"
            r"(?:qualquer|nenhum[a]?)\s+(?:participação|lucro|benefício|beneficio)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula exclui uma das partes da participação nos "
            "lucros/benefícios ou imputa todas as perdas a apenas uma das partes, "
            "configurando cláusula leonina (CC Art. 1.008 por analogia)."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.CLAUSULA_LEONINA,
    ),
    # ---- CC Art. 413: Perda Total de Prestações ----
    LegalRule(
        id="CC_413_PERDA_PRESTACOES",
        name="Perda Total de Prestações Pagas",
        legal_basis="CC, Art. 413",
        description=(
            "A cláusula que determina perda total dos valores já pagos em caso "
            "de rescisão pode ser considerada abusiva, pois configura cláusula "
            "penal desproporcional (Art. 413 determina redução equitativa)."
        ),
        heuristic_patterns=[
            r"(?:perda|perderá|perdera)\s+(?:a\s+)?(?:total(?:idade)?|integral|completa)\s+"
            r"(?:d[aeo]s?\s+)?(?:valores|prestações|pagamentos|parcelas)",
            r"(?:sem|nenhum)\s+(?:direito\s+(?:a|à|ao)\s+)?"
            r"(?:devolução|devoluçao|restituição|restituicao|reembolso)",
            r"(?:valores|quantias|importâncias)\s+(?:já|ja)\s+(?:pagos?|pagas?)\s+"
            r"(?:não|nao)\s+(?:serão|serao)\s+(?:devolvid|restituíd|reembolsad)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula determina perda total dos valores já "
            "pagos em caso de rescisão, sem qualquer devolução proporcional. "
            "Conforme CC Art. 413, a penalidade deve ser reduzida equitativamente."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.PERDA_PRESTACOES,
    ),
    # ---- CC Art. 424: Transferência de Responsabilidade ----
    LegalRule(
        id="CC_424_TRANSFERENCIA",
        name="Transferência Indevida de Responsabilidade",
        legal_basis="CC, Art. 424",
        description=(
            "A transferência de responsabilidade a terceiros ou à parte "
            "mais fraca do contrato sem justificativa pode configurar abusividade."
        ),
        heuristic_patterns=[
            r"(?:transferir|transfere|transferência)\s+(?:a\s+)?(?:responsabilidade|obrigação)\s+"
            r"(?:a\s+)?(?:terceiros|outra\s+parte)",
            r"(?:responsabilidade|ônus|onus)\s+(?:será|sera|fica)\s+"
            r"(?:exclusivamente|integralmente|totalmente)\s+(?:d[aeo]|por\s+conta)",
            r"(?:responderá|respondera)\s+(?:exclusivamente|sozinho|isoladamente)\s+"
            r"(?:por\s+)?(?:todos?\s+)?(?:os?\s+)?(?:danos?|prejuízos?|custos?)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula transfere toda a responsabilidade para "
            "apenas uma das partes ou para terceiros de forma injustificada. "
            "Analise se há equilíbrio na distribuição de riscos e responsabilidades."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.TRANSFERENCIA_RESPONSABILIDADE,
    ),
    # ---- CC Art. 944: Indenização Desproporcional ----
    LegalRule(
        id="CC_944_INDENIZACAO",
        name="Indenização Desproporcional",
        legal_basis="CC, Art. 944",
        description=(
            "A indenização mede-se pela extensão do dano (Art. 944). "
            "Cláusulas que fixam indenizações predeterminadas exorbitantes "
            "ou desvinculadas do dano real podem ser abusivas."
        ),
        heuristic_patterns=[
            r"(?:indenização|indenizacao)\s+(?:pré-fixada|prefixada|predeterminada)\s+"
            r"(?:de|no\s+valor\s+de)\s+(?:R\$\s*)?[\d.,]+",
            r"(?:indenizar|indenização|indenizacao)\s+(?:em|no)\s+(?:valor\s+)?"
            r"(?:equivalente|igual)\s+(?:a|ao)\s+(?:total|valor\s+(?:total|integral))",
            r"(?:lucros?\s+cessantes?\s+(?:presumid|estimad|arbitrad))",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula fixa indenizações predeterminadas "
            "desproporcionais ao dano potencial. Conforme CC Art. 944, a "
            "indenização deve ser proporcional à extensão do dano."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.INDENIZACAO_DESPROPORCIONAL,
    ),
    # ---- CDC Art. 51 VII (analogia): Arbitragem Compulsória ----
    LegalRule(
        id="CDC_51_VII_ARBITRAGEM",
        name="Arbitragem Compulsória",
        legal_basis="CDC, Art. 51, VII (por analogia)",
        description=(
            "A imposição compulsória de arbitragem em contratos de adesão "
            "pode ser considerada abusiva, especialmente quando não há "
            "negociação paritária entre as partes."
        ),
        heuristic_patterns=[
            r"(?:obrigatoriamente|compulsoriamente|exclusivamente)\s+"
            r"(?:submetid[ao]s?\s+)?(?:à|a)\s+(?:arbitragem|tribunal\s+arbitral)",
            r"(?:arbitragem|tribunal\s+arbitral)\s+(?:obrigatóri[ao]|compulsóri[ao])",
            r"(?:renunci[ao]|abre[m]?\s+mão)\s+(?:d[ao]\s+)?(?:direito\s+de\s+)?"
            r"(?:acess[ao]|recorrer)\s+(?:à|ao?)\s+(?:justiça|judiciário|poder\s+judiciário)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula impõe arbitragem compulsória sem "
            "possibilidade de acesso ao Poder Judiciário, especialmente em "
            "contratos de adesão. Por analogia ao CDC Art. 51, VII, a "
            "imposição de arbitragem compulsória pode ser abusiva."
        ),
        severity="MEDIUM",
        violation_type=AbusiveClauseType.ARBITRAGEM_COMPULSORIA,
    ),
    # ---- CDC Art. 51 X (analogia): Alteração de Preço Unilateral ----
    LegalRule(
        id="CDC_51_X_PRECO",
        name="Alteração Unilateral de Preço",
        legal_basis="CDC, Art. 51, X (por analogia)",
        description=(
            "A alteração unilateral de preço ou de valores contratuais sem "
            "critério objetivo previamente definido pode ser abusiva."
        ),
        heuristic_patterns=[
            r"(?:reajust|alter|modific)(?:ar|e)\s+(?:o\s+)?(?:preço|valor|"
            r"remuneração|honorário)\s+(?:unilateralmente|a\s+seu\s+critério)",
            r"(?:preço|valor|remuneração)\s+(?:poderá|podera|será|sera)\s+"
            r"(?:reajustad|alterad|modificad)[ao]\s+(?:unilateralmente|"
            r"a\s+critério\s+exclusiv[ao])",
            r"(?:reserva|direito\s+de)\s+(?:reajustar|alterar)\s+"
            r"(?:os?\s+)?(?:preços?|valores?)\s+(?:sem\s+)?(?:aviso|anuência|concordância)",
        ],
        fol_template=None,
        llm_prompt_hint=(
            "Verifique se a cláusula permite alteração unilateral de preços "
            "ou valores sem critério objetivo ou sem concordância da outra parte."
        ),
        severity="HIGH",
        violation_type=AbusiveClauseType.ALTERACAO_PRECO_UNILATERAL,
    ),
]


def get_legal_rules() -> list[LegalRule]:
    """Retorna todas as regras legais codificadas."""
    return LEGAL_RULES


def get_rules_by_type(violation_type: AbusiveClauseType) -> list[LegalRule]:
    """Retorna regras filtradas por tipo de violação."""
    return [r for r in LEGAL_RULES if r.violation_type == violation_type]


def get_rule_by_id(rule_id: str) -> LegalRule | None:
    """Retorna uma regra específica pelo ID."""
    for rule in LEGAL_RULES:
        if rule.id == rule_id:
            return rule
    return None
