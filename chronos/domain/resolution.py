"""Deterministic legacy test-resolution rules."""


def calc_modifier(attribute_value: int) -> int:
    """Return the legacy attribute modifier (attribute value minus ten)."""
    return attribute_value - 10


def resolve_check(modifier: int, dc: int, d20_raw: int) -> dict:
    """Resolve a pre-rolled d20 against a DC using the legacy outcomes."""
    total = d20_raw + modifier

    if d20_raw == 20:
        outcome = "SUCESSO_CRITICO"
    elif d20_raw == 1:
        outcome = "FALHA_CRITICA"
    elif total >= dc:
        outcome = "SUCESSO"
    else:
        outcome = "FALHA"

    return {"d20_raw": d20_raw, "total": total, "dc": dc, "result": outcome}
