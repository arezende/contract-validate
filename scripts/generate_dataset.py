#!/usr/bin/env python3
"""
Gerador de Dataset Sintético para Avaliação do ContractFOL.

Gera contratos sintéticos com inconsistências injetadas artificialmente,
conforme o design experimental da Seção 6.1 da dissertação:

- N contratos com estrutura realista (partes, vigência, cláusulas)
- Fração configurable com inconsistências injetadas (padrão: 60%)
- Ground truth exportado em clausulas_anotadas.json
- Arquivos de texto exportados em data/contracts/

Uso:
    python scripts/generate_dataset.py
    python scripts/generate_dataset.py --num-contracts 50 --seed 42
    python scripts/generate_dataset.py --num-contracts 50 --inconsistency-rate 0.6 --output-dir data/contracts
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Templates de cláusulas por modalidade deôntica (domínio esportivo, pt-BR)
# ---------------------------------------------------------------------------

PARTIES = [
    ("PATROCINADOR", "patrocinador"),
    ("CONTRATADO", "contratado"),
    ("ATLETA", "atleta"),
    ("COB", "cob"),
    ("CONTRATANTE", "contratante"),
    ("CONTRATADA", "contratada"),
    ("FORNECEDOR", "fornecedor"),
    ("CBDA", "cbda"),
]

CONTRACT_TYPES = [
    "Contrato de Patrocínio Esportivo",
    "Contrato de Fornecimento de Serviços",
    "Contrato de Atleta Profissional",
    "Contrato de Licenciamento de Marca",
    "Contrato de Prestação de Serviços Técnicos",
]

# (texto_template, modalidade, agente_index, fol_gold_template)
CLAUSE_TEMPLATES = {
    "OBRIGACAO_ATIVA": [
        (
            "O {party} obriga-se a realizar o pagamento mensal até o {day}º dia útil de cada mês.",
            "Obrigacao({agent}, Pagamento(mensal), DiaDia{day}UtilMes)",
        ),
        (
            "O {party} deverá apresentar relatório trimestral de atividades ao {party2}.",
            "∀t.Trimestre(t) → Obrigacao({agent}, Entrega(relatorio, {agent2}), FimTrimestre(t))",
        ),
        (
            "O {party} obriga-se a exibir a marca do {party2} em todos os materiais promocionais.",
            "Obrigacao({agent}, UsoMarca({agent2}, materiais_promocionais), Sempre)",
        ),
        (
            "O {party} deverá participar de no mínimo {n} eventos institucionais por ano.",
            "∀a.Ano(a) → Obrigacao({agent}, Participacao(eventos, min={n}), a)",
        ),
        (
            "O {party} obriga-se a manter equipe técnica mínima de {n} profissionais durante a vigência.",
            "Obrigacao({agent}, ManterEquipe(min={n}), Vigencia)",
        ),
        (
            "O {party} deverá entregar o relatório final em até {days} dias após o encerramento.",
            "Obrigacao({agent}, Entrega(relatorio_final), Encerramento + {days}dias)",
        ),
        (
            "O {party} obriga-se a fornecer suporte técnico 24 horas por dia durante a vigência.",
            "Obrigacao({agent}, SuporteTecnico(24h), Vigencia)",
        ),
        (
            "O {party} deverá concluir a implantação dos sistemas em até {days} dias corridos.",
            "Obrigacao({agent}, ConclusaoImplantacao, DataInicio + {days}dias)",
        ),
    ],
    "PROIBICAO": [
        (
            "É vedado ao {party} o uso da marca do {party2} sem autorização prévia e por escrito.",
            "Proibicao({agent}, UsoMarca({agent2}, sem_autorizacao))",
        ),
        (
            "O {party} não poderá subcontratar terceiros sem aprovação expressa do {party2}.",
            "Proibicao({agent}, Subcontratacao(sem_aprovacao_{agent2}))",
        ),
        (
            "É proibido ao {party} patrocinar eventos concorrentes durante a vigência deste contrato.",
            "Proibicao({agent}, Patrocinio(eventos_concorrentes))",
        ),
        (
            "O {party} não poderá divulgar informações confidenciais a terceiros não autorizados.",
            "Proibicao({agent}, Divulgacao(informacoes_confidenciais, terceiros))",
        ),
        (
            "É vedado ao {party} realizar alterações unilaterais nas especificações técnicas acordadas.",
            "Proibicao({agent}, AlteracaoUnilateral(especificacoes_tecnicas))",
        ),
        (
            "O {party} não poderá ceder os direitos deste contrato sem anuência prévia do {party2}.",
            "Proibicao({agent}, CessaoDireitos(sem_anuencia_{agent2}))",
        ),
    ],
    "PERMISSAO": [
        (
            "O {party} poderá utilizar as instalações do {party2} durante o período de treinamento.",
            "Permissao({agent}, UsoInstalacoes({agent2}))",
        ),
        (
            "O {party} poderá utilizar a imagem do {party2} em campanhas publicitárias aprovadas.",
            "Permissao({agent}, UsoImagem({agent2}, campanhas_aprovadas))",
        ),
        (
            "Mediante aprovação prévia, o {party} poderá rescindir o contrato com aviso de {days} dias.",
            "Condicao(Aprovacao, Permissao({agent}, Rescisao(aviso_{days}dias)))",
        ),
        (
            "O {party} poderá renovar o presente contrato por igual período com até {days} dias de antecedência.",
            "Condicao(Notificacao({agent}, {days}dias), Permissao({agent}, Renovacao(periodo_igual)))",
        ),
    ],
    "CONDICAO": [
        (
            "Caso o {party} não realize o pagamento no prazo, incidirá multa de {pct}% sobre o valor devido.",
            "Condicao(Inadimplencia({agent}, pagamento), Multa({pct_dec}))",
        ),
        (
            "Em caso de descumprimento, o {party} ficará sujeito a penalidade de R$ {value},00.",
            "Condicao(Descumprimento({agent}), Penalidade({value}))",
        ),
        (
            "O {party} receberá bônus de desempenho caso atinja a meta de {pct}% dos indicadores.",
            "Condicao(Meta({agent}, indicadores, {pct_dec}), Permissao({agent}, Bonus))",
        ),
    ],
    "DEFINICAO": [
        (
            "O presente contrato vigorará pelo período de {months} meses a partir da data de assinatura.",
            "Prazo(contrato, DataAssinatura, DataAssinatura + {months}meses)",
        ),
        (
            "O valor total do contrato é de R$ {value}.000,00 ({value_text} reais).",
            "ValorContrato(total, {value}000)",
        ),
        (
            "O reajuste anual será calculado com base no índice {index} do período.",
            "ReajusteAnual(contrato, indice_{index})",
        ),
        (
            "Para fins deste contrato, entende-se por EVENTO qualquer competição oficial organizada pelo {party}.",
            "Definicao(evento, CompeticaoOficial({agent}))",
        ),
        (
            "O foro competente para dirimir quaisquer dúvidas é o da Comarca de {city}.",
            "Foro(contrato, {city_id})",
        ),
    ],
}

# Pares de conflito por tipo — cada entrada é (template_A, template_B, tipo_conflito)
# Os templates usam {party}, {agent}, {value1}, {value2}, {days1}, {days2}, etc.
CONFLICT_TEMPLATES = {
    "OBRIGACAO_PROIBICAO": [
        (
            "O {party} obriga-se a divulgar publicamente os termos gerais do presente contrato.",
            "Obrigacao({agent}, Divulgacao(termos_contrato), Sempre)",
            "É expressamente vedado ao {party} divulgar informações sobre o contrato a terceiros.",
            "Proibicao({agent}, Divulgacao(informacoes_contrato))",
            "Obrigação e proibição simultânea de divulgação ao mesmo agente",
        ),
        (
            "O {party} obriga-se a fornecer suporte médico completo ao atleta durante as competições.",
            "Obrigacao({agent}, Suporte(medico, atleta), Competicao)",
            "O {party} não é responsável por qualquer suporte médico durante as competições.",
            "Proibicao({agent}, Responsabilidade(suporte_medico))",
            "Obrigação de suporte médico contradita por isenção de responsabilidade",
        ),
        (
            "O {party} obriga-se a permitir vistorias técnicas a qualquer momento durante a execução.",
            "Obrigacao({agent}, PermitirVistoria(tecnica), Execucao)",
            "É vedado ao {party} permitir acesso às instalações sem agendamento prévio de 48 horas.",
            "Proibicao({agent}, PermitirAcesso(sem_agendamento_48h))",
            "Permissão irrestrita de vistoria contradita por restrição de acesso",
        ),
        (
            "O {party} deverá utilizar exclusivamente insumos de terceiros certificados pelo {party2}.",
            "Obrigacao({agent}, UsoInsumos(terceiros_certificados_{agent2}), Sempre)",
            "É proibido ao {party} utilizar produtos ou insumos fornecidos por terceiros.",
            "Proibicao({agent}, UsoInsumos(terceiros))",
            "Obrigação de usar insumos de terceiros contradita por proibição de uso de insumos de terceiros",
        ),
    ],
    "OBRIGACOES_MUTUAMENTE_EXCLUSIVAS": [
        (
            "O {party} deverá entregar os relatórios exclusivamente em formato digital (PDF).",
            "Obrigacao({agent}, Entrega(relatorios, formato_digital), Sempre)",
            "O {party} deverá entregar os relatórios exclusivamente em formato físico impresso.",
            "Obrigacao({agent}, Entrega(relatorios, formato_fisico), Sempre)",
            "Formatos de entrega mutuamente exclusivos exigidos simultaneamente",
        ),
        (
            "O {party} deverá executar os serviços utilizando exclusivamente mão de obra própria.",
            "Obrigacao({agent}, ExecucaoServicos(mao_obra_propria), Sempre)",
            "O {party} deverá executar os serviços utilizando exclusivamente equipe terceirizada.",
            "Obrigacao({agent}, ExecucaoServicos(equipe_terceirizada), Sempre)",
            "Fontes de mão de obra mutuamente exclusivas exigidas simultaneamente",
        ),
        (
            "Os pagamentos deverão ser realizados exclusivamente via transferência bancária (TED/PIX).",
            "Obrigacao(partes, Pagamento(via_transferencia_bancaria), Sempre)",
            "Os pagamentos deverão ser realizados exclusivamente por meio de boleto bancário.",
            "Obrigacao(partes, Pagamento(via_boleto_bancario), Sempre)",
            "Modalidades de pagamento mutuamente exclusivas",
        ),
        (
            "O {party} deverá realizar as reuniões de acompanhamento semanalmente.",
            "Obrigacao({agent}, Reuniao(acompanhamento), Semanal)",
            "O {party} deverá realizar as reuniões de acompanhamento mensalmente.",
            "Obrigacao({agent}, Reuniao(acompanhamento), Mensal)",
            "Frequências de reunião incompatíveis (semanal vs. mensal)",
        ),
    ],
    "PRAZO_INCONSISTENTE": [
        (
            "O contrato terá vigência de {months1} ({months1_text}) meses contados da assinatura.",
            "Prazo(contrato, DataAssinatura, DataAssinatura + {months1}meses)",
            "O contrato terá vigência de {months2} ({months2_text}) meses contados da assinatura.",
            "Prazo(contrato, DataAssinatura, DataAssinatura + {months2}meses)",
            "Vigências contratuais incompatíveis definidas no mesmo instrumento",
        ),
        (
            "O pagamento da primeira parcela deverá ser efetuado em {days1} ({days1_text}) dias após a assinatura.",
            "Obrigacao(patrocinador, Pagamento(parcela_1), DataAssinatura + {days1}dias)",
            "O pagamento da primeira parcela deverá ser efetuado em {days2} ({days2_text}) dias após a assinatura.",
            "Obrigacao(patrocinador, Pagamento(parcela_1), DataAssinatura + {days2}dias)",
            "Prazo contraditório para pagamento da primeira parcela",
        ),
        (
            "A entrega do produto final deverá ocorrer em até {days1} ({days1_text}) dias corridos do início.",
            "Obrigacao(contratada, Entrega(produto_final), DataInicio + {days1}dias)",
            "A entrega do produto final deverá ocorrer em até {days2} ({days2_text}) dias corridos do início.",
            "Obrigacao(contratada, Entrega(produto_final), DataInicio + {days2}dias)",
            "Prazo de entrega do produto final definido de forma contraditória",
        ),
        (
            "O prazo de garantia dos serviços prestados será de {months1} ({months1_text}) meses.",
            "PrazoGarantia(servicos, {months1}meses)",
            "O prazo de garantia dos serviços prestados será de {months2} ({months2_text}) meses.",
            "PrazoGarantia(servicos, {months2}meses)",
            "Período de garantia definido com valores inconsistentes",
        ),
    ],
    "CONDICAO_IMPOSSIVEL": [
        (
            "O {party} receberá bonificação apenas se vencer a competição E obtiver índice olímpico.",
            "Condicao(Vitoria({agent}) ∧ IndiceOlimpico({agent}), Permissao({agent}, Bonificacao))",
            "O índice olímpico somente é concedido a atletas que não tenham vencido nenhuma competição seletiva.",
            "∀a.IndiceOlimpico(a) → ¬∃c.Vitoria(a, c)",
            "Bonificação condicionada a dois critérios mutuamente exclusivos (condição nunca satisfatível)",
        ),
        (
            "A rescisão só poderá ser efetuada mediante aprovação formal do Comitê Gestor.",
            "Condicao(AprovacaoComiteGestor, Permissao(partes, Rescisao))",
            "O Comitê Gestor não tem competência para apreciar ou aprovar rescisões contratuais.",
            "Proibicao(comite_gestor, ApreciacaoRescisao)",
            "Rescisão exige aprovação de órgão que está proibido de aprová-la (condição impossível)",
        ),
        (
            "O pagamento da multa rescisória somente ocorrerá após decisão judicial transitada em julgado.",
            "Condicao(DecisaoJudicial(transito_julgado), Pagamento(multa_rescisoria))",
            "Fica eleito o foro arbitral como único competente, sendo vedada qualquer intervenção judicial.",
            "Proibicao(poder_judiciario, Intervencao(disputas_contrato))",
            "Pagamento exige decisão judicial, mas intervenção judicial é vedada (condição impossível)",
        ),
    ],
    "AGENTE_AMBIGUO": [
        (
            "Fica responsável pela coordenação das atividades de patrocínio a parte denominada PATROCINADOR.",
            "Responsavel(patrocinador, Coordenacao(atividades_patrocinio))",
            "Fica responsável pela coordenação das atividades de patrocínio a parte denominada PARCEIRO ESTRATÉGICO.",
            "Responsavel(parceiro_estrategico, Coordenacao(atividades_patrocinio))",
            "Dois nomes diferentes atribuídos ao mesmo responsável, criando ambiguidade de agente",
        ),
        (
            "Os relatórios de execução deverão ser entregues pela CONTRATANTE ao FISCAL DO CONTRATO.",
            "Obrigacao(contratante, Entrega(relatorios_execucao, fiscal), MensalMente)",
            "Os relatórios de execução deverão ser entregues pela CONTRATADA ao FISCAL DO CONTRATO.",
            "Obrigacao(contratada, Entrega(relatorios_execucao, fiscal), MensalMente)",
            "Obrigação de entrega de relatório atribuída a partes diferentes (CONTRATANTE vs. CONTRATADA)",
        ),
        (
            "A gestão financeira dos recursos do contrato compete exclusivamente ao COB.",
            "Responsavel(cob, GestaFinanceira(recursos_contrato))",
            "A gestão financeira dos recursos do contrato compete exclusivamente à CONFEDERAÇÃO.",
            "Responsavel(confederacao, GestaoFinanceira(recursos_contrato))",
            "Gestão financeira atribuída a dois agentes distintos sem distinção de escopo",
        ),
    ],
    "VALOR_INCONSISTENTE": [
        (
            "O valor total do contrato é de R$ {value1}.000,00 ({value1_text} reais).",
            "ValorContrato(total, {value1}000)",
            "O valor total do contrato é de R$ {value2}.000,00 ({value2_text} reais).",
            "ValorContrato(total, {value2}000)",
            "Valor total do contrato definido com montantes contraditórios",
        ),
        (
            "A multa por inadimplência corresponderá a {pct1}% ({pct1_text} por cento) do valor total.",
            "Condicao(Inadimplencia, Multa({pct1_dec}, ValorTotal))",
            "A multa por inadimplência corresponderá a {pct2}% ({pct2_text} por cento) do valor total.",
            "Condicao(Inadimplencia, Multa({pct2_dec}, ValorTotal))",
            "Percentual de multa por inadimplência definido de forma contraditória",
        ),
        (
            "O reajuste anual do contrato será de {pct1}% ({pct1_text} por cento) sobre o valor base.",
            "ReajusteAnual(contrato, {pct1_dec}, ValorBase)",
            "O reajuste anual do contrato será de {pct2}% ({pct2_text} por cento) sobre o valor base.",
            "ReajusteAnual(contrato, {pct2_dec}, ValorBase)",
            "Índice de reajuste anual definido com percentuais contraditórios",
        ),
    ],
}

NUMBER_WORDS = {
    3: "três", 5: "cinco", 6: "seis", 7: "sete",
    10: "dez", 12: "doze", 15: "quinze", 18: "dezoito",
    24: "vinte e quatro", 30: "trinta", 36: "trinta e seis",
    45: "quarenta e cinco", 60: "sessenta", 90: "noventa",
    180: "cento e oitenta",
}

VALUE_WORDS = {
    500: "quinhentos mil",
    800: "oitocentos mil",
    1000: "hum milhão",
    1200: "hum milhão e duzentos mil",
    1500: "hum milhão e quinhentos mil",
    2000: "dois milhões",
    3000: "três milhões",
}

CITIES = [
    ("Rio de Janeiro", "rio_de_janeiro"),
    ("São Paulo", "sao_paulo"),
    ("Brasília", "brasilia"),
    ("Belo Horizonte", "belo_horizonte"),
]

INDICES = ["IPCA", "IGP-M", "INPC", "IPCA-E"]


# ---------------------------------------------------------------------------
# Gerador principal
# ---------------------------------------------------------------------------

class DatasetGenerator:
    """Gera dataset sintético de contratos com inconsistências injetadas."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.clause_counter = 0
        self.contract_counter = 0
        self.conflict_counter = 0

    def _next_clause_id(self) -> str:
        self.clause_counter += 1
        return f"CL{self.clause_counter:03d}"

    def _next_conflict_id(self) -> str:
        self.conflict_counter += 1
        return f"CP{self.conflict_counter:03d}"

    def _pick(self, lst: list):
        return self.rng.choice(lst)

    def _fill_template(self, template: str, **kwargs) -> str:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    def _random_party_pair(self):
        """Retorna dois agentes distintos."""
        parties = self.rng.sample(PARTIES, 2)
        return parties[0], parties[1]

    def _random_values(self, different: bool = True):
        """Retorna dois valores monetários (diferentes se different=True)."""
        keys = list(VALUE_WORDS.keys())
        v1 = self._pick(keys)
        if different:
            keys2 = [k for k in keys if k != v1]
            v2 = self._pick(keys2)
        else:
            v2 = v1
        return v1, v2

    def _random_months_pair(self):
        """Retorna dois prazos em meses incompatíveis."""
        options = [6, 12, 18, 24, 36]
        m1, m2 = self.rng.sample(options, 2)
        return m1, m2

    def _random_days_pair(self):
        """Retorna dois prazos em dias incompatíveis."""
        options = [15, 30, 45, 60, 90, 180]
        d1, d2 = self.rng.sample(options, 2)
        return d1, d2

    def _random_pct_pair(self):
        """Retorna dois percentuais incompatíveis."""
        options = [5, 8, 10, 15, 20, 25]
        p1, p2 = self.rng.sample(options, 2)
        return p1, p2

    def generate_plain_clause(self, contract_id: str) -> dict:
        """Gera uma cláusula sem conflito."""
        modality = self._pick(list(CLAUSE_TEMPLATES.keys()))
        templates = CLAUSE_TEMPLATES[modality]
        text_tmpl, fol_tmpl = self._pick(templates)

        party1, party2 = self._random_party_pair()
        months = self._pick([6, 12, 18, 24, 36])
        days = self._pick([15, 30, 45, 60, 90])
        n = self._pick([3, 5, 10, 12, 15])
        pct = self._pick([5, 8, 10, 15, 20])
        value = self._pick(list(VALUE_WORDS.keys()))
        city, city_id = self._pick(CITIES)
        index = self._pick(INDICES)

        kwargs = {
            "party": party1[0], "agent": party1[1],
            "party2": party2[0], "agent2": party2[1],
            "months": months, "months_text": NUMBER_WORDS.get(months, str(months)),
            "days": days, "days_text": NUMBER_WORDS.get(days, str(days)),
            "n": n, "day": self._pick([5, 10, 15]),
            "pct": pct, "pct_dec": round(pct / 100, 2),
            "value": value, "value_text": VALUE_WORDS.get(value, str(value)),
            "city": city, "city_id": city_id,
            "index": index,
        }

        clause_id = self._next_clause_id()
        return {
            "id": clause_id,
            "text": self._fill_template(text_tmpl, **kwargs),
            "modality": modality,
            "agent": party1[1],
            "fol_gold": self._fill_template(fol_tmpl, **kwargs),
            "notes": f"Cláusula gerada sinteticamente — contrato {contract_id}",
            "contract_id": contract_id,
            "has_conflict": False,
        }

    def generate_conflict_pair(self, contract_id: str) -> tuple[dict, dict, dict]:
        """
        Gera um par de cláusulas com conflito injetado.

        Returns:
            (clause_a, clause_b, conflict_record)
        """
        conflict_type = self._pick(list(CONFLICT_TEMPLATES.keys()))
        templates = CONFLICT_TEMPLATES[conflict_type]
        entry = self._pick(templates)
        text_a_tmpl, fol_a_tmpl, text_b_tmpl, fol_b_tmpl, description = entry

        party1, party2 = self._random_party_pair()
        months1, months2 = self._random_months_pair()
        days1, days2 = self._random_days_pair()
        value1, value2 = self._random_values()
        pct1, pct2 = self._random_pct_pair()

        kwargs = {
            "party": party1[0], "agent": party1[1],
            "party2": party2[0], "agent2": party2[1],
            "months1": months1, "months1_text": NUMBER_WORDS.get(months1, str(months1)),
            "months2": months2, "months2_text": NUMBER_WORDS.get(months2, str(months2)),
            "days1": days1, "days1_text": NUMBER_WORDS.get(days1, str(days1)),
            "days2": days2, "days2_text": NUMBER_WORDS.get(days2, str(days2)),
            "value1": value1, "value1_text": VALUE_WORDS.get(value1, str(value1)),
            "value2": value2, "value2_text": VALUE_WORDS.get(value2, str(value2)),
            "pct1": pct1, "pct1_text": NUMBER_WORDS.get(pct1, str(pct1)),
            "pct1_dec": round(pct1 / 100, 2),
            "pct2": pct2, "pct2_text": NUMBER_WORDS.get(pct2, str(pct2)),
            "pct2_dec": round(pct2 / 100, 2),
        }

        id_a = self._next_clause_id()
        id_b = self._next_clause_id()

        clause_a = {
            "id": id_a,
            "text": self._fill_template(text_a_tmpl, **kwargs),
            "modality": "OBRIGACAO_ATIVA" if "Obrigacao" in fol_a_tmpl else "PROIBICAO",
            "agent": party1[1],
            "fol_gold": self._fill_template(fol_a_tmpl, **kwargs),
            "notes": f"Par conflitante ({conflict_type}) — contrato {contract_id}",
            "contract_id": contract_id,
            "has_conflict": True,
        }
        clause_b = {
            "id": id_b,
            "text": self._fill_template(text_b_tmpl, **kwargs),
            "modality": "PROIBICAO" if "Proibicao" in fol_b_tmpl else "OBRIGACAO_ATIVA",
            "agent": party1[1],
            "fol_gold": self._fill_template(fol_b_tmpl, **kwargs),
            "notes": f"Par conflitante ({conflict_type}) — contrato {contract_id}",
            "contract_id": contract_id,
            "has_conflict": True,
        }
        conflict = {
            "id": self._next_conflict_id(),
            "clause_ids": [id_a, id_b],
            "conflict_type": conflict_type,
            "description": description,
            "resolution": "Revisar e alinhar as cláusulas conflitantes",
            "contract_id": contract_id,
        }
        return clause_a, clause_b, conflict

    def generate_contract(
        self,
        contract_id: str,
        num_clauses: int = 40,
        num_conflicts: int = 0,
    ) -> tuple[list[dict], list[dict], str]:
        """
        Gera um contrato sintético.

        Returns:
            (clauses, conflict_pairs, contract_text)
        """
        clauses: list[dict] = []
        conflict_pairs: list[dict] = []

        # Cláusulas definitórias iniciais (partes, vigência, valor)
        for _ in range(min(3, num_clauses)):
            clauses.append(self.generate_plain_clause(contract_id))

        # Pares de conflito injetados
        for _ in range(num_conflicts):
            ca, cb, conflict = self.generate_conflict_pair(contract_id)
            clauses.append(ca)
            clauses.append(cb)
            conflict_pairs.append(conflict)

        # Cláusulas regulares para completar
        remaining = num_clauses - len(clauses)
        for _ in range(max(0, remaining)):
            clauses.append(self.generate_plain_clause(contract_id))

        # Embaralhar cláusulas (exceto as 3 iniciais)
        initial = clauses[:3]
        rest = clauses[3:]
        self.rng.shuffle(rest)
        clauses = initial + rest

        # Gerar texto do contrato
        contract_text = self._render_contract_text(contract_id, clauses)

        return clauses, conflict_pairs, contract_text

    def _render_contract_text(self, contract_id: str, clauses: list[dict]) -> str:
        """Renderiza o contrato como texto corrido."""
        contract_type = self._pick(CONTRACT_TYPES)
        party1, party2 = self._random_party_pair()
        lines = [
            f"{contract_type.upper()}",
            f"Identificador: {contract_id}",
            "",
            f"As partes, {party1[0]} e {party2[0]}, celebram o presente contrato nos termos abaixo:",
            "",
        ]
        for i, cl in enumerate(clauses, 1):
            lines.append(f"Cláusula {i}ª — {cl['text']}")
            lines.append("")
        lines.append("Rio de Janeiro, data de assinatura.")
        return "\n".join(lines)

    def generate_dataset(
        self,
        num_contracts: int = 50,
        inconsistency_rate: float = 0.6,
        clauses_per_contract: int = 45,
        conflicts_per_inconsistent_contract: int = 2,
    ) -> tuple[list[dict], list[dict]]:
        """
        Gera o dataset completo.

        Returns:
            (all_clauses, all_conflicts)
        """
        all_clauses: list[dict] = []
        all_conflicts: list[dict] = []

        num_inconsistent = round(num_contracts * inconsistency_rate)

        for i in range(num_contracts):
            contract_id = f"CTR{i + 1:03d}"
            self.contract_counter += 1
            has_inconsistency = i < num_inconsistent
            num_conflicts = conflicts_per_inconsistent_contract if has_inconsistency else 0

            clauses, conflicts, _ = self.generate_contract(
                contract_id=contract_id,
                num_clauses=clauses_per_contract,
                num_conflicts=num_conflicts,
            )
            all_clauses.extend(clauses)
            all_conflicts.extend(conflicts)

        return all_clauses, all_conflicts


def main():
    parser = argparse.ArgumentParser(
        description="Gera dataset sintético de contratos para avaliação do ContractFOL"
    )
    parser.add_argument(
        "--num-contracts",
        type=int,
        default=50,
        help="Número total de contratos a gerar (default: 50)",
    )
    parser.add_argument(
        "--inconsistency-rate",
        type=float,
        default=0.6,
        help="Fração de contratos com inconsistências injetadas (default: 0.6)",
    )
    parser.add_argument(
        "--clauses-per-contract",
        type=int,
        default=45,
        help="Número de cláusulas por contrato (default: 45)",
    )
    parser.add_argument(
        "--conflicts-per-contract",
        type=int,
        default=2,
        help="Número de pares de conflito por contrato inconsistente (default: 2)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente aleatória para reprodutibilidade (default: 42)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/contracts",
        help="Diretório para arquivos .txt dos contratos (default: data/contracts)",
    )
    parser.add_argument(
        "--clauses-file",
        type=str,
        default="data/clauses/clausulas_sinteticas.json",
        help="Arquivo JSON de saída com ground truth sintético",
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="Não exportar arquivos .txt individuais",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ContractFOL — Gerador de Dataset Sintético")
    print("=" * 60)
    print(f"Contratos:              {args.num_contracts}")
    print(f"Taxa de inconsistência: {args.inconsistency_rate:.0%}")
    print(f"Cláusulas/contrato:     {args.clauses_per_contract}")
    print(f"Conflitos/contrato:     {args.conflicts_per_contract}")
    print(f"Seed:                   {args.seed}")
    print()

    generator = DatasetGenerator(seed=args.seed)
    all_clauses, all_conflicts = generator.generate_dataset(
        num_contracts=args.num_contracts,
        inconsistency_rate=args.inconsistency_rate,
        clauses_per_contract=args.clauses_per_contract,
        conflicts_per_inconsistent_contract=args.conflicts_per_contract,
    )

    print(f"Geradas {len(all_clauses)} cláusulas e {len(all_conflicts)} pares de conflito.")

    # Exportar contratos individuais em .txt
    if not args.no_txt:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Agrupar cláusulas por contrato
        contracts: dict[str, list[dict]] = {}
        for cl in all_clauses:
            cid = cl.get("contract_id", "unknown")
            contracts.setdefault(cid, []).append(cl)

        generator2 = DatasetGenerator(seed=args.seed)
        for contract_id, clauses in contracts.items():
            text = generator2._render_contract_text(contract_id, clauses)
            txt_path = output_dir / f"{contract_id}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

        print(f"Contratos .txt salvos em: {output_dir}/ ({len(contracts)} arquivos)")

    # Exportar ground truth em JSON
    clauses_path = Path(args.clauses_file)
    clauses_path.parent.mkdir(parents=True, exist_ok=True)

    # Limpar campos internos antes de exportar
    export_clauses = [
        {k: v for k, v in cl.items() if k != "has_conflict"}
        for cl in all_clauses
    ]
    export_conflicts = [
        {k: v for k, v in cf.items()}
        for cf in all_conflicts
    ]

    num_inconsistent = round(args.num_contracts * args.inconsistency_rate)
    payload = {
        "metadata": {
            "description": "Dataset sintético gerado automaticamente para avaliação do ContractFOL",
            "version": "synthetic-1.0",
            "language": "pt-BR",
            "domain": "contratos esportivos (patrocínio, fornecimento, atleta)",
            "seed": args.seed,
            "num_contracts": args.num_contracts,
            "num_inconsistent_contracts": num_inconsistent,
            "inconsistency_rate": args.inconsistency_rate,
            "total_clauses": len(export_clauses),
            "total_conflict_pairs": len(export_conflicts),
        },
        "clauses": export_clauses,
        "conflict_pairs": export_conflicts,
    }

    with open(clauses_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Ground truth salvo em: {clauses_path}")
    print()
    print("Estatísticas do dataset gerado:")
    print(f"  Total de cláusulas:        {len(export_clauses)}")
    print(f"  Total de pares conflitantes: {len(export_conflicts)}")
    print(f"  Contratos com conflito:    {num_inconsistent}/{args.num_contracts}")
    print()
    print("Para usar no experimento, rode:")
    print(f"  python scripts/run_experiment.py --clauses-file {args.clauses_file} --methods contractfol baseline")


if __name__ == "__main__":
    main()
