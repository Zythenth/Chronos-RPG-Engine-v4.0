"""Pure deterministic combat rules shared by legacy adapters."""

from collections.abc import Mapping
from typing import Any, Optional

from chronos.domain import resolution


ARMOR_DAMAGE_REDUCTION = 2
SHIP_DAMAGE_ON_SHIELDS = 15
SHIP_DAMAGE_ON_HULL = 10


def get_armor_reduction(
    armor_name: Optional[str],
    armor_definition: Optional[Mapping[str, Any]] = None,
) -> int:
    """Resolve damage reduction from explicitly supplied armor data."""
    if not armor_name:
        return 0
    if armor_definition is None:
        return ARMOR_DAMAGE_REDUCTION
    return armor_definition.get("damage_reduction", ARMOR_DAMAGE_REDUCTION)


def resolve_personal_combat(
    player_attr: int,
    enemy_dc: int,
    enemy_damage: int,
    attack_d20_raw: int,
    damage_d4_raw: int,
    armor_reduction: int,
    weapon_definition: Optional[Mapping[str, Any]] = None,
    enemy_is_stunned: bool = False,
    effect_d20_raw: Optional[int] = None,
) -> dict:
    """Resolve one personal attack from pre-rolled values and resolved data."""
    check = resolution.resolve_check(player_attr, enemy_dc, attack_d20_raw)
    d20_raw = check["d20_raw"]
    is_critical = d20_raw == 20

    weapon = weapon_definition or {}
    weapon_bonus: int = weapon.get("damage_bonus", 0)
    d4_raw = damage_d4_raw

    if check["result"] in ("SUCESSO_CRITICO", "SUCESSO"):
        base = d4_raw * 2 if is_critical else d4_raw
        damage_dealt = base + weapon_bonus
    else:
        damage_dealt = 0

    damage_taken = (
        0
        if enemy_is_stunned
        else max(0, enemy_damage - armor_reduction)
    )

    effect_applied: Optional[str] = None
    if damage_dealt > 0 and weapon.get("effect"):
        effect_id = weapon["effect"]
        effect_dc = weapon.get("effect_dc", 12)
        if effect_d20_raw is not None and (effect_d20_raw >= effect_dc or is_critical):
            effect_applied = effect_id

    return {
        "d20_raw": d20_raw,
        "total_attack": check["total"],
        "check_result": check["result"],
        "is_critical": is_critical,
        "d4_raw": d4_raw,
        "weapon_bonus": weapon_bonus,
        "damage_dealt": damage_dealt,
        "damage_reduction": armor_reduction,
        "damage_taken": damage_taken,
        "effect_applied": effect_applied,
    }


def resolve_ship_combat(
    player_piloting: int,
    enemy_ac: int,
    enemy_shields: int,
    d20_raw: int,
) -> dict:
    """Resolve one ship-to-ship cannon shot from a pre-rolled d20."""
    check = resolution.resolve_check(player_piloting, enemy_ac, d20_raw)

    if check["result"] in ("SUCESSO_CRITICO", "SUCESSO"):
        if enemy_shields > 0:
            shield_damage, hull_damage = SHIP_DAMAGE_ON_SHIELDS, 0
        else:
            shield_damage, hull_damage = 0, SHIP_DAMAGE_ON_HULL
    else:
        shield_damage, hull_damage = 0, 0

    return {
        "d20_raw": check["d20_raw"],
        "total_attack": check["total"],
        "check_result": check["result"],
        "shield_damage": shield_damage,
        "hull_damage": hull_damage,
    }
