from __future__ import annotations


def build_prompt(task: str, doc: str) -> str:
    if task == "eval1":
        return build_eval1_prompt(doc)
    if task == "eval2":
        return build_eval2_prompt(doc)
    if task == "eval3":
        return build_eval3_prompt(doc)
    raise ValueError(f"Tarefa desconhecida: {task}")


def build_eval1_prompt(doc: str) -> str:
    return f"""
You are a U.S. contract attorney who answers concisely.
Please read the legal document below in full.

Document:
\"\"\"
{doc}
\"\"\"

Does this document contain any discrepancy?
Reply with only "Yes" or "No".
""".strip()


def build_eval2_prompt(doc: str) -> str:
    return f"""
You are a U.S. contract attorney who answers concisely.
Please read the legal document below in full.

Document:
\"\"\"
{doc}
\"\"\"

Classify the discrepancy in the document into exactly one of the following labels:
- "in_text": an internal discrepancy, where one part of the document conflicts with another part of the same document.
- "legal": an external legal discrepancy, where the document conflicts with a statute, regulation, or legal requirement.
- "none": no discrepancy.

Reply with only one label: "in_text", "legal", or "none".
""".strip()


def build_eval3_prompt(doc: str) -> str:
    return f"""
You are a U.S. contract attorney who answers concisely.
Please read the legal document below in full.

Document:
\"\"\"
{doc}
\"\"\"

Identify the span or spans that reveal the discrepancy.
Return only valid JSON in this exact schema:
{{
  "has_discrepancy": true,
  "dimension": "in_text|legal",
  "spans": [
    {{
      "text": "exact copied text from the document when possible",
      "explanation": "short explanation",
      "law_citation": "citation or null"
    }}
  ]
}}

If there is no discrepancy, return:
{{
  "has_discrepancy": false,
  "dimension": "none",
  "spans": []
}}
""".strip()
