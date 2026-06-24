from clause_llm_eval.eval.parsers import parse_eval1, parse_eval2, parse_eval3


def test_parse_eval1_yes():
    assert parse_eval1("Yes")[0] == 1


def test_parse_eval1_no():
    assert parse_eval1("No.")[0] == 0


def test_parse_eval2_in_text():
    assert parse_eval2("in_text")[0] == "in_text"


def test_parse_eval2_legal():
    assert parse_eval2("legal")[0] == "legal"


def test_parse_eval3_object():
    pred, err = parse_eval3('{"has_discrepancy": true, "dimension": "in_text", "spans": []}')

    assert err is None
    assert pred["has_discrepancy"] is True


def test_parse_eval3_array():
    pred, err = parse_eval3('[{"text": "Section 2", "explanation": "Conflict"}]')

    assert err is None
    assert pred["has_discrepancy"] is True
    assert pred["spans"][0]["text"] == "Section 2"
