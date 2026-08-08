"""Pure deterministic combat rules shared by legacy adapters."""

from collections.abc import Mapping
from typing import Any, Optional

from chronos.domain import resolution


ARMOR_DAMAGE_REDUCTION = 2
SHIP_DAMAGE_ON_SHIELDS = 15
SHIP_DAMAGE_ON_HULL = 10
FLANQUEAR_DAMAGE_BONUS = 2


_PERSONAL_ATTACK_OUTCOMES = {
    "SUCESSO_CRITICO": "SUCESSO CRÍTICO",
    "SUCESSO": "SUCESSO",
    "FALHA": "FALHA",
    "FALHA_CRITICA": "FALHA CRÍTICA",
}


def _resolve_personal_check(
    modifier: int,
    enemy_dc: int,
    attack_d20_raw: int,
) -> dict:
    check = resolution.resolve_check(modifier, enemy_dc, attack_d20_raw)
    return {
        "d20_raw": check["d20_raw"],
        "total_attack": check["total"],
        "check_result": check["result"],
        "is_critical": check["result"] == "SUCESSO_CRITICO",
        "is_success": check["result"] in ("SUCESSO_CRITICO", "SUCESSO"),
    }


def _resolve_personal_attack_core(
    check: Mapping[str, Any],
    damage_d4_raw: int,
    weapon_damage_bonus: int,
    weapon_effect: Optional[str],
    effect_dc: int,
    effect_d20_raw: Optional[int],
    effect_requires_damage: bool,
) -> dict:
    """Apply personal d4, weapon bonus, and effect rules after a resolved check."""
    if check["is_success"]:
        effective_d4_damage = damage_d4_raw * (2 if check["is_critical"] else 1)
        weapon_bonus = weapon_damage_bonus
        damage_dealt = effective_d4_damage + weapon_bonus
    else:
        effective_d4_damage = 0
        weapon_bonus = 0
        damage_dealt = 0

    effect_allowed = damage_dealt > 0 if effect_requires_damage else check["is_success"]
    effect_eligible = bool(
        effect_allowed
        and weapon_effect
        and effect_d20_raw is not None
        and (check["is_critical"] or effect_d20_raw >= effect_dc)
    )

    return {
        "effective_d4_damage": effective_d4_damage,
        "weapon_bonus": weapon_bonus,
        "damage_dealt": damage_dealt,
        "effect_eligible": effect_eligible,
        "effect_applied": weapon_effect if effect_eligible else None,
    }


def prepare_personal_attack(
    player_modifier: int,
    enemy_dc: int,
    attack_d20_raw: int,
    attack_bonus: int = 0,
    attack_penalty: int = 0,
    weapon_effect: Optional[str] = None,
) -> dict:
    """Classify one live personal attack and state which follow-up rolls it needs."""
    check = _resolve_personal_check(
        player_modifier + attack_bonus + attack_penalty,
        enemy_dc,
        attack_d20_raw,
    )

    return {
        "d20_raw": check["d20_raw"],
        "total_attack": check["total_attack"],
        "check_result": check["check_result"],
        "outcome": _PERSONAL_ATTACK_OUTCOMES[check["check_result"]],
        "is_critical": check["is_critical"],
        "requires_damage_roll": check["is_success"],
        "requires_effect_roll": check["is_success"] and bool(weapon_effect),
    }


def resolve_personal_attack(
    preparation: Mapping[str, Any],
    damage_d4_raw: Optional[int],
    weapon_damage_bonus: int = 0,
    fixed_damage_bonus: int = 0,
    melee_damage_bonus: int = 0,
    position: str = "",
    weapon_effect: Optional[str] = None,
    weapon_effect_dc: Optional[int] = None,
    effect_d20_raw: Optional[int] = None,
) -> dict:
    """Resolve one live personal attack from its prepared check and rolled inputs."""

    if preparation["requires_damage_roll"]:
        if damage_d4_raw is None:
            raise ValueError("damage_d4_raw is required for a successful personal attack")
        d4_raw = damage_d4_raw
    else:
        d4_raw = None

    effect_dc = weapon_effect_dc if weapon_effect_dc is not None else 12
    if preparation["requires_effect_roll"] and effect_d20_raw is None:
        raise ValueError("effect_d20_raw is required for a successful weapon-effect attack")
    core = _resolve_personal_attack_core(
        {**preparation, "is_success": preparation["requires_damage_roll"]},
        d4_raw or 0,
        weapon_damage_bonus,
        weapon_effect,
        effect_dc,
        effect_d20_raw,
        effect_requires_damage=False,
    )
    applied_fixed_bonus = fixed_damage_bonus if preparation["requires_damage_roll"] else 0
    applied_melee_bonus = (
        melee_damage_bonus
        if preparation["requires_damage_roll"] and position in ("MELEE", "FLANQUEANDO")
        else 0
    )
    flanking_damage_bonus = (
        FLANQUEAR_DAMAGE_BONUS
        if preparation["requires_damage_roll"] and position == "FLANQUEANDO"
        else 0
    )

    return {
        **preparation,
        "d4_raw": d4_raw,
        "effective_d4_damage": core["effective_d4_damage"],
        "weapon_bonus": core["weapon_bonus"],
        "fixed_damage_bonus": applied_fixed_bonus,
        "melee_damage_bonus": applied_melee_bonus,
        "flanking_damage_bonus": flanking_damage_bonus,
        "damage_dealt": (
            core["damage_dealt"]
            + applied_fixed_bonus
            + applied_melee_bonus
            + flanking_damage_bonus
        ),
        "effect_d20_raw": effect_d20_raw,
        "effect_dc": effect_dc,
        "effect_eligible": core["effect_eligible"],
        "effect_applied": core["effect_applied"],
    }


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
    check = _resolve_personal_check(player_attr, enemy_dc, attack_d20_raw)

    weapon = weapon_definition or {}
    weapon_bonus: int = weapon.get("damage_bonus", 0)
    d4_raw = damage_d4_raw
    effect_id = weapon.get("effect")
    effect_dc = weapon.get("effect_dc", 12)
    core = _resolve_personal_attack_core(
        check,
        d4_raw,
        weapon_bonus,
        effect_id,
        effect_dc,
        effect_d20_raw,
        effect_requires_damage=True,
    )

    damage_taken = (
        0
        if enemy_is_stunned
        else max(0, enemy_damage - armor_reduction)
    )

    return {
        "d20_raw": check["d20_raw"],
        "total_attack": check["total_attack"],
        "check_result": check["check_result"],
        "is_critical": check["is_critical"],
        "d4_raw": d4_raw,
        "weapon_bonus": weapon_bonus,
        "damage_dealt": core["damage_dealt"],
        "damage_reduction": armor_reduction,
        "damage_taken": damage_taken,
        "effect_applied": core["effect_applied"],
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
