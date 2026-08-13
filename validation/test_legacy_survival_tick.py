"""Characterization tests for the current legacy survival tick contracts."""

import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

import system_engine


def _character(*, hp: int = 20, fome: int = 100, sede: int = 100, exaustao: int = 100) -> dict:
    return {
        "meta": {"last_updated": "TURNO_0"},
        "identity": {"name": "Ferro", "status": "STABLE"},
        "vitals": {
            "hp": {"current": hp, "max": 20},
            "oxygen_level": {"current": 100, "max": 100},
            "energy_reserves": {"current": 100, "max": 100},
            "fome": {"current": fome, "max": 100},
            "sede": {"current": sede, "max": 100},
            "exaustao": {"current": exaustao, "max": 100},
        },
        "passive_skills": [],
    }


class LegacySurvivalVitalCharacterizationTests(unittest.TestCase):
    def test_ensure_creates_absent_vitals_in_place_with_stable_format_and_order(self):
        cs = {"marker": "preserved"}

        result = system_engine._ensure_survival_vitals(cs)

        self.assertIsNone(result)
        self.assertEqual(
            cs,
            {
                "marker": "preserved",
                "vitals": {
                    "fome": {"current": 100, "max": 100},
                    "sede": {"current": 100, "max": 100},
                    "exaustao": {"current": 100, "max": 100},
                },
            },
        )
        self.assertEqual(list(cs["vitals"]), ["fome", "sede", "exaustao"])

    def test_ensure_preserves_existing_resources_fields_identity_and_scalar_compatibility(self):
        vitals = {
            "hp": {"current": 17, "max": 20},
            "fome": "7",
            "sede": {"max": 55, "source": "canteen"},
            "exaustao": {"current": 12, "source": "watch"},
            "oxygen_level": {"current": 88, "max": 100},
        }
        cs = {"vitals": vitals, "other": {"unchanged": True}}

        result = system_engine._ensure_survival_vitals(cs)

        self.assertIsNone(result)
        self.assertIs(cs["vitals"], vitals)
        self.assertEqual(
            cs,
            {
                "vitals": {
                    "hp": {"current": 17, "max": 20},
                    "fome": {"current": 7, "max": 100},
                    "sede": {"max": 55, "source": "canteen", "current": 100},
                    "exaustao": {"current": 12, "source": "watch", "max": 100},
                    "oxygen_level": {"current": 88, "max": 100},
                },
                "other": {"unchanged": True},
            },
        )
        self.assertEqual(
            list(vitals), ["hp", "fome", "sede", "exaustao", "oxygen_level"]
        )

    def test_ensure_preserves_a_complete_survival_vital_exactly(self):
        vitals = {
            "fome": {"current": 9, "max": 65, "source": "rations"},
        }
        cs = {"vitals": vitals}

        result = system_engine._ensure_survival_vitals(cs)

        self.assertIsNone(result)
        self.assertIs(cs["vitals"], vitals)
        self.assertEqual(
            cs,
            {
                "vitals": {
                    "fome": {"current": 9, "max": 65, "source": "rations"},
                    "sede": {"current": 100, "max": 100},
                    "exaustao": {"current": 100, "max": 100},
                }
            },
        )


class LegacySurvivalTickCharacterizationTests(unittest.TestCase):
    def test_tick_decays_resources_in_order_and_reports_the_critical_exhaustion_boundary(self):
        cs = _character(fome=10, sede=8, exaustao=21)
        report = ["before"]

        result = system_engine._tick_survival(cs, report, "combat")

        self.assertIsNone(result)
        self.assertEqual(
            cs["vitals"],
            {
                "hp": {"current": 20, "max": 20},
                "oxygen_level": {"current": 100, "max": 100},
                "energy_reserves": {"current": 100, "max": 100},
                "fome": {"current": 7, "max": 100},
                "sede": {"current": 3, "max": 100},
                "exaustao": {"current": 19, "max": 100},
            },
        )
        self.assertEqual(
            report,
            [
                "before",
                "\n0. SOBREVIVÊNCIA (decay por turno)",
                "   FOME: 10 → 7 (-3)",
                "   SEDE: 8 → 3 (-5)",
                "   EXAUSTAO: 21 → 19 (-2)",
                "   ⚠ EXAUSTÃO CRÍTICA (19%) — penalidade em rolagens!",
            ],
        )

    def test_tick_clamps_depletion_aggregates_hunger_and_thirst_damage_once_and_clamps_hp(self):
        cs = _character(hp=2, fome=2, sede=5, exaustao=2)
        report: list[str] = []

        with mock.patch.object(system_engine, "set_vital", wraps=system_engine.set_vital) as set_vital:
            result = system_engine._tick_survival(cs, report, "explore")

        self.assertIsNone(result)
        self.assertEqual(cs["vitals"]["fome"]["current"], 0)
        self.assertEqual(cs["vitals"]["sede"]["current"], 0)
        self.assertEqual(cs["vitals"]["exaustao"]["current"], 0)
        self.assertEqual(cs["vitals"]["hp"]["current"], 0)
        set_vital.assert_called_once_with(cs, "hp", -1)
        self.assertEqual(
            report,
            [
                "\n0. SOBREVIVÊNCIA (decay por turno)",
                "   FOME: 2 → 0 (-3)",
                "   ⚠ FOME ESGOTADA — -1 HP por turno!",
                "   SEDE: 5 → 0 (-5)",
                "   ⚠ SEDE ESGOTADA — -2 HP por turno!",
                "   EXAUSTAO: 2 → 0 (-2)",
                "   HP: 2 → 0 (-3 por esgotamento)",
            ],
        )

    def test_tick_repeats_damage_at_zero_without_unchanged_decay_lines_or_exhaustion_damage(self):
        cs = _character(hp=10, fome=0, sede=0, exaustao=0)
        report: list[str] = []

        with mock.patch.object(system_engine, "set_vital", wraps=system_engine.set_vital) as set_vital:
            result = system_engine._tick_survival(cs, report, "unknown")

        self.assertIsNone(result)
        self.assertEqual(cs["vitals"]["hp"]["current"], 7)
        set_vital.assert_called_once_with(cs, "hp", 7)
        self.assertEqual(
            report,
            [
                "\n0. SOBREVIVÊNCIA (decay por turno)",
                "   ⚠ FOME ESGOTADA — -1 HP por turno!",
                "   ⚠ SEDE ESGOTADA — -2 HP por turno!",
                "   HP: 10 → 7 (-3 por esgotamento)",
            ],
        )
        self.assertNotIn("   ⚠ EXAUSTÃO CRÍTICA (0%) — penalidade em rolagens!", report)

    def test_tick_exhaustion_warning_starts_at_twenty_and_excludes_above_limit_and_zero(self):
        cases = ((23, 21, False), (22, 20, True), (21, 19, True), (2, 0, False))

        for before, expected, warning_expected in cases:
            with self.subTest(before=before):
                cs = _character(exaustao=before)
                report: list[str] = []

                result = system_engine._tick_survival(cs, report, "combat")

                self.assertIsNone(result)
                self.assertEqual(cs["vitals"]["exaustao"]["current"], expected)
                warning = f"   ⚠ EXAUSTÃO CRÍTICA ({expected}%) — penalidade em rolagens!"
                self.assertEqual(warning in report, warning_expected)

    def _assert_tick_normalizes_without_decay_or_report(self, action: str):
        cs = {"vitals": {"hp": {"current": 20, "max": 20}}}
        report: list[str] = []

        with mock.patch.object(system_engine, "set_vital", wraps=system_engine.set_vital) as set_vital:
            result = system_engine._tick_survival(cs, report, action)

        self.assertIsNone(result)
        self.assertEqual(
            cs["vitals"],
            {
                "hp": {"current": 20, "max": 20},
                "fome": {"current": 100, "max": 100},
                "sede": {"current": 100, "max": 100},
                "exaustao": {"current": 100, "max": 100},
            },
        )
        self.assertEqual(report, [])
        set_vital.assert_not_called()

    def _assert_tick_decays_normally(self, action: str):
        cs = _character()
        report: list[str] = []

        result = system_engine._tick_survival(cs, report, action)

        self.assertIsNone(result)
        self.assertEqual(
            [cs["vitals"][key]["current"] for key in ("fome", "sede", "exaustao")],
            [97, 95, 98],
        )
        self.assertEqual(
            report,
            [
                "\n0. SOBREVIVÊNCIA (decay por turno)",
                "   FOME: 100 → 97 (-3)",
                "   SEDE: 100 → 95 (-5)",
                "   EXAUSTAO: 100 → 98 (-2)",
            ],
        )

    def test_status_normalizes_without_decay_or_report(self):
        self._assert_tick_normalizes_without_decay_or_report("status")

    def test_rest_normalizes_without_decay_or_report(self):
        self._assert_tick_normalizes_without_decay_or_report("rest")

    def test_empty_action_decays_normally(self):
        self._assert_tick_decays_normally("")

    def test_ordinary_action_decays_normally(self):
        self._assert_tick_decays_normally("combat")

    def test_unknown_action_decays_normally(self):
        self._assert_tick_decays_normally("not-a-command")


class LegacySurvivalMainCharacterizationTests(unittest.TestCase):
    def _run_main(self, action: str, action_patch_name: str, action_side_effect):
        cs = _character(fome=10, sede=10, exaustao=10)
        ac = {"combate_ativo": False}
        events: list[str] = []
        args = SimpleNamespace(action=action)
        original_tick = system_engine._tick_survival

        def load_character_sheet():
            events.append("load-character")
            return cs

        def load_active_combat():
            events.append("load-combat")
            return ac

        def load_inventory():
            events.append("load-inventory")
            return []

        def apply_status(character, report):
            events.append("status-effects")
            return 0

        def tick(character, report, tick_action):
            events.append("tick")
            return original_tick(character, report, tick_action)

        def dispatch(*dispatch_args):
            events.append("dispatch")
            return action_side_effect(*dispatch_args)

        with (
            mock.patch.object(
                system_engine.argparse.ArgumentParser, "parse_args", return_value=args
            ),
            mock.patch.object(system_engine, "load_character_sheet", side_effect=load_character_sheet),
            mock.patch.object(system_engine, "load_active_combat", side_effect=load_active_combat),
            mock.patch.object(system_engine, "load_inventory", side_effect=load_inventory),
            mock.patch.object(system_engine._me, "apply_passive_skill_effects", return_value={}),
            mock.patch.object(system_engine, "_apply_player_status", side_effect=apply_status),
            mock.patch.object(system_engine, "_tick_survival", side_effect=tick) as tick_mock,
            mock.patch.object(system_engine, action_patch_name, side_effect=dispatch) as action_mock,
            mock.patch.object(system_engine, "save_character_sheet") as save_character_sheet,
            mock.patch.object(system_engine, "save_active_combat") as save_active_combat,
            mock.patch.object(system_engine, "save_inventory") as save_inventory,
            mock.patch.object(system_engine, "load_chapter_tracker", return_value={}),
            mock.patch.object(system_engine, "save_chapter_tracker") as save_chapter_tracker,
            mock.patch.object(system_engine.os, "makedirs") as makedirs,
            mock.patch("builtins.open", mock.mock_open()) as opened,
            mock.patch("builtins.print") as printed,
        ):
            system_engine.main()

        return {
            "cs": cs,
            "events": events,
            "tick": tick_mock,
            "action": action_mock,
            "save_character_sheet": save_character_sheet,
            "save_active_combat": save_active_combat,
            "save_inventory": save_inventory,
            "save_chapter_tracker": save_chapter_tracker,
            "makedirs": makedirs,
            "opened": opened,
            "printed": printed,
        }

    def test_main_ticks_after_status_processing_and_before_action_report_and_dispatch(self):
        def action_combat(cs, ac, args, passive_fx, report):
            report.append("combat dispatched")

        result = self._run_main("combat", "action_combat", action_combat)

        self.assertEqual(
            result["events"],
            ["load-character", "load-combat", "load-inventory", "status-effects", "tick", "dispatch"],
        )
        result["tick"].assert_called_once_with(result["cs"], mock.ANY, "combat")
        result["action"].assert_called_once()
        report_text = result["printed"].call_args_list[0].args[0]
        self.assertLess(report_text.index("0. SOBREVIVÊNCIA"), report_text.index("1. AÇÃO: Combate"))
        self.assertLess(report_text.index("1. AÇÃO: Combate"), report_text.index("combat dispatched"))
        result["save_character_sheet"].assert_called_once_with(result["cs"])
        result["save_active_combat"].assert_called_once()
        result["save_inventory"].assert_not_called()
        result["save_chapter_tracker"].assert_not_called()
        result["makedirs"].assert_called_once()
        self.assertEqual(result["opened"].call_count, 1)
        self.assertIn("technical_report.txt", result["opened"].call_args.args[0])

    def test_main_status_does_not_call_survival_tick_or_save_campaign_state(self):
        def action_status(cs, ac, report):
            report.append("status dispatched")

        result = self._run_main("status", "action_status", action_status)

        self.assertEqual(
            result["events"],
            ["load-character", "load-combat", "load-inventory", "status-effects", "dispatch"],
        )
        result["tick"].assert_not_called()
        result["action"].assert_called_once()
        result["save_character_sheet"].assert_not_called()
        result["save_active_combat"].assert_not_called()
        result["save_inventory"].assert_not_called()
        result["save_chapter_tracker"].assert_not_called()
        self.assertEqual(result["opened"].call_count, 1)

    def test_main_rest_ticks_before_rest_dispatch_without_consuming_recoverable_vitals(self):
        seen_before_rest: dict[str, int] = {}

        def action_rest(cs, ac, args, passive_fx, report):
            seen_before_rest.update(
                {key: cs["vitals"][key]["current"] for key in ("fome", "sede", "exaustao")}
            )
            report.append("rest dispatched")

        result = self._run_main("rest", "action_rest", action_rest)

        self.assertEqual(
            result["events"],
            ["load-character", "load-combat", "load-inventory", "status-effects", "tick", "dispatch"],
        )
        result["tick"].assert_called_once_with(result["cs"], mock.ANY, "rest")
        self.assertEqual(seen_before_rest, {"fome": 10, "sede": 10, "exaustao": 10})
        report_text = result["printed"].call_args_list[0].args[0]
        self.assertNotIn("0. SOBREVIVÊNCIA", report_text)
        self.assertLess(report_text.index("1. AÇÃO: Descanso"), report_text.index("rest dispatched"))
        result["save_character_sheet"].assert_called_once_with(result["cs"])
        result["save_active_combat"].assert_called_once()
        self.assertEqual(result["opened"].call_count, 1)


class LegacySurvivalStageBoundaryTests(unittest.TestCase):
    def test_legacy_survival_tick_functions_remain_in_system_engine_not_domain_module(self):
        system_engine_tree = ast.parse(
            (ROOT / "skills" / "system_engine.py").read_text(encoding="utf-8")
        )
        survival_tree = ast.parse(
            (ROOT / "chronos" / "domain" / "survival.py").read_text(encoding="utf-8")
        )
        system_engine_functions = {
            node.name for node in system_engine_tree.body if isinstance(node, ast.FunctionDef)
        }
        survival_functions = {
            node.name for node in survival_tree.body if isinstance(node, ast.FunctionDef)
        }

        self.assertTrue({"_ensure_survival_vitals", "_tick_survival"} <= system_engine_functions)
        self.assertFalse({"_ensure_survival_vitals", "_tick_survival"} & survival_functions)
