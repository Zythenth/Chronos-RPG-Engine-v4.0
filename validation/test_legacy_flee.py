"""Characterization tests for the legacy ``action_flee`` public contract."""

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

import system_engine


def _character(dexterity: int = 10, hp: int = 20) -> dict:
    return {
        "meta": {"last_updated": "TURNO_0"},
        "identity": {"name": "Ferro", "status": "STABLE"},
        "vitals": {
            "hp": {"current": hp, "max": 20},
            "oxygen_level": {"current": 100, "max": 100},
            "energy_reserves": {"current": 10, "max": 100},
            "fome": {"current": 100, "max": 100},
            "sede": {"current": 100, "max": 100},
            "exaustao": {"current": 100, "max": 100},
        },
        "attributes": {
            "forca": {"value": 10},
            "destreza": {"value": dexterity},
        },
        "active_status_effects": [{"id": "veneno", "stacks": 1, "turno_restante": 2}],
        "progression": {"level": 1, "xp_current": 7, "xp_to_next_level": 100},
    }


def _combat(active: bool = True, armor: str | None = None, racial: int = 0) -> dict:
    return {
        "combate_ativo": active,
        "turno_combate": 4,
        "jogador": {"arma_equipada": None, "armadura_equipada": armor},
        "posicionamento": {"estado_atual": "MELEE"},
        "inimigo": {
            "nome": "Sentinela de Teste",
            "hp_atual": 20,
            "hp_maximo": 20,
            "dc_defesa": 15,
            "ac": 15,
            "escudos_atuais": 0,
            "velocidade": 100,
            "damage_bonus_racial": racial,
            "tipo_dano": "Físico",
            "status_effects": ["marcado"],
            "ficha_racial": {"drop": "Sucata", "pode_fugir": False, "dc_moral": 10},
        },
    }


def _hud(
    hp: int,
    rolls: list[int],
    used: int,
    criterion: str,
    suffix: str,
    dexterity: int,
    total: int,
    outcome: str,
    active: bool,
) -> str:
    if active:
        enemy = "│ INIMIGO: Sentinela de Teste   HP 20 / 20"
    else:
        enemy = "│ INIMIGO: —                    HP —"
    status = "DECEASED" if hp == 0 else "STABLE"
    suffix_label = f"({suffix})" if suffix else ""
    return (
        "\n6. HUD\n"
        "┌─────────────────────────────────────────────────────┐\n"
        f"│ HP {hp:>3}/20   O2 100%  EN  10%  Nv 1\n"
        "│ XP 7/100\n"
        "│ FOME 100%  SEDE 100%  EXAUSTÃO 100%\n"
        f"{enemy}\n"
        "├─────────────────────────────────────────────────────┤\n"
        f"│ D20_ROLLS : {rolls} → USADO: {used} ({criterion})\n"
        f"│ DADO_D20  : {used} + {dexterity - 10}(DES mod{suffix_label}) = {total} vs DC 15 → {outcome}\n"
        "│ D4_PLAYER : N/A\n"
        "│ D4_ENEMY  : N/A\n"
        "└─────────────────────────────────────────────────────┘\n"
        f"7. STATUS FINAL: {status}"
    )


def _expected_report(
    *,
    rolls: list[int],
    used: int,
    criterion: str,
    suffix: str,
    dexterity: int,
    total: int,
    outcome: str,
    hp_after: int,
    hp_before: int | None = None,
    d4: int | None = None,
    racial: int = 0,
    damage: int = 0,
    active: bool,
) -> list[str]:
    suffix_label = f"({suffix})" if suffix else ""
    report = [
        "\n2. SCRIPTS",
        f"   D20 {dexterity}{suffix_label}: {rolls} → USADO: {used} ({criterion})",
        f"   Total: {used} + {dexterity - 10}(DES mod) = {total} vs DC 15 → {outcome}",
        f"\n3. RESULTADO: {outcome}",
    ]
    if active:
        report.extend(
            (
                f"   Fuga falhou. Inimigo golpeia: D4[{d4}]+{racial}={d4 + racial} → -{damage} HP",
                "\n4. DELTAS — JOGADOR",
                f"   HP: {hp_before if hp_before is not None else hp_after + damage} → {hp_after} (-{damage})",
            )
        )
    else:
        report.extend(
            (
                "   Fuga bem-sucedida. combate_ativo → false",
                "   NOTA: Nenhum drop. Inimigo permanece vivo.",
            )
        )
    report.append(_hud(hp_after, rolls, used, criterion, suffix, dexterity, total, outcome, active))
    return report


def _expected_state(
    character_before: dict,
    combat_before: dict,
    *,
    hp_after: int,
    combat_active: bool,
) -> tuple[dict, dict]:
    character = copy.deepcopy(character_before)
    combat = copy.deepcopy(combat_before)
    character["vitals"]["hp"]["current"] = hp_after
    character["identity"]["status"] = "DECEASED" if hp_after == 0 else "STABLE"
    character["meta"]["last_updated"] = "TURNO_1"
    combat["combate_ativo"] = combat_active
    return character, combat


class LegacyFleeCharacterizationTests(unittest.TestCase):
    def test_inactive_guard_has_no_roll_hud_or_state_side_effects(self):
        """Detects a guard bypass before the legacy action performs any work."""
        character = _character()
        combat = _combat(active=False)
        before_character = copy.deepcopy(character)
        before_combat = copy.deepcopy(combat)
        report: list[str] = []

        with (
            mock.patch.object(system_engine._mr, "rolar") as flee_roll,
            mock.patch.object(system_engine, "_roll_enemy_d4") as enemy_roll,
            mock.patch.object(system_engine, "_print_hud") as hud,
        ):
            system_engine.action_flee(character, combat, SimpleNamespace(), {}, report)

        self.assertEqual(report, ["ERRO: Nenhum combate ativo."])
        self.assertEqual(character, before_character)
        self.assertEqual(combat, before_combat)
        flee_roll.assert_not_called()
        enemy_roll.assert_not_called()
        hud.assert_not_called()

    def test_roll_resolution_keeps_dc_modifier_stealth_and_natural_precedence(self):
        """Detects DC/modifier/stealth drift and natural-result precedence drift."""
        cases = (
            ([7, 12, 9], 12, "MELHOR", "(+2)", 12, 1, 15, "SUCESSO", 20, False),
            ([20, 1], 20, "MELHOR", "", 10, -100, -80, "SUCESSO CRÍTICO", 20, False),
            ([14, 4], 14, "MELHOR", "", 10, 0, 14, "FALHA", 19, True),
            ([1, 1, 1, 1, 1, 1, 1], 1, "MELHOR", "(+10)", 20, 100, 111, "FALHA CRÍTICA", 19, True),
            ([14, 5], 5, "PIOR", "(-3)", 7, 13, 15, "SUCESSO", 20, False),
            ([17], 17, "ÚNICO", "(-2)", 8, 0, 15, "SUCESSO", 20, False),
        )

        for rolls, used, criterion, suffix, dexterity, stealth, total, outcome, hp_after, enemy_hits in cases:
            with self.subTest(used=used, dexterity=dexterity, stealth=stealth):
                character = _character(dexterity=dexterity)
                combat = _combat()
                character_before = copy.deepcopy(character)
                combat_before = copy.deepcopy(combat)
                events: list[str] = []
                report: list[str] = []

                def multi_roll(faces, count):
                    events.append("flee d20")
                    self.assertEqual((faces, count), (20, len(rolls)))
                    return rolls

                def enemy_roll():
                    events.append("enemy d4")
                    return 1

                with (
                    mock.patch.object(
                        system_engine._mr,
                        "rolar",
                        side_effect=multi_roll,
                    ) as flee_roll,
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=enemy_roll) as enemy_d4,
                    mock.patch.object(
                        system_engine,
                        "_apply_player_status",
                        wraps=system_engine._apply_player_status,
                    ) as player_status,
                ):
                    system_engine.action_flee(
                        character,
                        combat,
                        SimpleNamespace(),
                        {"skill_bonuses": {"stealth": stealth}},
                        report,
                    )

                expected = _expected_report(
                    rolls=rolls,
                    used=used,
                    criterion=criterion,
                    suffix=suffix,
                    dexterity=dexterity,
                    total=total,
                    outcome=outcome,
                    hp_after=hp_after,
                    d4=1,
                    damage=1,
                    active=enemy_hits,
                )
                self.assertEqual(report, expected)
                self.assertEqual(
                    report[2],
                    f"   Total: {used} + {dexterity - 10}(DES mod) = {total} vs DC 15 → {outcome}",
                )
                self.assertNotIn("stealth", report[2].lower())
                flee_roll.assert_called_once_with(20, len(rolls))
                if enemy_hits:
                    enemy_d4.assert_called_once_with()
                else:
                    enemy_d4.assert_not_called()
                player_status.assert_not_called()
                self.assertEqual(events, ["flee d20"] + (["enemy d4"] if enemy_hits else []))
                expected_character, expected_combat = _expected_state(
                    character_before,
                    combat_before,
                    hp_after=hp_after,
                    combat_active=enemy_hits,
                )
                self.assertEqual(character, expected_character)
                self.assertEqual(combat, expected_combat)

    def test_success_changes_only_combat_flag_and_uses_legacy_hud_presentation(self):
        """Detects success-side-effect drift, including rewards or combat bookkeeping."""
        character = _character(dexterity=12)
        combat = _combat()
        character_before = copy.deepcopy(character)
        combat_before = copy.deepcopy(combat)
        report: list[str] = []

        with (
            mock.patch.object(system_engine._mr, "rolar", return_value=[7, 12, 9]) as flee_roll,
            mock.patch.object(system_engine, "_roll_enemy_d4") as enemy_roll,
            mock.patch.object(
                system_engine,
                "_apply_player_status",
                wraps=system_engine._apply_player_status,
            ) as player_status,
            mock.patch.object(
                system_engine,
                "_print_hud",
                wraps=system_engine._print_hud,
            ) as hud,
        ):
            system_engine.action_flee(
                character,
                combat,
                SimpleNamespace(),
                {"skill_bonuses": {"stealth": 1}},
                report,
            )

        self.assertEqual(
            report,
            _expected_report(
                rolls=[7, 12, 9],
                used=12,
                criterion="MELHOR",
                suffix="(+2)",
                dexterity=12,
                total=15,
                outcome="SUCESSO",
                hp_after=20,
                active=False,
            ),
        )
        flee_roll.assert_called_once_with(20, 3)
        expected_character, expected_combat = _expected_state(
            character_before, combat_before, hp_after=20, combat_active=False
        )
        self.assertEqual(character, expected_character)
        self.assertEqual(combat, expected_combat)
        self.assertNotIn("Moral", "\n".join(report))
        enemy_roll.assert_not_called()
        player_status.assert_not_called()
        hud.assert_called_once_with(
            character,
            combat,
            [7, 12, 9],
            12,
            "MELHOR",
            "(+2)",
            12,
            "DES",
            [],
            None,
            None,
            0,
            0,
            0,
            15,
            15,
            "SUCESSO",
            report,
        )

    def test_failed_retaliation_keeps_legacy_arithmetic_order_hp_write_and_hud_zeros(self):
        """Detects retaliation arithmetic/order/HP/HUD drift and combat-only mechanics."""
        cases = (
            (4, 3, 5, 15),
            (1, 0, 0, 20),
        )

        for d4, racial, damage, hp_after in cases:
            with self.subTest(d4=d4, racial=racial):
                character = _character()
                combat = _combat(armor="Armadura de Couro", racial=racial)
                character_before = copy.deepcopy(character)
                combat_before = copy.deepcopy(combat)
                events: list[str] = []
                report: list[str] = []
                original_set_vital = system_engine.set_vital

                def flee_roll(faces, count):
                    events.append("flee d20")
                    self.assertEqual((faces, count), (20, 2))
                    return [14, 4]

                def enemy_roll():
                    events.append("enemy d4")
                    return d4

                with (
                    mock.patch.object(system_engine._mr, "rolar", side_effect=flee_roll) as multi_roll,
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=enemy_roll) as d4_roll,
                    mock.patch.object(
                        system_engine,
                        "_apply_player_status",
                        wraps=system_engine._apply_player_status,
                    ) as player_status,
                    mock.patch.object(
                        system_engine,
                        "set_vital",
                        wraps=original_set_vital,
                    ) as hp_write,
                    mock.patch.object(
                        system_engine,
                        "_print_hud",
                        wraps=system_engine._print_hud,
                    ) as hud,
                ):
                    system_engine.action_flee(
                        character,
                        combat,
                        SimpleNamespace(),
                        {"dano_reducao_fisica": 99},
                        report,
                    )

                self.assertEqual(
                    report,
                    _expected_report(
                        rolls=[14, 4],
                        used=14,
                        criterion="MELHOR",
                        suffix="",
                        dexterity=10,
                        total=14,
                        outcome="FALHA",
                        hp_after=hp_after,
                        d4=d4,
                        racial=racial,
                        damage=damage,
                        active=True,
                    ),
                )
                self.assertEqual(events, ["flee d20", "enemy d4"])
                multi_roll.assert_called_once_with(20, 2)
                d4_roll.assert_called_once_with()
                player_status.assert_not_called()
                hp_write.assert_called_once_with(character, "hp", 20 - damage)
                expected_character, expected_combat = _expected_state(
                    character_before, combat_before, hp_after=hp_after, combat_active=True
                )
                self.assertEqual(character, expected_character)
                self.assertEqual(combat, expected_combat)
                self.assertNotIn("Moral", "\n".join(report))
                self.assertEqual(hud.call_args.args[11:14], (0, 0, 0))
                self.assertIn("│ D4_ENEMY  : N/A", report[-1])

    def test_zero_and_overkill_clamp_hp_without_last_breath_or_combat_completion(self):
        """Detects zero-HP handling drift, including Last Breath or completion processing."""
        for hp_before in (6, 4):
            with self.subTest(hp_before=hp_before):
                character = _character(hp=hp_before)
                combat = _combat(racial=2)
                character_before = copy.deepcopy(character)
                combat_before = copy.deepcopy(combat)
                report: list[str] = []
                original_set_vital = system_engine.set_vital

                with (
                    mock.patch.object(system_engine._mr, "rolar", return_value=[14, 4]) as multi_roll,
                    mock.patch.object(system_engine, "_roll_enemy_d4", return_value=4),
                    mock.patch.object(
                        system_engine,
                        "_apply_player_status",
                        wraps=system_engine._apply_player_status,
                    ) as player_status,
                    mock.patch.object(
                        system_engine,
                        "set_vital",
                        wraps=original_set_vital,
                    ) as hp_write,
                ):
                    system_engine.action_flee(
                        character,
                        combat,
                        SimpleNamespace(),
                        {
                            "dano_reducao_fisica": 99,
                            "ultimo_suspiro_disponivel": True,
                        },
                        report,
                    )

                self.assertEqual(
                    report,
                    _expected_report(
                        rolls=[14, 4],
                        used=14,
                        criterion="MELHOR",
                        suffix="",
                        dexterity=10,
                        total=14,
                        outcome="FALHA",
                        hp_after=0,
                        hp_before=hp_before,
                        d4=4,
                        racial=2,
                        damage=6,
                        active=True,
                    ),
                )
                multi_roll.assert_called_once_with(20, 2)
                player_status.assert_not_called()
                hp_write.assert_called_once_with(character, "hp", hp_before - 6)
                self.assertEqual(character["vitals"]["hp"]["current"], 0)
                expected_character, expected_combat = _expected_state(
                    character_before, combat_before, hp_after=0, combat_active=True
                )
                self.assertEqual(character, expected_character)
                self.assertEqual(combat, expected_combat)
                self.assertNotIn("ÚLTIMO SUSPIRO", "\n".join(report))
                self.assertNotIn("Moral", "\n".join(report))


if __name__ == "__main__":
    unittest.main()
