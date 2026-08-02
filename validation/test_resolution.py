"""Independent regression coverage for the extracted resolution domain."""

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

import mechanics_engine
from chronos.domain import dice, resolution


class ResolutionTests(unittest.TestCase):
    def test_calc_modifier_matches_legacy_formula_and_adapters(self):
        expected = {-7: -17, 0: -10, 10: 0, 17: 7, 25: 15}

        for attribute_value, modifier in expected.items():
            with self.subTest(attribute_value=attribute_value):
                self.assertEqual(resolution.calc_modifier(attribute_value), modifier)
                self.assertEqual(dice.calc_modifier(attribute_value), modifier)
                self.assertEqual(
                    mechanics_engine.calc_modifier(attribute_value), modifier
                )

    def test_resolve_check_uses_legacy_total_and_boundary_oracle(self):
        cases = (
            (3, 15, 12, 15, "SUCESSO"),
            (1, 15, 10, 11, "FALHA"),
            (0, 0, 2, 2, "SUCESSO"),
            (-5, 10, 14, 9, "FALHA"),
            (0, -3, 2, 2, "SUCESSO"),
            (5, 10, 5, 10, "SUCESSO"),
        )

        for modifier, dc, d20_raw, total, outcome in cases:
            with self.subTest(modifier=modifier, dc=dc, d20_raw=d20_raw):
                expected = {
                    "d20_raw": d20_raw,
                    "total": total,
                    "dc": dc,
                    "result": outcome,
                }
                self.assertEqual(resolution.resolve_check(modifier, dc, d20_raw), expected)
                self.assertEqual(mechanics_engine.resolve_check(modifier, dc, d20_raw), expected)

    def test_resolve_check_natural_rolls_override_totals(self):
        self.assertEqual(
            resolution.resolve_check(-100, 30, 20),
            {
                "d20_raw": 20,
                "total": -80,
                "dc": 30,
                "result": "SUCESSO_CRITICO",
            },
        )
        self.assertEqual(
            resolution.resolve_check(100, -10, 1),
            {
                "d20_raw": 1,
                "total": 101,
                "dc": -10,
                "result": "FALHA_CRITICA",
            },
        )

    def test_resolve_check_preserves_exact_keys_and_result_vocabulary(self):
        outcomes = (
            resolution.resolve_check(0, 10, 20),
            resolution.resolve_check(0, 10, 1),
            resolution.resolve_check(0, 10, 10),
            resolution.resolve_check(0, 10, 9),
        )
        expected_keys = ["d20_raw", "total", "dc", "result"]
        expected_results = {
            "SUCESSO_CRITICO",
            "SUCESSO",
            "FALHA",
            "FALHA_CRITICA",
        }

        self.assertEqual({entry["result"] for entry in outcomes}, expected_results)
        for entry in outcomes:
            self.assertEqual(list(entry), expected_keys)

    def test_adapters_delegate_to_resolution_domain(self):
        with mock.patch.object(
            resolution, "resolve_check", wraps=resolution.resolve_check
        ) as domain_resolve:
            expected = mechanics_engine.resolve_check(2, 12, 10)
        self.assertEqual(expected, {"d20_raw": 10, "total": 12, "dc": 12, "result": "SUCESSO"})
        domain_resolve.assert_called_once_with(2, 12, 10)

        with mock.patch.object(
            resolution, "calc_modifier", wraps=resolution.calc_modifier
        ) as domain_modifier:
            self.assertEqual(mechanics_engine.calc_modifier(13), 3)
        domain_modifier.assert_called_once_with(13)

    def test_dice_modifier_is_a_direct_domain_reexport(self):
        self.assertIs(dice.calc_modifier, resolution.calc_modifier)
        self.assertNotIn("attribute_value - 10", inspect.getsource(dice))

    def test_personal_combat_preserves_exact_resolution_consumer_output(self):
        self.assertEqual(
            mechanics_engine.resolve_personal_combat(
                player_attr=3,
                enemy_dc=15,
                enemy_damage=7,
                attack_d20_raw=12,
                damage_d4_raw=4,
            ),
            {
                "d20_raw": 12,
                "total_attack": 15,
                "check_result": "SUCESSO",
                "is_critical": False,
                "d4_raw": 4,
                "weapon_bonus": 0,
                "damage_dealt": 4,
                "damage_reduction": 0,
                "damage_taken": 7,
                "effect_applied": None,
            },
        )

    def test_ship_combat_preserves_exact_resolution_consumer_output(self):
        self.assertEqual(
            mechanics_engine.resolve_ship_combat(
                player_piloting=-2,
                enemy_ac=15,
                enemy_shields=20,
                d20_raw=17,
            ),
            {
                "d20_raw": 17,
                "total_attack": 15,
                "check_result": "SUCESSO",
                "shield_damage": 15,
                "hull_damage": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
