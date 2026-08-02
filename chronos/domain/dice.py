"""Pure dice and multi-roll rules shared by the legacy adapters."""

from collections.abc import Callable
import secrets

from .resolution import calc_modifier


Choice = Callable[[range], int]
Roller = Callable[[int, int], list[int]]


# Index zero represents attribute 1. Criteria stay normalized here; adapters
# project the legacy casing and accentuation they expose publicly.
MULTI_ROLL_TABLE: tuple[tuple[int, str], ...] = (
    (5, "pior"),
    (4, "pior"),
    (4, "pior"),
    (3, "pior"),
    (3, "pior"),
    (2, "pior"),
    (2, "pior"),
    (1, "unico"),
    (1, "unico"),
    (2, "melhor"),
    (2, "melhor"),
    (3, "melhor"),
    (3, "melhor"),
    (4, "melhor"),
    (4, "melhor"),
    (5, "melhor"),
    (5, "melhor"),
    (6, "melhor"),
    (6, "melhor"),
    (7, "melhor"),
)


def clamp_attribute(attribute_value: int) -> int:
    return max(1, min(20, attribute_value))


def multi_roll_rule(attribute_value: int) -> tuple[int, str]:
    return MULTI_ROLL_TABLE[clamp_attribute(attribute_value) - 1]


def roll_die(faces: int, choice: Choice | None = None) -> int:
    source = secrets.choice if choice is None else choice
    return source(range(1, faces + 1))


def roll_d20(choice: Choice | None = None) -> int:
    return roll_die(20, choice)


def roll_d4(choice: Choice | None = None) -> int:
    return roll_die(4, choice)


def roll_many(faces: int, count: int, choice: Choice | None = None) -> list[int]:
    return [roll_die(faces, choice) for _ in range(count)]


def select_roll(results: list[int], criterion: str) -> int:
    if criterion == "melhor":
        return max(results)
    if criterion == "pior":
        return min(results)
    return results[0]


def criterion_label(criterion: str) -> str:
    if criterion == "melhor":
        return "MELHOR"
    if criterion == "pior":
        return "PIOR"
    return "ÚNICO"


def modifier_suffix(modifier: int) -> str:
    if modifier == 0:
        return ""
    return f"({modifier:+})"


def multi_roll(
    faces: int,
    attribute_value: int,
    roller: Roller | None = None,
) -> tuple[list[int], int, str, str]:
    clamped = clamp_attribute(attribute_value)
    count, criterion = multi_roll_rule(clamped)
    results = roll_many(faces, count) if roller is None else roller(faces, count)
    used = select_roll(results, criterion)
    return results, used, criterion_label(criterion), modifier_suffix(calc_modifier(clamped))
