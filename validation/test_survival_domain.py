"""Direct characterization and adapter tests for pure survival-cost rules."""

import ast
import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

from chronos.domain import survival
import mechanics_engine


EXPECTED_BASAL_COST = {
    "A_selva": {"energy_reserves": -2, "oxygen_level": 0, "hp_passive": 0},
    "B_cidade": {"energy_reserves": -1, "oxygen_level": 0, "hp_passive": 0},
    "C_nave": {"energy_reserves": -1, "oxygen_level": -1},
    "D_eva": {"oxygen_level": -5, "energy_reserves": -2},
    "E_planeta": {"energy_reserves": -2},
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


class SurvivalDomainTests(unittest.TestCase):
    def assert_catalogs_equal_expected(self):
        for actual, expected in (
            (survival.BASAL_COST, EXPECTED_BASAL_COST),
            (survival.PLANET_EXTRA_COST, EXPECTED_PLANET_EXTRA_COST),
            (survival.ACTION_COST, EXPECTED_ACTION_COST),
        ):
            self.assertEqual(list(actual), list(expected))
            self.assertEqual(actual, expected)
            for name, values in expected.items():
                self.assertEqual(list(actual[name]), list(values))

    def test_complete_catalogs_preserve_order_zeroes_and_empty_actions(self):
        self.assert_catalogs_equal_expected()
        self.assertEqual(survival.BASAL_COST["A_selva"]["oxygen_level"], 0)
        self.assertEqual(survival.BASAL_COST["B_cidade"]["hp_passive"], 0)
        self.assertEqual(survival.PLANET_EXTRA_COST["deserto_de_vidro"], {})
        self.assertEqual(survival.ACTION_COST["primeiros_socorros"], {})
        self.assertEqual(survival.ACTION_COST["combate"], {})

    def test_get_basal_cost_known_unknown_none_case_and_planet_behavior(self):
        for profile, expected in EXPECTED_BASAL_COST.items():
            with self.subTest(profile=profile):
                result = survival.get_basal_cost(profile)
                self.assertEqual(result, expected)
                self.assertEqual(list(result), list(expected))

        for profile in ("a_selva", "unknown", None, ""):
            with self.subTest(profile=profile):
                self.assertEqual(survival.get_basal_cost(profile), {})

        expected_planet_costs = {
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
        for planet, expected in expected_planet_costs.items():
            with self.subTest(planet=planet):
                result = survival.get_basal_cost("E_planeta", planet)
                self.assertEqual(result, expected)
                self.assertEqual(list(result), list(expected))

        for planet in (None, "", "unknown", "MUNDO_CORROSIVO"):
            with self.subTest(unknown_planet=planet):
                self.assertEqual(survival.get_basal_cost("E_planeta", planet), {"energy_reserves": -2})

        for profile, expected in EXPECTED_BASAL_COST.items():
            if profile == "E_planeta":
                continue
            for planet in EXPECTED_PLANET_EXTRA_COST:
                with self.subTest(profile=profile, ignored_planet=planet):
                    self.assertEqual(survival.get_basal_cost(profile, planet), expected)

    def test_calculate_turn_cost_combines_in_order_and_handles_unknowns(self):
        cases = (
            ("explorar_area", "A_selva", None, {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0}),
            ("salto_decolagem", "C_nave", None, {"energy_reserves": -1, "oxygen_level": -1, "fuel_cells": -1}),
            ("scan", "E_planeta", "horizonte_eventos", {"energy_reserves": -8}),
            ("combate", "D_eva", None, {"oxygen_level": -5, "energy_reserves": -2}),
            ("scan", "unknown", None, {"energy_reserves": -5}),
            ("unknown", "unknown", None, {}),
            ("EXPLORAR_AREA", "A_selva", None, {"energy_reserves": -2, "oxygen_level": 0, "hp_passive": 0}),
        )
        for action, profile, planet, expected in cases:
            with self.subTest(action=action, profile=profile, planet=planet):
                result = survival.calculate_turn_cost(action, profile, planet)
                self.assertEqual(result, expected)
                self.assertEqual(list(result), list(expected))

        for action, expected in EXPECTED_ACTION_COST.items():
            with self.subTest(action_only=action):
                self.assertEqual(survival.calculate_turn_cost(action, None), expected)

    def test_returns_are_independent_and_catalogs_never_mutate(self):
        basal_before = copy.deepcopy(EXPECTED_BASAL_COST)
        planet_before = copy.deepcopy(EXPECTED_PLANET_EXTRA_COST)
        action_before = copy.deepcopy(EXPECTED_ACTION_COST)

        basal = survival.get_basal_cost("E_planeta", "paraiso_artificial")
        combined = survival.calculate_turn_cost("explorar_area", "A_selva")
        basal["energy_reserves"] = 999
        basal["new_key"] = -1
        combined["energy_reserves"] = 999
        combined["new_key"] = -1

        self.assertEqual(survival.BASAL_COST, basal_before)
        self.assertEqual(survival.PLANET_EXTRA_COST, planet_before)
        self.assertEqual(survival.ACTION_COST, action_before)
        self.assertEqual(
            survival.get_basal_cost("E_planeta", "paraiso_artificial"),
            {"energy_reserves": -2, "suit_integrity": -5, "hp_passive": -1},
        )
        self.assertEqual(
            survival.calculate_turn_cost("explorar_area", "A_selva"),
            {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0},
        )


class SurvivalAdapterTests(unittest.TestCase):
    def test_mechanics_catalogs_are_domain_identity_aliases(self):
        self.assertIs(mechanics_engine.BASAL_COST, survival.BASAL_COST)
        self.assertIs(mechanics_engine.PLANET_EXTRA_COST, survival.PLANET_EXTRA_COST)
        self.assertIs(mechanics_engine.ACTION_COST, survival.ACTION_COST)

    def test_wrappers_delegate_once_with_positional_defaults_and_return_unchanged(self):
        basal_sentinel = object()
        with mock.patch.object(survival, "get_basal_cost", return_value=basal_sentinel) as get_basal:
            self.assertIs(mechanics_engine.get_basal_cost("A_selva"), basal_sentinel)
            get_basal.assert_called_once_with("A_selva", None)

        turn_sentinel = object()
        with mock.patch.object(survival, "calculate_turn_cost", return_value=turn_sentinel) as calculate:
            self.assertIs(
                mechanics_engine.calculate_turn_cost("explorar_area", "E_planeta", "mundo_corrosivo"),
                turn_sentinel,
            )
            calculate.assert_called_once_with("explorar_area", "E_planeta", "mundo_corrosivo")

    def test_real_adapter_parity_and_public_signatures(self):
        self.assertEqual(
            mechanics_engine.get_basal_cost("E_planeta", "mundo_corrosivo"),
            {"energy_reserves": -2, "suit_integrity": -2},
        )
        self.assertEqual(
            mechanics_engine.calculate_turn_cost("salto_decolagem", "C_nave"),
            {"energy_reserves": -1, "oxygen_level": -1, "fuel_cells": -1},
        )
        tree = ast.parse((SKILLS / "mechanics_engine.py").read_text(encoding="utf-8"))
        signatures = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"get_basal_cost", "calculate_turn_cost"}
        }
        self.assertEqual(
            [ast.unparse(argument.annotation) for argument in signatures["get_basal_cost"].args.args],
            ["str", "Optional[str]"],
        )
        self.assertEqual(ast.unparse(signatures["get_basal_cost"].returns), "dict")
        self.assertEqual(
            [ast.unparse(argument.annotation) for argument in signatures["calculate_turn_cost"].args.args],
            ["str", "str", "Optional[str]"],
        )
        self.assertEqual(ast.unparse(signatures["calculate_turn_cost"].returns), "dict")
        self.assertEqual(len(signatures["get_basal_cost"].args.defaults), 1)
        self.assertEqual(len(signatures["calculate_turn_cost"].args.defaults), 1)
        self.assertIsNone(signatures["get_basal_cost"].args.defaults[0].value)
        self.assertIsNone(signatures["calculate_turn_cost"].args.defaults[0].value)

    def test_normal_package_and_dynamic_legacy_loads_work(self):
        self.assertIsNotNone(survival.calculate_turn_cost("explorar_area", "A_selva"))
        spec = importlib.util.spec_from_file_location(
            "legacy_mechanics_engine", SKILLS / "mechanics_engine.py"
        )
        legacy = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(legacy)
        self.assertIs(legacy.BASAL_COST, survival.BASAL_COST)
        self.assertEqual(
            legacy.calculate_turn_cost("explorar_area", "A_selva"),
            {"energy_reserves": -5, "oxygen_level": 0, "hp_passive": 0},
        )

    def test_adapter_ast_has_aliases_and_no_survival_formula(self):
        tree = ast.parse((SKILLS / "mechanics_engine.py").read_text(encoding="utf-8"))
        aliases = {}
        wrappers = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in {"BASAL_COST", "PLANET_EXTRA_COST", "ACTION_COST"}:
                    aliases[node.targets[0].id] = node.value
            if isinstance(node, ast.FunctionDef) and node.name in {"get_basal_cost", "calculate_turn_cost"}:
                wrappers[node.name] = node

        for name, value in aliases.items():
            self.assertIsInstance(value, ast.Attribute)
            self.assertIsInstance(value.value, ast.Name)
            self.assertEqual(value.value.id, "_survival")
            self.assertEqual(value.attr, name)

        self.assertEqual(set(wrappers), {"get_basal_cost", "calculate_turn_cost"})
        for name, function in wrappers.items():
            self.assertEqual(len(function.body), 1)
            self.assertIsInstance(function.body[0], ast.Return)
            call = function.body[0].value
            self.assertIsInstance(call, ast.Call)
            self.assertEqual(len([node for node in ast.walk(function) if isinstance(node, ast.Call)]), 1)
            self.assertIsInstance(call.func, ast.Attribute)
            self.assertIsInstance(call.func.value, ast.Name)
            self.assertEqual(call.func.value.id, "_survival")
            self.assertEqual(call.func.attr, name)
            self.assertFalse(any(isinstance(node, (ast.Dict, ast.BinOp, ast.For)) for node in ast.walk(function)))


class SurvivalPurityTests(unittest.TestCase):
    def test_survival_ast_has_no_forbidden_dependencies_or_io(self):
        tree = ast.parse((ROOT / "chronos" / "domain" / "survival.py").read_text(encoding="utf-8"))
        forbidden_modules = {
            "skills", "application", "infrastructure", "web", "os", "pathlib", "subprocess",
            "http", "urllib", "requests", "socket",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
                self.assertFalse(forbidden_modules.intersection(names))
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0], forbidden_modules)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "print", "input", "__import__"})


if __name__ == "__main__":
    unittest.main()
