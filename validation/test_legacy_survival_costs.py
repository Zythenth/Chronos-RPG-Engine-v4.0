"""Characterization tests for the current legacy survival-cost contracts."""

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

import mechanics_engine
import system_engine


EXPECTED_BASAL_COST = {
    "A_selva": {
        "energy_reserves": -2,
        "oxygen_level": 0,
        "hp_passive": 0,
    },
    "B_cidade": {
        "energy_reserves": -1,
        "oxygen_level": 0,
        "hp_passive": 0,
    },
    "C_nave": {
        "energy_reserves": -1,
        "oxygen_level": -1,
    },
    "D_eva": {
        "oxygen_level": -5,
        "energy_reserves": -2,
    },
    "E_planeta": {
        "energy_reserves": -2,
    },
}

EXPECTED_PLANET_EXTRA_COST = {
    "mundo_corrosivo": {"suit_integrity": -2},
    "abismo_oceanico": {"hull_integrity": -3},
    "deserto_de_vidro": {},
    "cemiterio_silicio": {},
    "gigante_gasoso": {"fuel_cells": -1},
    "mundo_simbiotico": {"hp_passive": -2},
    "orbe_estilhacado": {},
    "mundo_orfao": {"hp_passive": -3},
    "horizonte_eventos": {"energy_reserves": -1},
    "paraiso_artificial": {"suit_integrity": -5, "hp_passive": -1},
}

EXPECTED_ACTION_COST = {
    "explorar_area": {"energy_reserves": -3},
    "usar_chip": {"energy_reserves": -5},
    "scan": {"energy_reserves": -5},
    "primeiros_socorros": {},
    "combate": {},
    "scan_setor": {"energy_reserves": -5},
    "salto_decolagem": {"fuel_cells": -1},
    "pouso_atmosferico": {"fuel_cells": -2},
    "recarregar_sistemas": {"energy_reserves": -10},
    "ataque_canhao": {"energy_reserves": -2},
}


def _character(*, energy: int = 10, oxygen: int = 100, hp: int = 20) -> dict:
    return {
        "meta": {"last_updated": "TURNO_0"},
        "identity": {"name": "Ferro", "status": "STABLE"},
        "vitals": {
            "hp": {"current": hp, "max": 20},
            "oxygen_level": {"current": oxygen, "max": 100},
            "energy_reserves": {"current": energy, "max": 100},
            "fome": {"current": 100, "max": 100},
            "sede": {"current": 100, "max": 100},
            "exaustao": {"current": 100, "max": 100},
        },
        "attributes": {"sobrevivencia": {"value": 10}},
        "progression": {"level": 1, "xp_current": 7, "xp_to_next_level": 100},
    }


class LegacySurvivalCostCharacterizationTests(unittest.TestCase):
    def test_basal_cost_catalog_preserves_all_profiles_order_keys_and_values(self):
        """Detects profile, nested-key, zero-value, or profile-difference drift."""
        self.assertEqual(list(mechanics_engine.BASAL_COST), list(EXPECTED_BASAL_COST))
        self.assertEqual(mechanics_engine.BASAL_COST, EXPECTED_BASAL_COST)

        for profile, expected in EXPECTED_BASAL_COST.items():
            with self.subTest(profile=profile):
                self.assertEqual(list(mechanics_engine.BASAL_COST[profile]), list(expected))
                self.assertEqual(mechanics_engine.BASAL_COST[profile], expected)

        self.assertEqual(EXPECTED_BASAL_COST["A_selva"]["oxygen_level"], 0)
        self.assertEqual(EXPECTED_BASAL_COST["A_selva"]["hp_passive"], 0)
        self.assertNotEqual(EXPECTED_BASAL_COST["A_selva"], EXPECTED_BASAL_COST["B_cidade"])
        self.assertNotEqual(EXPECTED_BASAL_COST["C_nave"], EXPECTED_BASAL_COST["D_eva"])

    def test_get_basal_cost_is_case_sensitive_and_returns_independent_copies(self):
        """Detects fallback, case-folding, or shared-dictionary mutations."""
        before = copy.deepcopy(mechanics_engine.BASAL_COST)

        for profile, expected in EXPECTED_BASAL_COST.items():
            with self.subTest(profile=profile):
                self.assertEqual(mechanics_engine.get_basal_cost(profile), expected)
                self.assertEqual(list(mechanics_engine.get_basal_cost(profile)), list(expected))

        self.assertEqual(mechanics_engine.get_basal_cost("a_selva"), {})
        self.assertEqual(mechanics_engine.get_basal_cost("unknown"), {})
        self.assertEqual(mechanics_engine.get_basal_cost(None), {})

        returned = mechanics_engine.get_basal_cost("A_selva")
        returned["energy_reserves"] = 999
        returned["new_key"] = -9
        self.assertEqual(mechanics_engine.BASAL_COST, before)
        self.assertEqual(mechanics_engine.get_basal_cost("A_selva"), EXPECTED_BASAL_COST["A_selva"])
        self.assertEqual(mechanics_engine.get_basal_cost("B_cidade"), EXPECTED_BASAL_COST["B_cidade"])

    def test_planet_extra_cost_catalog_preserves_all_entries_order_keys_and_values(self):
        """Detects catalog additions, removals, order changes, or altered extra costs."""
        self.assertEqual(
            list(mechanics_engine.PLANET_EXTRA_COST), list(EXPECTED_PLANET_EXTRA_COST)
        )
        self.assertEqual(mechanics_engine.PLANET_EXTRA_COST, EXPECTED_PLANET_EXTRA_COST)
        for planet, expected in EXPECTED_PLANET_EXTRA_COST.items():
            with self.subTest(planet=planet):
                self.assertEqual(list(mechanics_engine.PLANET_EXTRA_COST[planet]), list(expected))
                self.assertEqual(mechanics_engine.PLANET_EXTRA_COST[planet], expected)

    def test_get_basal_cost_applies_planet_extras_only_to_e_planeta_without_mutation(self):
        """Detects wrong-profile extras, overwrites instead of sums, and global mutation."""
        before_basal = copy.deepcopy(mechanics_engine.BASAL_COST)
        before_planets = copy.deepcopy(mechanics_engine.PLANET_EXTRA_COST)
        expected_e_planet = {
            "mundo_corrosivo": {"energy_reserves": -2, "suit_integrity": -2},
            "abismo_oceanico": {"energy_reserves": -2, "hull_integrity": -3},
            "deserto_de_vidro": {"energy_reserves": -2},
            "cemiterio_silicio": {"energy_reserves": -2},
            "gigante_gasoso": {"energy_reserves": -2, "fuel_cells": -1},
            "mundo_simbiotico": {"energy_reserves": -2, "hp_passive": -2},
            "orbe_estilhacado": {"energy_reserves": -2},
            "mundo_orfao": {"energy_reserves": -2, "hp_passive": -3},
            "horizonte_eventos": {"energy_reserves": -3},
            "paraiso_artificial": {
                "energy_reserves": -2,
                "suit_integrity": -5,
                "hp_passive": -1,
            },
        }

        for planet, expected in expected_e_planet.items():
            with self.subTest(e_planet=planet):
                actual = mechanics_engine.get_basal_cost("E_planeta", planet)
                self.assertEqual(actual, expected)
                self.assertEqual(list(actual), list(expected))

        for planet in (None, "", "unknown", "MUNDO_CORROSIVO"):
            with self.subTest(e_planet=planet):
                self.assertEqual(
                    mechanics_engine.get_basal_cost("E_planeta", planet),
                    {"energy_reserves": -2},
                )

        for profile, expected in EXPECTED_BASAL_COST.items():
            if profile == "E_planeta":
                continue
            for planet in EXPECTED_PLANET_EXTRA_COST:
                with self.subTest(profile=profile, ignored_planet=planet):
                    self.assertEqual(mechanics_engine.get_basal_cost(profile, planet), expected)

        returned = mechanics_engine.get_basal_cost("E_planeta", "paraiso_artificial")
        returned["suit_integrity"] = 999
        returned["energy_reserves"] = 999
        self.assertEqual(mechanics_engine.BASAL_COST, before_basal)
        self.assertEqual(mechanics_engine.PLANET_EXTRA_COST, before_planets)
        self.assertEqual(
            mechanics_engine.get_basal_cost("E_planeta", "paraiso_artificial"),
            expected_e_planet["paraiso_artificial"],
        )

    def test_action_cost_catalog_preserves_actions_order_keys_and_values(self):
        """Detects catalog drift, including energy, fuel, and intentionally empty actions."""
        self.assertEqual(list(mechanics_engine.ACTION_COST), list(EXPECTED_ACTION_COST))
        self.assertEqual(mechanics_engine.ACTION_COST, EXPECTED_ACTION_COST)
        for action, expected in EXPECTED_ACTION_COST.items():
            with self.subTest(action=action):
                self.assertEqual(list(mechanics_engine.ACTION_COST[action]), list(expected))
                self.assertEqual(mechanics_engine.ACTION_COST[action], expected)

        self.assertEqual(EXPECTED_ACTION_COST["explorar_area"], {"energy_reserves": -3})
        self.assertEqual(EXPECTED_ACTION_COST["salto_decolagem"], {"fuel_cells": -1})
        self.assertEqual(EXPECTED_ACTION_COST["primeiros_socorros"], {})
        self.assertEqual(EXPECTED_ACTION_COST["combate"], {})

    def test_action_costs_are_used_by_calculate_turn_cost_without_mutating_catalogs(self):
        """Detects discarded action costs, case folding, fallback, and shared result mutation."""
        before_basal = copy.deepcopy(mechanics_engine.BASAL_COST)
        before_actions = copy.deepcopy(mechanics_engine.ACTION_COST)

        for action, expected in EXPECTED_ACTION_COST.items():
            with self.subTest(action=action):
                self.assertEqual(mechanics_engine.calculate_turn_cost(action, "unknown"), expected)

        self.assertEqual(mechanics_engine.calculate_turn_cost("EXPLORAR_AREA", "unknown"), {})
        self.assertEqual(mechanics_engine.calculate_turn_cost("unknown", "unknown"), {})

        returned = mechanics_engine.calculate_turn_cost("explorar_area", "unknown")
        returned["energy_reserves"] = 999
        returned["new_key"] = -9
        self.assertEqual(mechanics_engine.BASAL_COST, before_basal)
        self.assertEqual(mechanics_engine.ACTION_COST, before_actions)
        self.assertEqual(
            mechanics_engine.calculate_turn_cost("explorar_area", "unknown"),
            {"energy_reserves": -3},
        )

    def test_calculate_turn_cost_combines_explicit_legacy_cases_in_order_without_mutation(self):
        """Detects replacement, dropped zeroes, order drift, or mutable shared results."""
        before_basal = copy.deepcopy(mechanics_engine.BASAL_COST)
        before_planets = copy.deepcopy(mechanics_engine.PLANET_EXTRA_COST)
        before_actions = copy.deepcopy(mechanics_engine.ACTION_COST)
        cases = (
            (
                "explorar_area",
                "A_selva",
                None,
                {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0},
            ),
            (
                "salto_decolagem",
                "C_nave",
                None,
                {"energy_reserves": -1, "oxygen_level": -1, "fuel_cells": -1},
            ),
            (
                "unknown",
                "D_eva",
                None,
                {"oxygen_level": -5, "energy_reserves": -2},
            ),
            ("scan", "unknown", None, {"energy_reserves": -5}),
            ("unknown", "unknown", None, {}),
            (
                "explorar_area",
                "E_planeta",
                "paraiso_artificial",
                {"energy_reserves": -5, "suit_integrity": -5, "hp_passive": -1},
            ),
        )

        for action, profile, planet, expected in cases:
            with self.subTest(action=action, profile=profile, planet=planet):
                actual = mechanics_engine.calculate_turn_cost(action, profile, planet)
                self.assertEqual(actual, expected)
                self.assertEqual(list(actual), list(expected))

        first = mechanics_engine.calculate_turn_cost("explorar_area", "A_selva")
        first["energy_reserves"] = 999
        second = mechanics_engine.calculate_turn_cost("explorar_area", "A_selva")
        self.assertEqual(second, {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0})
        self.assertIsNot(first, second)
        self.assertEqual(mechanics_engine.BASAL_COST, before_basal)
        self.assertEqual(mechanics_engine.PLANET_EXTRA_COST, before_planets)
        self.assertEqual(mechanics_engine.ACTION_COST, before_actions)


class LegacyExploreSurvivalCostCharacterizationTests(unittest.TestCase):
    def test_action_explore_uses_default_or_override_profile_once_and_charges_after_success_or_failure(self):
        """Detects lost profile wiring, success-only charging, or a changed HUD/outcome path."""
        cases = (
            (None, ([20], 20, "ÚNICO", ""), 5, 100, "SUCESSO CRÍTICO", "A_selva"),
            ("C_nave", ([1], 1, "ÚNICO", ""), 6, 99, "FALHA CRÍTICA", "C_nave"),
        )

        for profile_arg, roll_result, expected_energy, expected_oxygen, outcome, expected_profile in cases:
            with self.subTest(profile=expected_profile, outcome=outcome):
                character = _character()
                report: list[str] = []
                args = SimpleNamespace(dc="medio", profile=profile_arg)
                with (
                    mock.patch.object(system_engine, "_roll", return_value=roll_result),
                    mock.patch.object(
                        system_engine._me,
                        "calculate_turn_cost",
                        wraps=system_engine._me.calculate_turn_cost,
                    ) as calculate_cost,
                ):
                    system_engine.action_explore(character, {}, args, {}, report)

                calculate_cost.assert_called_once_with("explorar_area", expected_profile)
                self.assertEqual(character["vitals"]["energy_reserves"]["current"], expected_energy)
                self.assertEqual(character["vitals"]["oxygen_level"]["current"], expected_oxygen)
                self.assertIn(f"\n3. RESULTADO: {outcome}", report)
                self.assertIn(f"→ {outcome}", report[-1])
                self.assertIn(f"EN {expected_energy:>3}%", report[-1])

    def test_action_explore_charges_only_existing_nonzero_vitals_once_in_cost_order_and_clamps(self):
        """Detects zero or unknown charges, repeated writes, report-order drift, or lost clamping."""
        character = _character(energy=10, oxygen=88, hp=10)
        report: list[str] = []
        costs = {
            "energy_reserves": -3,
            "oxygen_level": 0,
            "suit_integrity": -4,
            "hp": -30,
        }
        original_set_vital = system_engine.set_vital

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                return_value=([15], 15, "ÚNICO", ""),
            ),
            mock.patch.object(
                system_engine._me,
                "calculate_turn_cost",
                return_value=costs,
            ) as calculate_cost,
            mock.patch.object(system_engine, "set_vital", wraps=original_set_vital) as set_vital,
        ):
            system_engine.action_explore(
                character,
                {},
                SimpleNamespace(dc="medio", profile="D_eva"),
                {},
                report,
            )

        calculate_cost.assert_called_once_with("explorar_area", "D_eva")
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 7)
        self.assertEqual(character["vitals"]["oxygen_level"]["current"], 88)
        self.assertEqual(character["vitals"]["hp"]["current"], 0)
        self.assertEqual(
            set_vital.call_args_list,
            [mock.call(character, "energy_reserves", 7), mock.call(character, "hp", -20)],
        )
        self.assertEqual(
            report[report.index("\n4. DELTAS — JOGADOR") + 1:-1],
            ["   energy_reserves: -3", "   hp: -30"],
        )
        self.assertIn("→ SUCESSO", report[-1])
        self.assertIn("7. STATUS FINAL: DECEASED", report[-1])

    def test_action_explore_rolls_before_calculating_cost_then_applies_deltas(self):
        """Freezes the observed roll → cost → vital-write sequence despite the cost docstring."""
        character = _character()
        report: list[str] = []
        events: list[str] = []
        original_set_vital = system_engine.set_vital

        def roll(*_args):
            events.append("roll")
            return ([15], 15, "ÚNICO", "")

        def calculate_cost(*_args):
            events.append("cost")
            return {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0}

        def set_vital(cs, key, value):
            events.append(f"set:{key}")
            original_set_vital(cs, key, value)

        with (
            mock.patch.object(system_engine, "_roll", side_effect=roll),
            mock.patch.object(system_engine._me, "calculate_turn_cost", side_effect=calculate_cost),
            mock.patch.object(system_engine, "set_vital", side_effect=set_vital),
        ):
            system_engine.action_explore(
                character,
                {},
                SimpleNamespace(dc="medio", profile=None),
                {},
                report,
            )

        self.assertEqual(events, ["roll", "cost", "set:energy_reserves"])
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 5)


if __name__ == "__main__":
    unittest.main()
