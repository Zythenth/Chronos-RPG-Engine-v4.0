"""Independent regression coverage for the extracted combat domain."""

import ast
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


class CombatDomainTests(unittest.TestCase):
    def test_constants_are_shared_by_the_legacy_module(self):
        self.assertEqual(combat.ARMOR_DAMAGE_REDUCTION, 2)
        self.assertEqual(combat.SHIP_DAMAGE_ON_SHIELDS, 15)
        self.assertEqual(combat.SHIP_DAMAGE_ON_HULL, 10)

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
    def test_domain_module_has_no_external_io_or_registry_dependencies(self):
        mechanics_source = ROOT / "skills" / "mechanics_engine.py"
        mechanics_tree = ast.parse(mechanics_source.read_text(encoding="utf-8"))
        expected_aliases = {
            "ARMOR_DAMAGE_REDUCTION": "ARMOR_DAMAGE_REDUCTION",
            "SHIP_DAMAGE_ON_SHIELDS": "SHIP_DAMAGE_ON_SHIELDS",
            "SHIP_DAMAGE_ON_HULL": "SHIP_DAMAGE_ON_HULL",
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
