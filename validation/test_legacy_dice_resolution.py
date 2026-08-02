"""Stage 1A characterization tests for the current legacy dice contracts.

These tests intentionally freeze behavior that diverges from the canonical GDD:

* modifiers currently use ``attribute - 10`` instead of
  ``floor((effective attribute - 10) / 2)``;
* natural 20 and natural 1 are automatic critical outcomes, regardless of the
  total, instead of changing only one degree when the total permits it; and
* d20/d4 use ``secrets.choice`` without a seed or injected source, so tests
  control the existing lowest randomness boundary rather than expecting
  reproducible runtime randomness.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

import d20
import d4
import mechanics_engine
import multi_roll
from chronos.domain import dice


class LegacyDiceResolutionTests(unittest.TestCase):
    def test_legacy_d20_uses_inclusive_low_and_high_bounds_at_choice_boundary(self):
        """The legacy d20 passes range(1, 21), including both endpoints."""
        with mock.patch.object(d20.secrets, "choice", side_effect=[1, 20]) as choice:
            self.assertEqual(d20.rolar_d20(), 1)
            self.assertEqual(d20.rolar_d20(), 20)

        self.assertEqual(
            choice.call_args_list,
            [mock.call(range(1, 21)), mock.call(range(1, 21))],
        )

    def test_legacy_d4_uses_inclusive_low_and_high_bounds_at_choice_boundary(self):
        """The legacy d4 passes range(1, 5), including both endpoints."""
        with mock.patch.object(d4.secrets, "choice", side_effect=[1, 4]) as choice:
            self.assertEqual(d4.rolar_d4(), 1)
            self.assertEqual(d4.rolar_d4(), 4)

        self.assertEqual(
            choice.call_args_list,
            [mock.call(range(1, 5)), mock.call(range(1, 5))],
        )

    def test_legacy_multi_roll_selects_best_worst_and_single_results(self):
        """The four-field tuple preserves each current selection criterion."""
        cases = (
            (20, 10, [4, 17], ([4, 17], 17, "MELHOR", "")),
            (20, 6, [4, 17], ([4, 17], 4, "PIOR", "(-4)")),
            (4, 8, [3], ([3], 3, "ÚNICO", "(-2)")),
        )

        for faces, attr_value, rolls, expected in cases:
            with self.subTest(faces=faces, attr_value=attr_value):
                dice = multi_roll._d20 if faces == 20 else multi_roll._d4
                with mock.patch.object(
                    dice,
                    "rolar_d20" if faces == 20 else "rolar_d4",
                    side_effect=rolls,
                ) as roll:
                    actual = multi_roll.do_multi_roll(faces, attr_value)

                self.assertEqual(actual, expected)
                self.assertEqual(roll.call_count, len(rolls))

    def test_legacy_multi_roll_clamps_attribute_below_one(self):
        """Below-range values use the attribute-1 legacy table entry."""
        rolls = [4, 3, 2, 1, 2]
        with mock.patch.object(
            multi_roll._d4, "rolar_d4", side_effect=rolls
        ) as roll:
            actual = multi_roll.do_multi_roll(4, -100)

        self.assertEqual(actual, ([4, 3, 2, 1, 2], 1, "PIOR", "(-9)"))
        self.assertEqual(roll.call_count, 5)

    def test_legacy_multi_roll_clamps_attribute_above_twenty(self):
        """Above-range values use the attribute-20 legacy table entry."""
        rolls = [1, 2, 3, 4, 1, 2, 3]
        with mock.patch.object(
            multi_roll._d4, "rolar_d4", side_effect=rolls
        ) as roll:
            actual = multi_roll.do_multi_roll(4, 100)

        self.assertEqual(actual, ([1, 2, 3, 4, 1, 2, 3], 4, "MELHOR", "(+10)"))
        self.assertEqual(roll.call_count, 7)

    def test_legacy_roll_tables_preserve_all_entries_and_criterion_spelling(self):
        """The duplicated tables preserve current criterion spelling, casing, and accentuation."""
        expected_multi_roll = {
            1: (5, "pior"),
            2: (4, "pior"),
            3: (4, "pior"),
            4: (3, "pior"),
            5: (3, "pior"),
            6: (2, "pior"),
            7: (2, "pior"),
            8: (1, "unico"),
            9: (1, "unico"),
            10: (2, "melhor"),
            11: (2, "melhor"),
            12: (3, "melhor"),
            13: (3, "melhor"),
            14: (4, "melhor"),
            15: (4, "melhor"),
            16: (5, "melhor"),
            17: (5, "melhor"),
            18: (6, "melhor"),
            19: (6, "melhor"),
            20: (7, "melhor"),
        }
        expected_mechanics = {
            1: (5, "PIOR"),
            2: (4, "PIOR"),
            3: (4, "PIOR"),
            4: (3, "PIOR"),
            5: (3, "PIOR"),
            6: (2, "PIOR"),
            7: (2, "PIOR"),
            8: (1, "ÚNICO"),
            9: (1, "ÚNICO"),
            10: (2, "MELHOR"),
            11: (2, "MELHOR"),
            12: (3, "MELHOR"),
            13: (3, "MELHOR"),
            14: (4, "MELHOR"),
            15: (4, "MELHOR"),
            16: (5, "MELHOR"),
            17: (5, "MELHOR"),
            18: (6, "MELHOR"),
            19: (6, "MELHOR"),
            20: (7, "MELHOR"),
        }

        self.assertEqual(multi_roll.ROLL_TABLE, expected_multi_roll)
        self.assertEqual(mechanics_engine.ROLL_TABLE, expected_mechanics)

    def test_legacy_modifiers_are_attribute_minus_ten(self):
        """The current modifier remains attr-10, not the canonical GDD formula."""
        expected = {1: -9, 7: -3, 10: 0, 13: 3, 20: 10}

        for attr_value, modifier in expected.items():
            with self.subTest(attr_value=attr_value):
                self.assertEqual(multi_roll._calc_mod(attr_value), modifier)
                self.assertEqual(
                    mechanics_engine.calc_modifier(attr_value), modifier
                )

    def test_legacy_table_and_modifier_parity_for_representative_attributes(self):
        """Both legacy implementations agree on counts, labels, and modifiers."""
        expected = {
            1: (5, "pior", "PIOR", -9),
            8: (1, "unico", "ÚNICO", -2),
            10: (2, "melhor", "MELHOR", 0),
            20: (7, "melhor", "MELHOR", 10),
        }

        for attr_value, (count, multi_criterion, mechanics_criterion, modifier) in expected.items():
            with self.subTest(attr_value=attr_value):
                self.assertEqual(
                    multi_roll.ROLL_TABLE[attr_value],
                    (count, multi_criterion),
                )
                self.assertEqual(
                    mechanics_engine.ROLL_TABLE[attr_value],
                    (count, mechanics_criterion),
                )
                self.assertEqual(multi_roll._calc_mod(attr_value), modifier)
                self.assertEqual(mechanics_engine.calc_modifier(attr_value), modifier)

    def test_legacy_resolve_check_returns_exact_success_and_failure_records(self):
        """Ordinary checks preserve the exact four-key result dictionary."""
        self.assertEqual(
            mechanics_engine.resolve_check(modifier=3, dc=15, d20_raw=12),
            {"d20_raw": 12, "total": 15, "dc": 15, "result": "SUCESSO"},
        )
        self.assertEqual(
            mechanics_engine.resolve_check(modifier=1, dc=15, d20_raw=10),
            {"d20_raw": 10, "total": 11, "dc": 15, "result": "FALHA"},
        )

    def test_legacy_resolve_check_natural_twenty_and_one_override_total(self):
        """Legacy natural-roll handling forces critical outcomes regardless of total."""
        self.assertEqual(
            mechanics_engine.resolve_check(modifier=-100, dc=30, d20_raw=20),
            {
                "d20_raw": 20,
                "total": -80,
                "dc": 30,
                "result": "SUCESSO_CRITICO",
            },
        )
        self.assertEqual(
            mechanics_engine.resolve_check(modifier=100, dc=-10, d20_raw=1),
            {
                "d20_raw": 1,
                "total": 101,
                "dc": -10,
                "result": "FALHA_CRITICA",
            },
        )

    def test_domain_dice_accept_a_controlled_choice_callable(self):
        """The pure domain keeps its random source injectable for deterministic tests."""
        choices = []

        def choose_highest(values):
            choices.append(values)
            return values.stop - 1

        self.assertEqual(dice.roll_d20(choice=choose_highest), 20)
        self.assertEqual(dice.roll_d4(choice=choose_highest), 4)
        self.assertEqual(choices, [range(1, 21), range(1, 5)])

    def test_domain_multi_roll_accepts_a_controlled_roller(self):
        """The domain receives rolls through a minimal callable seam."""
        calls = []

        def controlled_roller(faces, count):
            calls.append((faces, count))
            return [4, 17]

        self.assertEqual(
            dice.multi_roll(20, 10, roller=controlled_roller),
            ([4, 17], 17, "MELHOR", ""),
        )
        self.assertEqual(calls, [(20, 2)])

    def test_domain_rules_match_both_legacy_table_projections(self):
        """Normalized domain rules preserve both public legacy table spellings."""
        for attribute in range(1, 21):
            with self.subTest(attribute=attribute):
                count, criterion = dice.multi_roll_rule(attribute)
                self.assertEqual(multi_roll.ROLL_TABLE[attribute], (count, criterion))
                self.assertEqual(
                    mechanics_engine.ROLL_TABLE[attribute],
                    (count, dice.criterion_label(criterion)),
                )

    def test_legacy_adapters_delegate_to_the_domain(self):
        """Adapters retain their public functions while routing policy to the domain."""
        with mock.patch.object(d20._dice, "roll_d20", return_value=20) as roll_d20:
            self.assertEqual(d20.rolar_d20(), 20)
        roll_d20.assert_called_once_with(choice=d20.secrets.choice)

        with mock.patch.object(d4._dice, "roll_d4", return_value=4) as roll_d4:
            self.assertEqual(d4.rolar_d4(), 4)
        roll_d4.assert_called_once_with(choice=d4.secrets.choice)

        expected = ([4, 17], 17, "MELHOR", "")
        with mock.patch.object(
            multi_roll._dice, "multi_roll", return_value=expected
        ) as roll_multi:
            self.assertEqual(multi_roll.do_multi_roll(20, 10), expected)
        roll_multi.assert_called_once_with(20, 10, roller=multi_roll.rolar)

        with mock.patch.object(
            mechanics_engine._dice, "calc_modifier", return_value=99
        ) as modifier:
            self.assertEqual(mechanics_engine.calc_modifier(10), 99)
        modifier.assert_called_once_with(10)

        import system_engine

        with mock.patch.object(
            system_engine._me, "calc_modifier", return_value=-99
        ) as system_modifier:
            self.assertEqual(system_engine._mod(10), -99)
        system_modifier.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
