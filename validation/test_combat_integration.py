"""Integration coverage for live combat actions delegating to combat mechanics."""

import ast
import inspect
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


def _character(dexterity: int = 10, energy: int = 10) -> dict:
    return {
        "meta": {"last_updated": "TURNO_0"},
        "identity": {"name": "Ferro", "status": "STABLE"},
        "vitals": {
            "hp": {"current": 20, "max": 20},
            "oxygen_level": {"current": 100, "max": 100},
            "energy_reserves": {"current": energy, "max": 100},
            "hull_integrity": {"current": 100, "max": 100},
            "fome": {"current": 100, "max": 100},
            "sede": {"current": 100, "max": 100},
            "exaustao": {"current": 100, "max": 100},
        },
        "attributes": {
            "forca": {"value": 10},
            "destreza": {"value": dexterity},
        },
        "progression": {"level": 1, "xp_current": 0, "xp_to_next_level": 100},
    }


def _combat(ac: int = 15, shields: int = 20, hull: int = 20) -> dict:
    return {
        "combate_ativo": True,
        "turno_combate": 0,
        "jogador": {"arma_equipada": None, "armadura_equipada": None},
        "posicionamento": {"estado_atual": "MELEE"},
        "inimigo": {
            "nome": "Sentinela de Teste",
            "hp_atual": hull,
            "hp_maximo": hull,
            "dc_defesa": ac,
            "ac": ac,
            "escudos_atuais": shields,
            "velocidade": 0,
            "damage_bonus_racial": 0,
            "tipo_dano": "Físico",
            "status_effects": [],
            "ficha_racial": {"drop": "Sucata", "pode_fugir": False, "dc_moral": 10},
        },
    }


def _fire(character: dict, combat: dict, roll: int, passive_fx: dict | None = None) -> list[str]:
    report: list[str] = []
    with mock.patch.object(system_engine, "_roll", return_value=([roll], roll, "ÚNICO", "")):
        system_engine.action_naval_fire(
            character, combat, SimpleNamespace(), passive_fx or {}, report
        )
    return report


class LiveNavalActionIntegrationTests(unittest.TestCase):
    def test_guards_preserve_legacy_state_and_never_delegate(self):
        cases = (
            (False, 10, "Nenhum combate ativo"),
            (True, 1, "Sem energia suficiente"),
        )

        for active, energy, message in cases:
            with self.subTest(active=active, energy=energy):
                character = _character(energy=energy)
                combat = _combat()
                combat["combate_ativo"] = active
                report: list[str] = []

                with mock.patch.object(
                    system_engine._me,
                    "resolve_ship_combat",
                    side_effect=AssertionError("guard must not resolve naval combat"),
                ) as resolve_ship_combat:
                    system_engine.action_naval_fire(
                        character, combat, SimpleNamespace(), {}, report
                    )

                resolve_ship_combat.assert_not_called()
                self.assertEqual(character["vitals"]["energy_reserves"]["current"], energy)
                self.assertEqual(combat["turno_combate"], 0)
                self.assertTrue(any(message in line for line in report))

    def test_delegation_uses_effective_modifier_current_enemy_data_and_used_d20(self):
        character = _character(dexterity=12)
        combat = _combat(ac=15, shields=8)
        report: list[str] = []

        with (
            mock.patch.object(system_engine, "_roll", return_value=([10], 10, "ÚNICO", "")),
            mock.patch.object(
                system_engine._me,
                "resolve_ship_combat",
                wraps=system_engine._me.resolve_ship_combat,
            ) as resolve_ship_combat,
        ):
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {"ataque_naval_bonus": 3},
                report,
            )

        resolve_ship_combat.assert_called_once_with(
            player_piloting=5,
            enemy_ac=15,
            enemy_shields=8,
            d20_raw=10,
        )
        self.assertEqual(combat["inimigo"]["escudos_atuais"], 0)
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertTrue(any("Ataque: 10 + 2(DES mod) = 15 vs AC 15" in line for line in report))
        self.assertTrue(any("Resultado: SUCESSO (15 dano nos escudos → 8 para 0)" in line for line in report))

    def test_real_domain_path_preserves_naval_branches_naturals_and_reports(self):
        cases = (
            (14, 10, 15, 20, 20, 20, 20, True, "Resultado: FALHA"),
            (15, 10, 15, 20, 20, 5, 20, True, "15 dano nos escudos → 20 para 5"),
            (15, 10, 15, 0, 25, 0, 15, True, "10 dano no casco → 25 para 15"),
            (1, 20, 10, 20, 20, 20, 20, True, "Resultado: FALHA"),
            (20, 1, 99, 20, 20, 5, 20, True, "Resultado: SUCESSO"),
            (15, 10, 15, 0, 7, 0, 0, False, "Inimigo DESTRUÍDO"),
        )

        for roll, dexterity, ac, shields, hull, expected_shields, expected_hull, active, report_text in cases:
            with self.subTest(roll=roll, shields=shields, hull=hull):
                character = _character(dexterity=dexterity)
                combat = _combat(ac=ac, shields=shields, hull=hull)

                report = _fire(character, combat, roll)

                self.assertEqual(combat["inimigo"]["escudos_atuais"], expected_shields)
                self.assertEqual(combat["inimigo"]["hp_atual"], expected_hull)
                self.assertEqual(combat["combate_ativo"], active)
                self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
                self.assertEqual(combat["turno_combate"], 1)
                self.assertTrue(any(report_text in line for line in report))

    def test_returned_nonlegacy_damage_values_drive_clamped_state_and_report(self):
        cases = (
            (4, 20, {"shield_damage": 7, "hull_damage": 0}, "7 dano nos escudos → 4 para 0", 0, 20, True),
            (0, 2, {"shield_damage": 0, "hull_damage": 3}, "3 dano no casco → 2 para 0", 0, 0, False),
        )

        for shields, hull, damage, report_text, expected_shields, expected_hull, active in cases:
            with self.subTest(damage=damage):
                character = _character()
                combat = _combat(shields=shields, hull=hull)
                report: list[str] = []
                result = {
                    "d20_raw": 15,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    **damage,
                }

                with (
                    mock.patch.object(system_engine, "_roll", return_value=([15], 15, "ÚNICO", "")),
                    mock.patch.object(system_engine._me, "resolve_ship_combat", return_value=result),
                ):
                    system_engine.action_naval_fire(
                        character, combat, SimpleNamespace(), {}, report
                    )

                self.assertEqual(combat["inimigo"]["escudos_atuais"], expected_shields)
                self.assertEqual(combat["inimigo"]["hp_atual"], expected_hull)
                self.assertEqual(combat["combate_ativo"], active)
                self.assertTrue(any(report_text in line for line in report))

    def test_critical_domain_vocabulary_is_adapted_for_legacy_presentation(self):
        cases = (
            ("SUCESSO_CRITICO", 4, 0, "SUCESSO"),
            ("FALHA_CRITICA", 0, 0, "FALHA"),
        )

        for result_name, shield_damage, hull_damage, expected in cases:
            with self.subTest(result_name=result_name):
                character = _character()
                combat = _combat(shields=8)
                report: list[str] = []
                result = {
                    "d20_raw": 20 if result_name == "SUCESSO_CRITICO" else 1,
                    "total_attack": 20,
                    "check_result": result_name,
                    "shield_damage": shield_damage,
                    "hull_damage": hull_damage,
                }

                with (
                    mock.patch.object(system_engine, "_roll", return_value=([result["d20_raw"]], result["d20_raw"], "ÚNICO", "")),
                    mock.patch.object(system_engine._me, "resolve_ship_combat", return_value=result),
                ):
                    system_engine.action_naval_fire(
                        character, combat, SimpleNamespace(), {}, report
                    )

                rendered = "\n".join(report)
                self.assertIn(f"Resultado: {expected}", rendered)
                self.assertIn(f"→ {expected}", rendered)
                self.assertNotIn(result_name, rendered)

    def test_action_calls_only_the_mechanics_ship_resolver_and_applies_its_result(self):
        character = _character()
        combat = _combat(shields=6)
        report: list[str] = []
        result = {
            "d20_raw": 15,
            "total_attack": 15,
            "check_result": "SUCESSO",
            "shield_damage": 6,
            "hull_damage": 0,
        }

        with (
            mock.patch.object(system_engine, "_roll", return_value=([15], 15, "ÚNICO", "")),
            mock.patch.object(system_engine._me, "resolve_ship_combat", return_value=result) as resolve_ship_combat,
        ):
            system_engine.action_naval_fire(character, combat, SimpleNamespace(), {}, report)

        tree = ast.parse(inspect.getsource(system_engine.action_naval_fire))
        calls = [
            call for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "_me"
            and call.func.attr == "resolve_ship_combat"
        ]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("chronos.domain", inspect.getsource(system_engine.action_naval_fire))
        resolve_ship_combat.assert_called_once()
        self.assertEqual(combat["inimigo"]["escudos_atuais"], 0)
        self.assertTrue(any("6 dano nos escudos → 6 para 0" in line for line in report))
