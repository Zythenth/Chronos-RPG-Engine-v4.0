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


class LivePersonalActionIntegrationTests(unittest.TestCase):
    def test_action_has_one_direct_final_domain_delegation_and_no_local_attack_formula(self):
        source = inspect.getsource(system_engine.action_combat)
        tree = ast.parse(source)
        domain_calls = [
            call
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "_combat"
        ]
        call_names = [call.func.attr for call in domain_calls]

        self.assertEqual(call_names.count("prepare_personal_attack"), 1)
        self.assertEqual(call_names.count("resolve_personal_attack"), 1)
        self.assertNotIn("total_attack =", source)
        self.assertNotIn("d20_used == 20", source)
        self.assertNotIn("d20_used == 1", source)
        self.assertNotIn("dano_flank =", source)
        self.assertNotIn("ef_roll >=", source)

    def test_level_one_delegates_once_and_failure_does_not_roll_damage_or_effect(self):
        character = _character()
        combat = _combat()
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[([10], 10, "ÚNICO", ""), ([14], 14, "ÚNICO", "")],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]) as d20_roll,
            mock.patch.object(system_engine._d4, "rolar_d4") as player_damage,
            mock.patch.object(
                system_engine._combat.resolution,
                "resolve_check",
                wraps=system_engine._combat.resolution.resolve_check,
            ) as resolve_check,
            mock.patch.object(system_engine, "_roll_enemy_d4", return_value=1),
            mock.patch.object(
                system_engine._combat,
                "resolve_personal_attack",
                wraps=system_engine._combat.resolve_personal_attack,
            ) as resolve_personal_attack,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon="Pistola de Choque"),
                {},
                report,
            )

        resolve_personal_attack.assert_called_once()
        resolve_check.assert_called_once_with(0, 15, 14)
        player_damage.assert_not_called()
        self.assertEqual(d20_roll.call_count, 1)
        self.assertEqual(combat["inimigo"]["hp_atual"], 20)
        self.assertEqual(combat["inimigo"]["status_effects"], [])
        self.assertTrue(any("→ FALHA" in line for line in report))

    def test_level_three_delegates_twice_unless_the_first_attack_fumbles(self):
        cases = (
            (15, 18, 2, True, 2),
            (1, None, 1, False, 1),
        )

        for first_roll, second_roll, expected_calls, has_multiattack, expected_checks in cases:
            with self.subTest(first_roll=first_roll):
                character = _character()
                character["progression"]["level"] = 3
                combat = _combat()
                report: list[str] = []
                rolls = [([10], 10, "ÚNICO", ""), ([first_roll], first_roll, "ÚNICO", "")]
                if second_roll is not None:
                    rolls.append(([second_roll], second_roll, "ÚNICO", ""))

                with (
                    mock.patch.object(system_engine, "_roll", side_effect=rolls),
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[2]),
                    mock.patch.object(
                        system_engine._combat.resolution,
                        "resolve_check",
                        wraps=system_engine._combat.resolution.resolve_check,
                    ) as resolve_check,
                    mock.patch.object(system_engine, "_roll_enemy_d4", return_value=1),
                    mock.patch.object(
                        system_engine._combat,
                        "resolve_personal_attack",
                        wraps=system_engine._combat.resolve_personal_attack,
                    ) as resolve_personal_attack,
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {},
                        report,
                    )

                self.assertEqual(resolve_personal_attack.call_count, expected_calls)
                self.assertEqual(resolve_check.call_count, expected_checks)
                self.assertEqual(any("MULTI-ATAQUE" in line for line in report), has_multiattack)

    def test_final_resolver_receives_exact_live_attack_values(self):
        character = _character(dexterity=12)
        character["progression"]["level"] = 3
        combat = _combat(hull=40)
        combat["posicionamento"]["estado_atual"] = "FLANQUEANDO"
        report: list[str] = []
        preparations: list[dict] = []
        original_prepare = system_engine._combat.prepare_personal_attack

        def prepare(*args, **kwargs):
            preparation = original_prepare(*args, **kwargs)
            preparations.append(preparation)
            return preparation

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([10], 10, "ÚNICO", ""),
                    ([14], 14, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10, 12, 11]),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[2, 3]),
            mock.patch.object(system_engine, "_roll_enemy_d4", return_value=1),
            mock.patch.object(
                system_engine._combat,
                "prepare_personal_attack",
                side_effect=prepare,
            ),
            mock.patch.object(
                system_engine._combat,
                "resolve_personal_attack",
                wraps=system_engine._combat.resolve_personal_attack,
            ) as resolve_personal_attack,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon="Pistola de Choque"),
                {"ataque_bonus": 3, "dano_bonus_fixo": 4, "dano_bonus_melee": 5},
                report,
            )

        self.assertEqual(combat["inimigo"]["hp_atual"], 11)
        self.assertEqual(len(preparations), 2)
        for preparation, call, damage_roll, effect_roll in zip(
            preparations,
            resolve_personal_attack.call_args_list,
            (2, 3),
            (12, 11),
        ):
            self.assertIs(call.kwargs["preparation"], preparation)
            self.assertEqual(call.kwargs["damage_d4_raw"], damage_roll)
            self.assertEqual(call.kwargs["effect_d20_raw"], effect_roll)
            self.assertEqual(call.kwargs["weapon_damage_bonus"], 1)
            self.assertEqual(call.kwargs["fixed_damage_bonus"], 4)
            self.assertEqual(call.kwargs["melee_damage_bonus"], 5)
            self.assertEqual(call.kwargs["position"], "FLANQUEANDO")
            self.assertEqual(call.kwargs["weapon_effect"], "atordoamento")
            self.assertEqual(call.kwargs["weapon_effect_dc"], 12)

    def test_successful_weapon_multiattack_keeps_cross_boundary_random_order(self):
        character = _character()
        character["progression"]["level"] = 3
        combat = _combat(hull=100)
        events: list[str] = []
        report: list[str] = []
        original_prepare = system_engine._combat.prepare_personal_attack
        original_resolve = system_engine._combat.resolve_personal_attack
        player_labels = iter(("player initiative", "attack one", "attack two"))
        player_rolls = iter(
            (([10], 10, "ÚNICO", ""), ([15], 15, "ÚNICO", ""), ([19], 19, "ÚNICO", ""))
        )
        d20_labels = iter(("enemy initiative", "effect one", "effect two"))
        d20_rolls = iter((10, 12, 12))
        d4_labels = iter(("damage one", "damage two"))
        d4_rolls = iter((2, 3))
        preparation_count = 0
        final_count = 0

        def player_roll(*_args):
            events.append(next(player_labels))
            return next(player_rolls)

        def d20_roll():
            events.append(next(d20_labels))
            return next(d20_rolls)

        def d4_roll():
            events.append(next(d4_labels))
            return next(d4_rolls)

        def prepare(*args, **kwargs):
            nonlocal preparation_count
            preparation_count += 1
            events.append(f"prepare {preparation_count}")
            return original_prepare(*args, **kwargs)

        def resolve(*args, **kwargs):
            nonlocal final_count
            final_count += 1
            events.append(f"final {final_count}")
            return original_resolve(*args, **kwargs)

        def enemy_d4():
            events.append("enemy damage")
            return 1

        with (
            mock.patch.object(system_engine, "_roll", side_effect=player_roll),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=d20_roll),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=d4_roll),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=enemy_d4),
            mock.patch.object(system_engine._combat, "prepare_personal_attack", side_effect=prepare),
            mock.patch.object(system_engine._combat, "resolve_personal_attack", side_effect=resolve),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon="Pistola de Choque"),
                {},
                report,
            )

        self.assertEqual(
            events,
            [
                "player initiative",
                "enemy initiative",
                "attack one",
                "prepare 1",
                "damage one",
                "effect one",
                "final 1",
                "attack two",
                "prepare 2",
                "damage two",
                "effect two",
                "final 2",
                "enemy damage",
            ],
        )

    def test_final_domain_result_governs_damage_effect_flank_total_and_hud(self):
        character = _character()
        combat = _combat(hull=20)
        combat["posicionamento"]["estado_atual"] = "FLANQUEANDO"
        report: list[str] = []
        preparation = {
            "d20_raw": 15,
            "total_attack": 15,
            "check_result": "SUCESSO",
            "outcome": "SUCESSO",
            "is_critical": False,
            "requires_damage_roll": True,
            "requires_effect_roll": True,
        }
        final_result = {
            **preparation,
            "d4_raw": 1,
            "effective_d4_damage": 1,
            "weapon_bonus": 0,
            "fixed_damage_bonus": 0,
            "melee_damage_bonus": 0,
            "flanking_damage_bonus": 8,
            "damage_dealt": 6,
            "effect_d20_raw": 1,
            "effect_dc": 99,
            "effect_eligible": True,
            "effect_applied": "queimadura",
            "total_attack": 99,
        }

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[([10], 10, "ÚNICO", ""), ([15], 15, "ÚNICO", "")],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10, 1]),
            mock.patch.object(system_engine._d4, "rolar_d4", return_value=1),
            mock.patch.object(system_engine, "_roll_enemy_d4", return_value=1),
            mock.patch.object(
                system_engine._combat,
                "prepare_personal_attack",
                return_value=preparation,
            ),
            mock.patch.object(
                system_engine._combat,
                "resolve_personal_attack",
                return_value=final_result,
            ) as resolve_personal_attack,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon="Pistola de Choque"),
                {},
                report,
            )

        resolve_personal_attack.assert_called_once()
        resolve_personal_attack.assert_called_once_with(
            preparation=preparation,
            damage_d4_raw=1,
            weapon_damage_bonus=1,
            fixed_damage_bonus=0,
            melee_damage_bonus=0,
            position="FLANQUEANDO",
            weapon_effect="atordoamento",
            weapon_effect_dc=12,
            effect_d20_raw=1,
        )
        self.assertEqual(combat["inimigo"]["hp_atual"], 14)
        self.assertEqual(
            combat["inimigo"]["status_effects"],
            [{"id": "queimadura", "stacks": 1, "turno_restante": 3}],
        )
        rendered = "\n".join(report)
        self.assertIn("★ FLANQUEANDO: +8 dano de flanqueio", rendered)
        self.assertIn("Efeito aplicado: queimadura (roll=1 vs DC99)", rendered)
        self.assertIn("= 99 vs DC 15 → SUCESSO", rendered)
        self.assertIn("DADO_D20  : 15 + 0(DES mod) = 99 vs DC 15 → SUCESSO", rendered)
