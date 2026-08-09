"""Independent regression coverage for the extracted combat domain."""

import ast
import inspect
import itertools
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

import mechanics_engine
from chronos.domain import combat, resolution


PERSONAL_RESULT_KEYS = [
    "d20_raw",
    "total_attack",
    "check_result",
    "is_critical",
    "d4_raw",
    "weapon_bonus",
    "damage_dealt",
    "damage_reduction",
    "damage_taken",
    "effect_applied",
]
SHIP_RESULT_KEYS = [
    "d20_raw",
    "total_attack",
    "check_result",
    "shield_damage",
    "hull_damage",
]


def _resolve_live_personal_attack(
    player_modifier: int,
    enemy_dc: int,
    attack_d20_raw: int,
    damage_d4_raw: int | None,
    weapon_damage_bonus: int = 0,
    fixed_damage_bonus: int = 0,
    melee_damage_bonus: int = 0,
    position: str = "",
    weapon_effect: str | None = None,
    weapon_effect_dc: int | None = None,
    effect_d20_raw: int | None = None,
    attack_bonus: int = 0,
    attack_penalty: int = 0,
) -> dict:
    preparation = combat.prepare_personal_attack(
        player_modifier,
        enemy_dc,
        attack_d20_raw,
        attack_bonus,
        attack_penalty,
        weapon_effect,
    )
    return combat.resolve_personal_attack(
        preparation,
        damage_d4_raw,
        weapon_damage_bonus,
        fixed_damage_bonus,
        melee_damage_bonus,
        position,
        weapon_effect,
        weapon_effect_dc,
        effect_d20_raw,
    )


class CombatDomainTests(unittest.TestCase):
    def test_constants_are_shared_by_the_legacy_module(self):
        self.assertEqual(combat.ARMOR_DAMAGE_REDUCTION, 2)
        self.assertEqual(combat.SHIP_DAMAGE_ON_SHIELDS, 15)
        self.assertEqual(combat.SHIP_DAMAGE_ON_HULL, 10)
        self.assertEqual(combat.FLANQUEAR_DAMAGE_BONUS, 2)

    def test_live_personal_attack_preparation_uses_resolution_and_gates_rolls(self):
        cases = (
            (
                (2, 15, 12, 1, 0, "atordoamento"),
                {
                    "d20_raw": 12,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    "outcome": "SUCESSO",
                    "is_critical": False,
                    "requires_damage_roll": True,
                    "requires_effect_roll": True,
                },
            ),
            (
                (100, -10, 1, 0, 0, "atordoamento"),
                {
                    "d20_raw": 1,
                    "total_attack": 101,
                    "check_result": "FALHA_CRITICA",
                    "outcome": "FALHA CRÍTICA",
                    "is_critical": False,
                    "requires_damage_roll": False,
                    "requires_effect_roll": False,
                },
            ),
        )

        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(combat.prepare_personal_attack(*inputs), expected)

    def test_live_personal_attack_final_resolution_consumes_one_preparation(self):
        with (
            mock.patch.object(
                resolution,
                "resolve_check",
                wraps=resolution.resolve_check,
            ) as resolve_check,
            mock.patch.object(
                combat,
                "prepare_personal_attack",
                wraps=combat.prepare_personal_attack,
            ) as prepare,
            mock.patch.object(
                combat,
                "_resolve_personal_check",
                wraps=combat._resolve_personal_check,
            ) as resolve_personal_check,
        ):
            preparation = combat.prepare_personal_attack(
                player_modifier=2,
                enemy_dc=15,
                attack_d20_raw=12,
                attack_bonus=1,
            )
            result = combat.resolve_personal_attack(
                preparation=preparation,
                damage_d4_raw=1,
            )

        self.assertEqual(result["outcome"], "SUCESSO")
        self.assertEqual(result["damage_dealt"], 1)
        prepare.assert_called_once()
        resolve_personal_check.assert_called_once_with(3, 15, 12)
        resolve_check.assert_called_once_with(3, 15, 12)

    def test_live_personal_attack_preserves_576_preparation_resolution_combinations(self):
        combinations = itertools.product(
            (1, 10, 20),
            (0, 1),
            (0, -4),
            (0, 3),
            (0, 1),
            (0, 2),
            ("DISTANCIA", "MELEE", "FLANQUEANDO"),
            (None, "atordoamento"),
        )

        for (
            attack_d20_raw,
            attack_bonus,
            attack_penalty,
            damage_d4_raw,
            weapon_damage_bonus,
            fixed_damage_bonus,
            position,
            weapon_effect,
        ) in combinations:
            with self.subTest(
                d20=attack_d20_raw,
                bonus=attack_bonus,
                penalty=attack_penalty,
                damage=damage_d4_raw,
                weapon_bonus=weapon_damage_bonus,
                fixed_bonus=fixed_damage_bonus,
                position=position,
                effect=weapon_effect,
            ):
                preparation = combat.prepare_personal_attack(
                    2,
                    12,
                    attack_d20_raw,
                    attack_bonus,
                    attack_penalty,
                    weapon_effect,
                )
                result = combat.resolve_personal_attack(
                    preparation,
                    damage_d4_raw if preparation["requires_damage_roll"] else None,
                    weapon_damage_bonus,
                    fixed_damage_bonus,
                    0,
                    position,
                    weapon_effect,
                    12,
                    12 if weapon_effect else None,
                )

                total_attack = attack_d20_raw + 2 + attack_bonus + attack_penalty
                if attack_d20_raw == 20:
                    check_result = "SUCESSO_CRITICO"
                elif attack_d20_raw == 1:
                    check_result = "FALHA_CRITICA"
                elif total_attack >= 12:
                    check_result = "SUCESSO"
                else:
                    check_result = "FALHA"
                is_success = check_result in ("SUCESSO_CRITICO", "SUCESSO")
                is_critical = check_result == "SUCESSO_CRITICO"
                effective_d4_damage = damage_d4_raw * (2 if is_critical else 1) if is_success else 0
                applied_weapon_bonus = weapon_damage_bonus if is_success else 0
                applied_fixed_bonus = fixed_damage_bonus if is_success else 0
                flanking_damage_bonus = 2 if is_success and position == "FLANQUEANDO" else 0
                damage_dealt = (
                    effective_d4_damage
                    + applied_weapon_bonus
                    + applied_fixed_bonus
                    + flanking_damage_bonus
                )
                effect_eligible = bool(
                    is_success
                    and weapon_effect
                    and (is_critical or 12 >= 12)
                )

                self.assertEqual(
                    result,
                    {
                        "d20_raw": attack_d20_raw,
                        "total_attack": total_attack,
                        "check_result": check_result,
                        "outcome": {
                            "SUCESSO_CRITICO": "SUCESSO CRÍTICO",
                            "SUCESSO": "SUCESSO",
                            "FALHA": "FALHA",
                            "FALHA_CRITICA": "FALHA CRÍTICA",
                        }[check_result],
                        "is_critical": is_critical,
                        "requires_damage_roll": is_success,
                        "requires_effect_roll": is_success and bool(weapon_effect),
                        "d4_raw": damage_d4_raw if is_success else None,
                        "effective_d4_damage": effective_d4_damage,
                        "weapon_bonus": applied_weapon_bonus,
                        "fixed_damage_bonus": applied_fixed_bonus,
                        "melee_damage_bonus": 0,
                        "flanking_damage_bonus": flanking_damage_bonus,
                        "damage_dealt": damage_dealt,
                        "effect_d20_raw": 12 if weapon_effect else None,
                        "effect_dc": 12,
                        "effect_eligible": effect_eligible,
                        "effect_applied": weapon_effect if effect_eligible else None,
                    },
                )

    def test_live_personal_attack_uses_attack_and_damage_components(self):
        result = _resolve_live_personal_attack(
            player_modifier=2,
            enemy_dc=15,
            attack_d20_raw=13,
            damage_d4_raw=3,
            weapon_damage_bonus=4,
            fixed_damage_bonus=5,
            melee_damage_bonus=6,
            position="FLANQUEANDO",
            weapon_effect="queimadura",
            weapon_effect_dc=17,
            effect_d20_raw=17,
            attack_bonus=2,
            attack_penalty=-1,
        )

        self.assertEqual(result["total_attack"], 16)
        self.assertEqual(result["outcome"], "SUCESSO")
        self.assertEqual(result["effective_d4_damage"], 3)
        self.assertEqual(result["weapon_bonus"], 4)
        self.assertEqual(result["fixed_damage_bonus"], 5)
        self.assertEqual(result["melee_damage_bonus"], 6)
        self.assertEqual(result["flanking_damage_bonus"], 2)
        self.assertEqual(result["damage_dealt"], 20)
        self.assertTrue(result["effect_eligible"])
        self.assertEqual(result["effect_applied"], "queimadura")

    def test_live_personal_attack_preserves_naturals_and_effect_eligibility(self):
        ordinary_failure = _resolve_live_personal_attack(
            0, 15, 14, None, weapon_effect="atordoamento", effect_d20_raw=20
        )
        natural_one = _resolve_live_personal_attack(
            100, -10, 1, None, weapon_effect="atordoamento", effect_d20_raw=20
        )
        critical = _resolve_live_personal_attack(
            -100,
            30,
            20,
            3,
            weapon_damage_bonus=2,
            weapon_effect="atordoamento",
            weapon_effect_dc=20,
            effect_d20_raw=1,
        )
        effect_refused = _resolve_live_personal_attack(
            0,
            10,
            10,
            2,
            weapon_effect="atordoamento",
            weapon_effect_dc=12,
            effect_d20_raw=11,
        )

        self.assertEqual(ordinary_failure["outcome"], "FALHA")
        self.assertFalse(ordinary_failure["requires_damage_roll"])
        self.assertFalse(ordinary_failure["requires_effect_roll"])
        self.assertEqual(ordinary_failure["damage_dealt"], 0)
        self.assertIsNone(ordinary_failure["effect_applied"])
        self.assertEqual(natural_one["outcome"], "FALHA CRÍTICA")
        self.assertEqual(natural_one["damage_dealt"], 0)
        self.assertEqual(critical["outcome"], "SUCESSO CRÍTICO")
        self.assertEqual(critical["effective_d4_damage"], 6)
        self.assertEqual(critical["damage_dealt"], 8)
        self.assertEqual(critical["effect_applied"], "atordoamento")
        self.assertFalse(effect_refused["effect_eligible"])
        self.assertIsNone(effect_refused["effect_applied"])

    def test_live_personal_attack_rejects_missing_required_success_rolls(self):
        with self.assertRaisesRegex(ValueError, "damage_d4_raw"):
            _resolve_live_personal_attack(0, 10, 10, None)

        with self.assertRaisesRegex(ValueError, "effect_d20_raw"):
            _resolve_live_personal_attack(
                0, 10, 10, 1, weapon_effect="atordoamento"
            )

        with self.assertRaisesRegex(ValueError, "effect_d20_raw"):
            _resolve_live_personal_attack(
                -100, 30, 20, 1, weapon_effect="atordoamento"
            )

    def test_live_personal_attack_failure_accepts_missing_rolls(self):
        result = _resolve_live_personal_attack(
            0,
            15,
            14,
            None,
            weapon_effect="atordoamento",
            effect_d20_raw=None,
        )

        self.assertEqual(result["outcome"], "FALHA")
        self.assertEqual(result["damage_dealt"], 0)
        self.assertIsNone(result["effect_applied"])

    def test_live_and_legacy_effect_policies_differ_at_zero_damage(self):
        weapon = {"damage_bonus": 0, "effect": "atordoamento", "effect_dc": 12}
        live_result = _resolve_live_personal_attack(
            player_modifier=0,
            enemy_dc=10,
            attack_d20_raw=10,
            damage_d4_raw=0,
            weapon_damage_bonus=0,
            weapon_effect="atordoamento",
            weapon_effect_dc=12,
            effect_d20_raw=12,
        )
        legacy_result = combat.resolve_personal_combat(
            player_attr=0,
            enemy_dc=10,
            enemy_damage=0,
            attack_d20_raw=10,
            damage_d4_raw=0,
            armor_reduction=0,
            weapon_definition=weapon,
            effect_d20_raw=12,
        )

        self.assertEqual(live_result["outcome"], "SUCESSO")
        self.assertEqual(live_result["damage_dealt"], 0)
        self.assertTrue(live_result["effect_eligible"])
        self.assertEqual(live_result["effect_applied"], "atordoamento")
        self.assertEqual(legacy_result["check_result"], "SUCESSO")
        self.assertEqual(legacy_result["damage_dealt"], 0)
        self.assertIsNone(legacy_result["effect_applied"])

    def test_personal_success_preserves_damage_armor_effect_and_order(self):
        weapon = {"damage_bonus": 1, "effect": "sangramento", "effect_dc": 13}

        result = combat.resolve_personal_combat(
            player_attr=3,
            enemy_dc=15,
            enemy_damage=7,
            attack_d20_raw=12,
            damage_d4_raw=4,
            armor_reduction=2,
            weapon_definition=weapon,
            effect_d20_raw=13,
        )

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(
            result,
            {
                "d20_raw": 12,
                "total_attack": 15,
                "check_result": "SUCESSO",
                "is_critical": False,
                "d4_raw": 4,
                "weapon_bonus": 1,
                "damage_dealt": 5,
                "damage_reduction": 2,
                "damage_taken": 5,
                "effect_applied": "sangramento",
            },
        )

    def test_personal_failure_and_natural_one_do_not_deal_damage(self):
        weapon = {"damage_bonus": 1, "effect": "sangramento", "effect_dc": 13}

        ordinary_failure = combat.resolve_personal_combat(
            player_attr=0,
            enemy_dc=15,
            enemy_damage=1,
            attack_d20_raw=14,
            damage_d4_raw=4,
            armor_reduction=2,
            weapon_definition=weapon,
            effect_d20_raw=20,
        )
        natural_one = combat.resolve_personal_combat(
            player_attr=100,
            enemy_dc=-10,
            enemy_damage=99,
            attack_d20_raw=1,
            damage_d4_raw=4,
            armor_reduction=0,
            weapon_definition=weapon,
            effect_d20_raw=20,
        )

        self.assertEqual(ordinary_failure["check_result"], "FALHA")
        self.assertEqual(ordinary_failure["damage_dealt"], 0)
        self.assertEqual(ordinary_failure["damage_taken"], 0)
        self.assertIsNone(ordinary_failure["effect_applied"])
        self.assertEqual(natural_one["check_result"], "FALHA_CRITICA")
        self.assertFalse(natural_one["is_critical"])
        self.assertEqual(natural_one["damage_dealt"], 0)

    def test_personal_natural_twenty_doubles_only_the_d4_and_can_apply_effect(self):
        weapon = {"damage_bonus": 2, "effect": "queimadura", "effect_dc": 14}

        result = combat.resolve_personal_combat(
            player_attr=-100,
            enemy_dc=30,
            enemy_damage=6,
            attack_d20_raw=20,
            damage_d4_raw=3,
            armor_reduction=0,
            weapon_definition=weapon,
            effect_d20_raw=1,
        )

        self.assertEqual(result["check_result"], "SUCESSO_CRITICO")
        self.assertTrue(result["is_critical"])
        self.assertEqual(result["damage_dealt"], 8)
        self.assertEqual(result["weapon_bonus"], 2)
        self.assertEqual(result["effect_applied"], "queimadura")

    def test_effect_threshold_is_inclusive_and_below_threshold_is_refused(self):
        weapon = {"damage_bonus": 0, "effect": "atordoamento", "effect_dc": 12}
        at_threshold = combat.resolve_personal_combat(
            0, 10, 0, 10, 1, 0, weapon, effect_d20_raw=12
        )
        below_threshold = combat.resolve_personal_combat(
            0, 10, 0, 10, 1, 0, weapon, effect_d20_raw=11
        )

        self.assertEqual(at_threshold["check_result"], "SUCESSO")
        self.assertEqual(at_threshold["effect_applied"], "atordoamento")
        self.assertIsNone(below_threshold["effect_applied"])

    def test_effect_requires_a_roll_even_for_a_critical_hit(self):
        weapon = {"damage_bonus": 0, "effect": "queimadura", "effect_dc": 20}
        result = combat.resolve_personal_combat(
            -100, 30, 0, 20, 2, 0, weapon, effect_d20_raw=None
        )

        self.assertEqual(result["check_result"], "SUCESSO_CRITICO")
        self.assertEqual(result["damage_dealt"], 4)
        self.assertIsNone(result["effect_applied"])

    def test_stunned_enemy_takes_no_return_damage(self):
        result = combat.resolve_personal_combat(
            0,
            10,
            99,
            10,
            2,
            4,
            {},
            enemy_is_stunned=True,
        )

        self.assertEqual(result["damage_dealt"], 2)
        self.assertEqual(result["damage_reduction"], 4)
        self.assertEqual(result["damage_taken"], 0)

    def test_enemy_damage_reduction_multiplier_and_ordinary_return_contract(self):
        cases = (
            ((7, 0, 0, False), 7),
            ((7, 2, 0, False), 5),
            ((7, 0, 3, False), 4),
            ((7, 2, 3, False), 2),
            ((5, 2, 3, False), 0),
            ((2, 5, 3, False), 0),
            ((7, 2, 1, True), 6),
            ((5, 0, 0, True), 7),
        )

        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(combat.resolve_enemy_damage(*inputs), expected)

        class ReducedDamage(int):
            def __sub__(self, other):
                return ReducedDamage(super().__sub__(other))

            def __int__(self):
                raise AssertionError("ordinary enemy damage must not be coerced")

            def __mul__(self, other):
                raise AssertionError("ordinary enemy damage must not be multiplied")

        result = combat.resolve_enemy_damage(ReducedDamage(7), 0, 0, False)
        self.assertIsInstance(result, ReducedDamage)
        self.assertEqual(result, 7)

    def test_legacy_personal_combat_delegates_enemy_damage_without_contract_drift(self):
        expected_signature = [
            "player_attr",
            "enemy_dc",
            "enemy_damage",
            "attack_d20_raw",
            "damage_d4_raw",
            "armor_reduction",
            "weapon_definition",
            "enemy_is_stunned",
            "effect_d20_raw",
        ]
        self.assertEqual(list(inspect.signature(combat.resolve_personal_combat).parameters), expected_signature)

        with mock.patch.object(combat, "resolve_enemy_damage", return_value=6) as resolve_enemy_damage:
            result = combat.resolve_personal_combat(0, 10, 9, 10, 2, 3, {})

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(result["damage_taken"], 6)
        resolve_enemy_damage.assert_called_once_with(
            raw_damage=9,
            armor_reduction=3,
            passive_reduction=0,
            enemy_acted_first=False,
        )

        with mock.patch.object(combat, "resolve_enemy_damage") as resolve_enemy_damage:
            stunned = combat.resolve_personal_combat(0, 10, 9, 10, 2, 3, {}, enemy_is_stunned=True)

        self.assertEqual(list(stunned), PERSONAL_RESULT_KEYS)
        self.assertEqual(stunned["damage_taken"], 0)
        resolve_enemy_damage.assert_not_called()

    def test_armor_reduction_uses_only_explicit_data(self):
        self.assertEqual(combat.get_armor_reduction(None, None), 0)
        self.assertEqual(
            combat.get_armor_reduction("Armadura de Couro", {"damage_reduction": 7}),
            7,
        )
        self.assertEqual(
            combat.get_armor_reduction("Armadura Não Catalogada", None),
            combat.ARMOR_DAMAGE_REDUCTION,
        )
        self.assertEqual(
            combat.get_armor_reduction("Armadura Incompleta", {}),
            combat.ARMOR_DAMAGE_REDUCTION,
        )

    def test_ship_combat_preserves_shields_hull_failure_and_naturals(self):
        cases = (
            (
                (3, 15, 8, 12),
                {
                    "d20_raw": 12,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    "shield_damage": 15,
                    "hull_damage": 0,
                },
            ),
            (
                (3, 15, 0, 12),
                {
                    "d20_raw": 12,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    "shield_damage": 0,
                    "hull_damage": 10,
                },
            ),
            (
                (0, 15, 8, 14),
                {
                    "d20_raw": 14,
                    "total_attack": 14,
                    "check_result": "FALHA",
                    "shield_damage": 0,
                    "hull_damage": 0,
                },
            ),
            (
                (100, -10, 8, 1),
                {
                    "d20_raw": 1,
                    "total_attack": 101,
                    "check_result": "FALHA_CRITICA",
                    "shield_damage": 0,
                    "hull_damage": 0,
                },
            ),
            (
                (-100, 30, 8, 20),
                {
                    "d20_raw": 20,
                    "total_attack": -80,
                    "check_result": "SUCESSO_CRITICO",
                    "shield_damage": 15,
                    "hull_damage": 0,
                },
            ),
        )

        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                result = combat.resolve_ship_combat(*inputs)
                self.assertEqual(list(result), SHIP_RESULT_KEYS)
                self.assertEqual(result, expected)

    def test_domain_uses_resolution_module_for_natural_outcomes(self):
        with mock.patch.object(
            resolution, "resolve_check", wraps=resolution.resolve_check
        ) as resolve_check:
            result = combat.resolve_ship_combat(0, 10, 0, 20)

        self.assertEqual(result["check_result"], "SUCESSO_CRITICO")
        resolve_check.assert_called_once_with(0, 10, 20)


class CombatAdapterTests(unittest.TestCase):
    def test_armor_adapter_resolves_registry_then_delegates(self):
        armor = mechanics_engine.ARMOR_REGISTRY["Armadura de Couro"]
        with mock.patch.object(
            combat, "get_armor_reduction", wraps=combat.get_armor_reduction
        ) as domain_get_armor:
            result = mechanics_engine.get_armor_reduction("Armadura de Couro")

        self.assertEqual(result, 2)
        domain_get_armor.assert_called_once_with("Armadura de Couro", armor)

    def test_personal_adapter_resolves_content_then_delegates(self):
        weapon = mechanics_engine.WEAPON_REGISTRY["Lança Primitiva"]
        with mock.patch.object(
            combat,
            "resolve_personal_combat",
            wraps=combat.resolve_personal_combat,
        ) as domain_resolve:
            result = mechanics_engine.resolve_personal_combat(
                player_attr=3,
                enemy_dc=15,
                enemy_damage=7,
                attack_d20_raw=12,
                damage_d4_raw=4,
                armor_name="Armadura de Couro",
                weapon_name="Lança Primitiva",
                effect_d20_raw=13,
            )

        self.assertEqual(result["damage_dealt"], 5)
        self.assertEqual(domain_resolve.call_count, 1)
        forwarded = domain_resolve.call_args.kwargs
        self.assertEqual(forwarded["armor_reduction"], 2)
        self.assertIs(forwarded["weapon_definition"], weapon)

    def test_ship_adapter_delegates_without_content_lookup(self):
        with mock.patch.object(
            combat, "resolve_ship_combat", wraps=combat.resolve_ship_combat
        ) as domain_resolve:
            result = mechanics_engine.resolve_ship_combat(3, 15, 8, 12)

        self.assertEqual(result["shield_damage"], 15)
        domain_resolve.assert_called_once_with(
            player_piloting=3,
            enemy_ac=15,
            enemy_shields=8,
            d20_raw=12,
        )

    def test_legacy_public_signatures_remain_unchanged(self):
        armor_signature = inspect.signature(mechanics_engine.get_armor_reduction)
        self.assertEqual(list(armor_signature.parameters), ["armor_name"])
        self.assertIs(
            armor_signature.parameters["armor_name"].default,
            inspect.Parameter.empty,
        )

        personal_signature = inspect.signature(mechanics_engine.resolve_personal_combat)
        self.assertEqual(
            list(personal_signature.parameters),
            [
                "player_attr",
                "enemy_dc",
                "enemy_damage",
                "attack_d20_raw",
                "damage_d4_raw",
                "armor_name",
                "weapon_name",
                "enemy_is_stunned",
                "effect_d20_raw",
            ],
        )
        self.assertEqual(
            [personal_signature.parameters[name].default for name in list(personal_signature.parameters)[5:]],
            [None, None, False, None],
        )

        ship_signature = inspect.signature(mechanics_engine.resolve_ship_combat)
        self.assertEqual(
            list(ship_signature.parameters),
            ["player_piloting", "enemy_ac", "enemy_shields", "d20_raw"],
        )


class CombatArchitectureTests(unittest.TestCase):
    def test_personal_resolvers_share_the_private_check_and_attack_core(self):
        with (
            mock.patch.object(
                combat,
                "_resolve_personal_check",
                wraps=combat._resolve_personal_check,
            ) as resolve_check,
            mock.patch.object(
                combat,
                "_resolve_personal_attack_core",
                wraps=combat._resolve_personal_attack_core,
            ) as resolve_core,
        ):
            live_result = _resolve_live_personal_attack(
                player_modifier=2,
                enemy_dc=15,
                attack_d20_raw=13,
                damage_d4_raw=3,
                weapon_damage_bonus=2,
                weapon_effect="queimadura",
                weapon_effect_dc=14,
                effect_d20_raw=14,
                attack_bonus=1,
            )
            legacy_result = combat.resolve_personal_combat(
                player_attr=3,
                enemy_dc=15,
                enemy_damage=7,
                attack_d20_raw=12,
                damage_d4_raw=4,
                armor_reduction=2,
                weapon_definition={
                    "damage_bonus": 1,
                    "effect": "sangramento",
                    "effect_dc": 13,
                },
                effect_d20_raw=13,
            )

        self.assertEqual(live_result["damage_dealt"], 5)
        self.assertEqual(live_result["effect_applied"], "queimadura")
        self.assertEqual(legacy_result["damage_dealt"], 5)
        self.assertEqual(legacy_result["effect_applied"], "sangramento")
        self.assertEqual(resolve_check.call_count, 2)
        self.assertEqual(resolve_core.call_count, 2)

    def test_public_personal_resolvers_have_no_duplicate_rule_formulas(self):
        source_path = ROOT / "chronos" / "domain" / "combat.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

        direct_resolution_callers = {
            name
            for name, function in functions.items()
            if any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "resolution"
                and call.func.attr == "resolve_check"
                for call in ast.walk(function)
            )
        }
        self.assertIn("_resolve_personal_check", direct_resolution_callers)
        self.assertNotIn("prepare_personal_attack", direct_resolution_callers)
        self.assertNotIn("resolve_personal_attack", direct_resolution_callers)
        self.assertNotIn("resolve_personal_combat", direct_resolution_callers)

        for name in ("resolve_personal_attack", "resolve_personal_combat"):
            function_source = ast.get_source_segment(source, functions[name])
            self.assertNotIn("damage_d4_raw *", function_source)
            self.assertNotIn("effect_d20_raw >=", function_source)

        live_signature = inspect.signature(combat.resolve_personal_attack)
        self.assertEqual(
            list(live_signature.parameters),
            [
                "preparation",
                "damage_d4_raw",
                "weapon_damage_bonus",
                "fixed_damage_bonus",
                "melee_damage_bonus",
                "position",
                "weapon_effect",
                "weapon_effect_dc",
                "effect_d20_raw",
            ],
        )

        live_calls = [
            call
            for call in ast.walk(functions["resolve_personal_attack"])
            if isinstance(call, ast.Call)
        ]
        self.assertFalse(
            any(
                isinstance(call.func, ast.Name)
                and call.func.id in {"prepare_personal_attack", "_resolve_personal_check"}
                for call in live_calls
            )
        )
        self.assertFalse(
            any(
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "resolution"
                and call.func.attr == "resolve_check"
                for call in live_calls
            )
        )

    def test_domain_module_has_no_external_io_or_registry_dependencies(self):
        mechanics_source = ROOT / "skills" / "mechanics_engine.py"
        mechanics_tree = ast.parse(mechanics_source.read_text(encoding="utf-8"))
        expected_aliases = {
            "ARMOR_DAMAGE_REDUCTION": "ARMOR_DAMAGE_REDUCTION",
            "SHIP_DAMAGE_ON_SHIELDS": "SHIP_DAMAGE_ON_SHIELDS",
            "SHIP_DAMAGE_ON_HULL": "SHIP_DAMAGE_ON_HULL",
            "FLANQUEAR_DAMAGE_BONUS": "FLANQUEAR_DAMAGE_BONUS",
        }
        alias_assignments = {name: [] for name in expected_aliases}
        for node in ast.walk(mechanics_tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in alias_assignments:
                    alias_assignments[target.id].append(node.value)

        for name, domain_name in expected_aliases.items():
            self.assertEqual(len(alias_assignments[name]), 1)
            value = alias_assignments[name][0]
            self.assertIsInstance(value, ast.Attribute)
            self.assertIsInstance(value.value, ast.Name)
            self.assertEqual(value.value.id, "_combat")
            self.assertEqual(value.attr, domain_name)

        source_path = ROOT / "chronos" / "domain" / "combat.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        approved_imports = {"collections.abc", "typing", "chronos.domain"}
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)

        self.assertEqual(set(imported_modules), approved_imports)

        forbidden_call_parts = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
            "os",
            "environ",
            "env",
            "getenv",
            "subprocess",
            "requests",
            "urllib",
            "http",
            "socket",
            "network",
            "pathlib",
            "read",
            "read_text",
            "read_bytes",
            "write",
            "write_text",
            "write_bytes",
            "save",
            "load",
            "dump",
            "persist",
            "repository",
            "storage",
            "database",
            "sqlite",
            "connect",
            "request",
            "urlopen",
            "run",
            "call",
            "check_call",
            "check_output",
            "commit",
            "insert",
            "update",
            "delete",
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                call_parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                call_parts.append(current.id)
            self.assertTrue(call_parts)
            self.assertFalse(
                any(part in forbidden_call_parts for part in call_parts),
                msg=f"forbidden domain call: {'.'.join(reversed(call_parts))}",
            )

        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        self.assertFalse(any("REGISTRY" in name.upper() for name in names | attributes))
        self.assertFalse(any("CURRENT_STATE" in name.upper() for name in names | attributes))


if __name__ == "__main__":
    unittest.main()
