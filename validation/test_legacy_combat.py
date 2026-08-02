"""Stage 2C-A characterization tests for current legacy combat behavior.

The legacy helpers and the live action flows are deliberately tested separately:
their similar-looking rules currently have distinct public contracts that must stay
stable until the approved extraction work begins.
"""

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


MORAL_FLEE_THRESHOLD = 0.30
FLANQUEAR_DAMAGE_BONUS = 2
MULTI_ATTACK_MIN_LEVEL = 3
MULTI_ATTACK_PENALTY = -4
ARMOR_DAMAGE_REDUCTION = 2
SHIP_DAMAGE_ON_SHIELDS = 15
SHIP_DAMAGE_ON_HULL = 10

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


def _character() -> dict:
    """Return isolated in-memory state sufficient for the action HUD."""
    return {
        "meta": {"last_updated": "TURNO_0"},
        "identity": {"name": "Ferro", "status": "STABLE"},
        "vitals": {
            "hp": {"current": 20, "max": 20},
            "oxygen_level": {"current": 100, "max": 100},
            "energy_reserves": {"current": 10, "max": 100},
            "hull_integrity": {"current": 100, "max": 100},
            "fome": {"current": 100, "max": 100},
            "sede": {"current": 100, "max": 100},
            "exaustao": {"current": 100, "max": 100},
        },
        "attributes": {
            "forca": {"value": 10},
            "destreza": {"value": 10},
        },
        "progression": {
            "level": 1,
            "xp_current": 0,
            "xp_to_next_level": 100,
        },
    }


def _combat() -> dict:
    """Return isolated active combat state for either combat action."""
    return {
        "combate_ativo": True,
        "turno_combate": 0,
        "jogador": {"arma_equipada": None, "armadura_equipada": None},
        "posicionamento": {"estado_atual": "MELEE"},
        "inimigo": {
            "nome": "Sentinela de Teste",
            "hp_atual": 20,
            "hp_maximo": 20,
            "dc_defesa": 15,
            "ac": 15,
            "escudos_atuais": 0,
            "velocidade": 0,
            "damage_bonus_racial": 0,
            "tipo_dano": "Físico",
            "status_effects": [],
            "ficha_racial": {
                "drop": "Sucata",
                "pode_fugir": False,
                "dc_moral": 10,
            },
        },
    }


class LegacyCombatCharacterizationTests(unittest.TestCase):
    def test_legacy_armor_lookup_preserves_none_registered_and_unknown_cases(self):
        """Armor lookup keeps its current zero, registered, and fallback branches."""
        self.assertEqual(mechanics_engine.get_armor_reduction(None), 0)
        self.assertEqual(
            mechanics_engine.get_armor_reduction("Armadura de Couro"),
            ARMOR_DAMAGE_REDUCTION,
        )
        self.assertEqual(
            mechanics_engine.get_armor_reduction("Armadura Não Catalogada"),
            ARMOR_DAMAGE_REDUCTION,
        )

    def test_legacy_personal_success_weapon_armor_and_threshold_effect(self):
        """An ordinary hit adds weapon damage, reduces damage taken, and accepts effect DC equality."""
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
                "damage_reduction": ARMOR_DAMAGE_REDUCTION,
                "damage_taken": 5,
                "effect_applied": "sangramento",
            },
        )

    def test_legacy_personal_failure_uses_unknown_weapon_and_clamps_damage_taken(self):
        """A failed attack still applies fallback armor reduction and clamps incoming damage at zero."""
        result = mechanics_engine.resolve_personal_combat(
            player_attr=0,
            enemy_dc=15,
            enemy_damage=1,
            attack_d20_raw=14,
            damage_d4_raw=4,
            armor_name="Armadura Não Catalogada",
            weapon_name="Arma Não Catalogada",
            effect_d20_raw=20,
        )

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(
            result,
            {
                "d20_raw": 14,
                "total_attack": 14,
                "check_result": "FALHA",
                "is_critical": False,
                "d4_raw": 4,
                "weapon_bonus": 0,
                "damage_dealt": 0,
                "damage_reduction": ARMOR_DAMAGE_REDUCTION,
                "damage_taken": 0,
                "effect_applied": None,
            },
        )

    def test_legacy_personal_natural_twenty_doubles_d4_and_accepts_low_effect_roll(self):
        """A natural 20 overrides the total, doubles d4 damage, and bypasses the weapon effect DC."""
        result = mechanics_engine.resolve_personal_combat(
            player_attr=-100,
            enemy_dc=30,
            enemy_damage=6,
            attack_d20_raw=20,
            damage_d4_raw=3,
            weapon_name="Rifle Energético",
            effect_d20_raw=1,
        )

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(
            result,
            {
                "d20_raw": 20,
                "total_attack": -80,
                "check_result": "SUCESSO_CRITICO",
                "is_critical": True,
                "d4_raw": 3,
                "weapon_bonus": 2,
                "damage_dealt": 8,
                "damage_reduction": 0,
                "damage_taken": 6,
                "effect_applied": "queimadura",
            },
        )

    def test_legacy_personal_natural_one_is_critical_failure_and_stun_blocks_damage(self):
        """A natural 1 overrides a passing total, while a stunned enemy deals no return damage."""
        result = mechanics_engine.resolve_personal_combat(
            player_attr=100,
            enemy_dc=-10,
            enemy_damage=99,
            attack_d20_raw=1,
            damage_d4_raw=4,
            weapon_name="Lança Primitiva",
            enemy_is_stunned=True,
            effect_d20_raw=20,
        )

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(
            result,
            {
                "d20_raw": 1,
                "total_attack": 101,
                "check_result": "FALHA_CRITICA",
                "is_critical": False,
                "d4_raw": 4,
                "weapon_bonus": 1,
                "damage_dealt": 0,
                "damage_reduction": 0,
                "damage_taken": 0,
                "effect_applied": None,
            },
        )

    def test_legacy_personal_effect_rejects_roll_below_its_dc(self):
        """A noncritical hit leaves the status absent when its raw effect roll is below DC 13."""
        result = mechanics_engine.resolve_personal_combat(
            player_attr=0,
            enemy_dc=15,
            enemy_damage=2,
            attack_d20_raw=15,
            damage_d4_raw=1,
            weapon_name="Lança Primitiva",
            effect_d20_raw=12,
        )

        self.assertEqual(list(result), PERSONAL_RESULT_KEYS)
        self.assertEqual(
            result,
            {
                "d20_raw": 15,
                "total_attack": 15,
                "check_result": "SUCESSO",
                "is_critical": False,
                "d4_raw": 1,
                "weapon_bonus": 1,
                "damage_dealt": 2,
                "damage_reduction": 0,
                "damage_taken": 2,
                "effect_applied": None,
            },
        )

    def test_legacy_ship_combat_preserves_damage_branches_and_natural_outcomes(self):
        """Legacy naval resolution has fixed shield/hull damage and natural-roll overrides."""
        cases = (
            (
                "shield hit",
                dict(player_piloting=3, enemy_ac=15, enemy_shields=8, d20_raw=12),
                {
                    "d20_raw": 12,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    "shield_damage": SHIP_DAMAGE_ON_SHIELDS,
                    "hull_damage": 0,
                },
            ),
            (
                "hull hit at zero shields",
                dict(player_piloting=3, enemy_ac=15, enemy_shields=0, d20_raw=12),
                {
                    "d20_raw": 12,
                    "total_attack": 15,
                    "check_result": "SUCESSO",
                    "shield_damage": 0,
                    "hull_damage": SHIP_DAMAGE_ON_HULL,
                },
            ),
            (
                "ordinary miss",
                dict(player_piloting=0, enemy_ac=15, enemy_shields=8, d20_raw=14),
                {
                    "d20_raw": 14,
                    "total_attack": 14,
                    "check_result": "FALHA",
                    "shield_damage": 0,
                    "hull_damage": 0,
                },
            ),
            (
                "natural one",
                dict(player_piloting=100, enemy_ac=-10, enemy_shields=8, d20_raw=1),
                {
                    "d20_raw": 1,
                    "total_attack": 101,
                    "check_result": "FALHA_CRITICA",
                    "shield_damage": 0,
                    "hull_damage": 0,
                },
            ),
            (
                "natural twenty",
                dict(player_piloting=-100, enemy_ac=30, enemy_shields=8, d20_raw=20),
                {
                    "d20_raw": 20,
                    "total_attack": -80,
                    "check_result": "SUCESSO_CRITICO",
                    "shield_damage": SHIP_DAMAGE_ON_SHIELDS,
                    "hull_damage": 0,
                },
            ),
        )

        for branch, inputs, expected in cases:
            with self.subTest(branch=branch):
                result = mechanics_engine.resolve_ship_combat(**inputs)
                self.assertEqual(list(result), SHIP_RESULT_KEYS)
                self.assertEqual(result, expected)


class LiveCombatActionCharacterizationTests(unittest.TestCase):
    def test_action_combat_inactive_refuses_without_state_mutation(self):
        """The inactive guard returns before the action mutates either in-memory state object."""
        character = _character()
        combat = _combat()
        combat["combate_ativo"] = False
        before_character = copy.deepcopy(character)
        before_combat = copy.deepcopy(combat)
        report: list[str] = []

        system_engine.action_combat(
            character,
            combat,
            SimpleNamespace(position="FLANQUEANDO", weapon="Lança Primitiva"),
            {},
            report,
        )

        self.assertEqual(character, before_character)
        self.assertEqual(combat, before_combat)
        self.assertTrue(any("Nenhum combate ativo" in line for line in report))

    def test_action_combat_updates_position_and_initiative_tie_favors_ferro(self):
        """A supplied position is persisted and equal initiative totals give Ferro the first turn."""
        character = _character()
        combat = _combat()
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ) as player_roll,
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]) as enemy_initiative,
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position="FLANQUEANDO", weapon=None),
                {},
                report,
            )

        self.assertEqual(combat["posicionamento"]["estado_atual"], "FLANQUEANDO")
        self.assertEqual(character["vitals"]["hp"]["current"], 19)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 2)
        self.assertEqual(enemy_initiative.call_count, 1)
        enemy_damage.assert_called_once_with()
        self.assertTrue(any("FERRO ataca PRIMEIRO" in line for line in report))

    def test_action_combat_enemy_initiative_multiplier_follows_reductions(self):
        """Enemy-first initiative applies int(x * 1.5) only after armor and physical-passive reduction."""
        character = _character()
        combat = _combat()
        combat["jogador"]["armadura_equipada"] = "Armadura de Couro"
        combat["inimigo"]["damage_bonus_racial"] = 2
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[11]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[4]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {"dano_reducao_fisica": 1},
                report,
            )

        # (4 enemy d4 + 2 racial - 2 armor - 1 passive) * 1.5 -> int(4.5) == 4.
        self.assertEqual(character["vitals"]["hp"]["current"], 16)
        self.assertTrue(any("dano ×1.5" in line for line in report))

    def test_action_combat_physical_passive_requires_exact_accented_damage_type(self):
        """The passive reduction is applied only when tipo_dano is exactly the current 'Físico' spelling."""
        cases = (("Físico", 19), ("Fisico", 16))

        for damage_type, expected_hp in cases:
            with self.subTest(damage_type=damage_type):
                character = _character()
                combat = _combat()
                combat["inimigo"]["tipo_dano"] = damage_type
                report: list[str] = []

                with (
                    mock.patch.object(
                        system_engine,
                        "_roll",
                        side_effect=[
                            ([10], 10, "ÚNICO", ""),
                            ([1], 1, "ÚNICO", ""),
                        ],
                    ) as player_roll,
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[4]),
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {"dano_reducao_fisica": 3},
                        report,
                    )

                self.assertEqual(character["vitals"]["hp"]["current"], expected_hp)
                self.assertEqual(player_roll.call_count, 2)

    def test_action_combat_success_failure_and_critical_damage_branches(self):
        """Ordinary success/failure and natural-20 critical branches retain their separate damage rules."""
        cases = (
            ("ordinary success", 15, "SUCESSO", 3, 27, 1),
            ("ordinary failure", 14, "FALHA", 3, 30, 0),
            ("natural twenty", 20, "SUCESSO CRÍTICO", 3, 24, 1),
        )

        for branch, attack_raw, expected_outcome, d4_raw, expected_enemy_hp, d4_calls in cases:
            with self.subTest(branch=branch):
                character = _character()
                combat = _combat()
                combat["inimigo"]["hp_atual"] = 30
                combat["inimigo"]["hp_maximo"] = 30
                report: list[str] = []

                with (
                    mock.patch.object(
                        system_engine,
                        "_roll",
                        side_effect=[
                            ([10], 10, "ÚNICO", ""),
                            ([attack_raw], attack_raw, "ÚNICO", ""),
                        ],
                    ) as player_roll,
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[d4_raw]) as player_damage,
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {},
                        report,
                    )

                self.assertEqual(combat["inimigo"]["hp_atual"], expected_enemy_hp)
                self.assertEqual(character["vitals"]["hp"]["current"], 19)
                self.assertEqual(player_roll.call_count, 2)
                self.assertEqual(player_damage.call_count, d4_calls)
                self.assertTrue(any(expected_outcome in line for line in report))

    def test_action_combat_fumble_suppresses_second_attack_at_multiattack_level(self):
        """A natural-1 first attack at level 3 does not consume a second attack or player damage roll."""
        character = _character()
        character["progression"]["level"] = MULTI_ATTACK_MIN_LEVEL
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ) as player_roll,
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[4]) as player_damage,
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(combat["inimigo"]["hp_atual"], 30)
        self.assertEqual(player_roll.call_count, 2)
        player_damage.assert_not_called()
        self.assertFalse(any("MULTI-ATAQUE" in line for line in report))

    def test_action_combat_multiattack_starts_at_level_three_with_minus_four_penalty(self):
        """Level 2 has one attack; level 3 gets a second whose -4 turns raw 18 into a failure."""
        cases = (
            (MULTI_ATTACK_MIN_LEVEL - 1, 2, 28, False),
            (MULTI_ATTACK_MIN_LEVEL, 3, 28, True),
        )

        for level, expected_roll_calls, expected_enemy_hp, has_multiattack in cases:
            with self.subTest(level=level):
                character = _character()
                character["progression"]["level"] = level
                combat = _combat()
                combat["inimigo"]["hp_atual"] = 30
                combat["inimigo"]["hp_maximo"] = 30
                report: list[str] = []
                roll_sequence = [
                    ([10], 10, "ÚNICO", ""),
                    ([15], 15, "ÚNICO", ""),
                ]
                if level == MULTI_ATTACK_MIN_LEVEL:
                    roll_sequence.append(([18], 18, "ÚNICO", ""))

                with (
                    mock.patch.object(system_engine, "_roll", side_effect=roll_sequence) as player_roll,
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[2]) as player_damage,
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {},
                        report,
                    )

                self.assertEqual(combat["inimigo"]["hp_atual"], expected_enemy_hp)
                self.assertEqual(player_roll.call_count, expected_roll_calls)
                self.assertEqual(player_damage.call_count, 1)
                self.assertEqual(
                    any("MULTI-ATAQUE" in line for line in report),
                    has_multiattack,
                )
                if has_multiattack:
                    self.assertTrue(any("(pen -4) = 14 vs DC 15 → FALHA" in line for line in report))

    def test_action_combat_melee_and_flank_bonuses_are_position_specific(self):
        """Melee damage applies only in MELEE/FLANQUEANDO, while flanking independently adds two damage."""
        cases = (
            ("MELEE", 5),
            ("FLANQUEANDO", 2 + 3 + FLANQUEAR_DAMAGE_BONUS),
            ("DISTANCIA", 2),
            ("COBERTO", 2),
        )

        for position, expected_damage in cases:
            with self.subTest(position=position):
                character = _character()
                combat = _combat()
                combat["posicionamento"]["estado_atual"] = position
                combat["inimigo"]["hp_atual"] = 30
                combat["inimigo"]["hp_maximo"] = 30
                report: list[str] = []

                with (
                    mock.patch.object(
                        system_engine,
                        "_roll",
                        side_effect=[
                            ([10], 10, "ÚNICO", ""),
                            ([15], 15, "ÚNICO", ""),
                        ],
                    ) as player_roll,
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[2]) as player_damage,
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {"dano_bonus_melee": 3},
                        report,
                    )

                self.assertEqual(combat["inimigo"]["hp_atual"], 30 - expected_damage)
                self.assertEqual(player_roll.call_count, 2)
                player_damage.assert_called_once_with()

    def test_action_combat_attack_and_fixed_damage_bonuses_use_their_separate_steps(self):
        """Attack bonus turns raw 14 into a hit, then fixed damage is added after d4."""
        character = _character()
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([14], 14, "ÚNICO", ""),
                ],
            ) as player_roll,
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[2]) as player_damage,
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {"ataque_bonus": 1, "dano_bonus_fixo": 3},
                report,
            )

        self.assertEqual(combat["inimigo"]["hp_atual"], 25)
        self.assertEqual(player_roll.call_count, 2)
        player_damage.assert_called_once_with()
        self.assertTrue(any("→ SUCESSO" in line for line in report))

    def test_action_combat_weapon_effect_accepts_and_rejects_raw_effect_rolls(self):
        """Pistola de Choque applies its status at 12 and leaves state unchanged below that DC."""
        cases = ((12, [{"id": "atordoamento", "stacks": 1, "turno_restante": 1}], True), (11, [], False))

        for effect_roll, expected_statuses, effect_message in cases:
            with self.subTest(effect_roll=effect_roll):
                character = _character()
                combat = _combat()
                combat["inimigo"]["hp_atual"] = 30
                combat["inimigo"]["hp_maximo"] = 30
                report: list[str] = []

                with (
                    mock.patch.object(
                        system_engine,
                        "_roll",
                        side_effect=[
                            ([10], 10, "ÚNICO", ""),
                            ([15], 15, "ÚNICO", ""),
                        ],
                    ),
                    mock.patch.object(
                        system_engine._d20,
                        "rolar_d20",
                        side_effect=[10, effect_roll],
                    ) as d20_roll,
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[1]),
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon="Pistola de Choque"),
                        {},
                        report,
                    )

                self.assertEqual(combat["inimigo"]["status_effects"], expected_statuses)
                self.assertEqual(d20_roll.call_count, 2)
                self.assertEqual(
                    any("Efeito aplicado: atordoamento" in line for line in report),
                    effect_message,
                )

    def test_action_combat_critical_weapon_effect_bypasses_effect_dc(self):
        """A critical Pistola de Choque hit applies atordoamento even when its effect d20 is below 12."""
        character = _character()
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([20], 20, "ÚNICO", ""),
                ],
            ) as player_roll,
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10, 1]) as d20_roll,
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[3]) as player_damage,
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon="Pistola de Choque"),
                {},
                report,
            )

        # Critical d4 3 doubles to 6, then the weapon's fixed +1 makes 7 damage.
        self.assertEqual(combat["inimigo"]["hp_atual"], 23)
        self.assertEqual(
            combat["inimigo"]["status_effects"],
            [{"id": "atordoamento", "stacks": 1, "turno_restante": 1}],
        )
        self.assertEqual(player_roll.call_count, 2)
        self.assertEqual(d20_roll.call_count, 2)
        player_damage.assert_called_once_with()
        enemy_damage.assert_called_once_with()

    def test_action_combat_enemy_status_damage_dc_reduction_and_lifecycle(self):
        """Enemy statuses deal periodic damage, reduce DC, expire at one turn, and decrement otherwise."""
        character = _character()
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["hp_atual"] = 30
        enemy["hp_maximo"] = 30
        enemy["status_effects"] = [
            {"id": "sangramento", "stacks": 2, "turno_restante": None},
            {"id": "veneno", "stacks": 1, "turno_restante": 1},
            {"id": "queimadura", "stacks": 1, "turno_restante": 3},
            {"id": "corrosao", "stacks": 1, "turno_restante": 2},
        ]
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([13], 13, "ÚNICO", ""),
                ],
            ) as player_roll,
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[1]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        # 2*2 bleeding + 2 venom + 3 burn + 1 player d4 = 10 total damage.
        self.assertEqual(enemy["hp_atual"], 20)
        self.assertEqual(
            enemy["status_effects"],
            [
                {"id": "sangramento", "stacks": 2, "turno_restante": None},
                {"id": "queimadura", "stacks": 1, "turno_restante": 2},
                {"id": "corrosao", "stacks": 1, "turno_restante": 1},
            ],
        )
        self.assertEqual(player_roll.call_count, 2)
        self.assertTrue(any("vs DC 13 → SUCESSO" in line for line in report))

    def test_action_combat_stun_blocks_counterattack_and_expires(self):
        """Atordoamento present at turn start removes itself and prevents the enemy d4 counterattack."""
        character = _character()
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        combat["inimigo"]["status_effects"] = [
            {"id": "atordoamento", "stacks": 1, "turno_restante": 1}
        ]
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[4]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(character["vitals"]["hp"]["current"], 20)
        self.assertEqual(combat["inimigo"]["status_effects"], [])
        enemy_damage.assert_not_called()
        self.assertTrue(any("D4_ENEMY: N/A (atordoado)" in line for line in report))

    def test_action_combat_evaluates_morale_at_exactly_thirty_percent(self):
        """HP exactly 3/10 triggers morale; equality with the moral DC prevents the resulting flee."""
        character = _character()
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["hp_atual"] = 10
        enemy["hp_maximo"] = 10
        enemy["ficha_racial"]["pode_fugir"] = True
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([15], 15, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10, 10]) as d20_roll,
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[4]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {"dano_bonus_fixo": 3},
                report,
            )

        self.assertEqual(enemy["hp_atual"], int(10 * MORAL_FLEE_THRESHOLD))
        self.assertTrue(combat["combate_ativo"])
        self.assertEqual(d20_roll.call_count, 2)
        self.assertTrue(any("Teste moral: 10 vs DC 10" in line for line in report))

    def test_action_combat_does_not_roll_morale_at_thirty_one_percent(self):
        """A fleeing-capable enemy at 31/100 HP skips morale and performs its ordinary counterattack."""
        character = _character()
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["hp_atual"] = 31
        enemy["hp_maximo"] = 100
        enemy["ficha_racial"]["pode_fugir"] = True
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]) as d20_roll,
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(enemy["hp_atual"], 31)
        self.assertTrue(combat["combate_ativo"])
        self.assertEqual(character["vitals"]["hp"]["current"], 19)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(d20_roll.call_count, 1)
        enemy_damage.assert_called_once_with()

    def test_action_combat_morale_flee_grants_partial_xp_and_skips_counterattack(self):
        """Below-DC morale at 20% HP adds half the medium XP award to an existing total."""
        character = _character()
        character["progression"]["xp_current"] = 7
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["hp_atual"] = 7
        enemy["hp_maximo"] = 20
        enemy["ficha_racial"]["pode_fugir"] = True
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([15], 15, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10, 9]),
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[3]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(enemy["hp_atual"], 4)
        self.assertFalse(combat["combate_ativo"])
        self.assertEqual(character["progression"]["xp_current"], 17)
        self.assertEqual(combat["turno_combate"], 1)
        enemy_damage.assert_not_called()
        self.assertTrue(any("XP parcial (fuga): +10" in line for line in report))

    def test_action_combat_nonfleeing_enemy_skips_morale_even_below_threshold(self):
        """pode_fugir false prevents a moral d20 and keeps a 30%-HP enemy in combat."""
        character = _character()
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["hp_atual"] = 7
        enemy["hp_maximo"] = 10
        enemy["ficha_racial"]["pode_fugir"] = False
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([15], 15, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]) as d20_roll,
            mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[4]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(enemy["hp_atual"], 3)
        self.assertTrue(combat["combate_ativo"])
        self.assertEqual(d20_roll.call_count, 1)
        enemy_damage.assert_called_once_with()

    def test_action_combat_death_disables_combat_and_uses_hp_xp_bands(self):
        """Killing enemies at the band boundaries adds 10, 20, or 35 XP to the current total."""
        # Starting XP 5 plus the weak/medium/strong awards 10/20/35.
        cases = ((10, 15), (11, 25), (26, 40))

        for max_hp, expected_total_xp in cases:
            with self.subTest(max_hp=max_hp):
                character = _character()
                character["progression"]["xp_current"] = 5
                combat = _combat()
                enemy = combat["inimigo"]
                enemy["hp_atual"] = 4
                enemy["hp_maximo"] = max_hp
                report: list[str] = []

                with (
                    mock.patch.object(
                        system_engine,
                        "_roll",
                        side_effect=[
                            ([10], 10, "ÚNICO", ""),
                            ([15], 15, "ÚNICO", ""),
                        ],
                    ),
                    mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]) as d20_roll,
                    mock.patch.object(system_engine._d4, "rolar_d4", side_effect=[4]),
                    mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[1]) as enemy_damage,
                ):
                    system_engine.action_combat(
                        character,
                        combat,
                        SimpleNamespace(position=None, weapon=None),
                        {},
                        report,
                    )

                self.assertFalse(combat["combate_ativo"])
                self.assertEqual(character["progression"]["xp_current"], expected_total_xp)
                self.assertEqual(combat["turno_combate"], 1)
                self.assertEqual(d20_roll.call_count, 1)
                enemy_damage.assert_not_called()
                self.assertTrue(any("Status: MORTO" in line for line in report))

    def test_action_combat_last_breath_leaves_player_at_one_hp(self):
        """The current Last Breath passive restores a lethal counterattack result to exactly one HP."""
        character = _character()
        character["vitals"]["hp"]["current"] = 3
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[4]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {"ultimo_suspiro_disponivel": True},
                report,
            )

        self.assertEqual(character["vitals"]["hp"]["current"], 1)
        self.assertTrue(any("ÚLTIMO SUSPIRO ATIVADO" in line for line in report))

    def test_action_combat_lethal_counterattack_without_last_breath_keeps_zero_hp(self):
        """The same lethal counterattack reaches zero when Último Suspiro is absent."""
        character = _character()
        character["vitals"]["hp"]["current"] = 3
        combat = _combat()
        combat["inimigo"]["hp_atual"] = 30
        combat["inimigo"]["hp_maximo"] = 30
        report: list[str] = []

        with (
            mock.patch.object(
                system_engine,
                "_roll",
                side_effect=[
                    ([10], 10, "ÚNICO", ""),
                    ([1], 1, "ÚNICO", ""),
                ],
            ),
            mock.patch.object(system_engine._d20, "rolar_d20", side_effect=[10]),
            mock.patch.object(system_engine, "_roll_enemy_d4", side_effect=[4]),
        ):
            system_engine.action_combat(
                character,
                combat,
                SimpleNamespace(position=None, weapon=None),
                {},
                report,
            )

        self.assertEqual(character["vitals"]["hp"]["current"], 0)
        self.assertFalse(any("ÚLTIMO SUSPIRO ATIVADO" in line for line in report))


class LiveNavalActionCharacterizationTests(unittest.TestCase):
    def test_action_naval_fire_inactive_refuses_without_mechanical_mutation(self):
        """The inactive guard returns before naval fire spends energy or changes ship combat state."""
        character = _character()
        character["vitals"]["energy_reserves"]["current"] = 9
        combat = _combat()
        combat["combate_ativo"] = False
        combat["inimigo"]["escudos_atuais"] = 19
        combat["inimigo"]["hp_atual"] = 17
        before_character = copy.deepcopy(character)
        before_combat = copy.deepcopy(combat)
        report: list[str] = []

        system_engine.action_naval_fire(
            character,
            combat,
            SimpleNamespace(),
            {},
            report,
        )

        self.assertEqual(character, before_character)
        self.assertEqual(combat, before_combat)
        self.assertTrue(any("Nenhum combate ativo" in line for line in report))

    def test_action_naval_fire_low_energy_refuses_without_consumption_or_turn(self):
        """Energy below two returns before either the resource or combat turn is mutated."""
        character = _character()
        character["vitals"]["energy_reserves"]["current"] = 1
        combat = _combat()
        report: list[str] = []

        system_engine.action_naval_fire(
            character,
            combat,
            SimpleNamespace(),
            {},
            report,
        )

        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 1)
        self.assertEqual(combat["turno_combate"], 0)
        self.assertTrue(any("Sem energia suficiente" in line for line in report))

    def test_action_naval_fire_at_exactly_two_energy_consumes_the_final_reserve(self):
        """The energy guard accepts exactly two, then a valid miss spends both points and advances the turn."""
        character = _character()
        character["vitals"]["energy_reserves"]["current"] = 2
        combat = _combat()
        combat["inimigo"]["escudos_atuais"] = 20
        report: list[str] = []

        with mock.patch.object(
            system_engine,
            "_roll",
            side_effect=[([14], 14, "ÚNICO", "")],
        ) as player_roll:
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {},
                report,
            )

        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 0)
        self.assertEqual(combat["inimigo"]["escudos_atuais"], 20)
        self.assertEqual(combat["inimigo"]["hp_atual"], 20)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 1)

    def test_action_naval_fire_miss_consumes_energy_and_processes_turn(self):
        """A valid naval miss still spends exactly two energy, leaves defenses intact, and increments the turn."""
        character = _character()
        character["vitals"]["energy_reserves"]["current"] = 5
        combat = _combat()
        combat["inimigo"]["escudos_atuais"] = 20
        report: list[str] = []

        with mock.patch.object(
            system_engine,
            "_roll",
            side_effect=[([14], 14, "ÚNICO", "")],
        ) as player_roll:
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {},
                report,
            )

        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 3)
        self.assertEqual(combat["inimigo"]["escudos_atuais"], 20)
        self.assertEqual(combat["inimigo"]["hp_atual"], 20)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 1)
        self.assertTrue(any("Resultado: FALHA" in line for line in report))

    def test_action_naval_fire_attack_bonus_turns_near_miss_into_shield_hit(self):
        """Only ataque_naval_bonus +1 turns raw 14 with DES 10 into a hit against AC 15."""
        character = _character()
        combat = _combat()
        combat["inimigo"]["escudos_atuais"] = 20
        report: list[str] = []

        with mock.patch.object(
            system_engine,
            "_roll",
            side_effect=[([14], 14, "ÚNICO", "")],
        ) as player_roll:
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {"ataque_naval_bonus": 1},
                report,
            )

        # 14 + (DES 10 - 10) + 1 = 15, so shields take the fixed 15 damage.
        self.assertEqual(combat["inimigo"]["escudos_atuais"], 5)
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 1)

    def test_action_naval_fire_ignores_non_naval_attack_bonus(self):
        """Generic ataque_bonus cannot turn raw 14 with DES 10 into an AC-15 naval hit."""
        character = _character()
        combat = _combat()
        combat["inimigo"]["escudos_atuais"] = 20
        report: list[str] = []

        with mock.patch.object(
            system_engine,
            "_roll",
            side_effect=[([14], 14, "ÚNICO", "")],
        ) as player_roll:
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {"ataque_bonus": 1},
                report,
            )

        self.assertEqual(combat["inimigo"]["escudos_atuais"], 20)
        self.assertEqual(combat["inimigo"]["hp_atual"], 20)
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 1)

    def test_action_naval_fire_unshielded_nonlethal_hit_damages_hull_only(self):
        """An unshielded hull above ten HP loses exactly ten and keeps combat active."""
        character = _character()
        combat = _combat()
        enemy = combat["inimigo"]
        enemy["escudos_atuais"] = 0
        enemy["hp_atual"] = 25
        enemy["hp_maximo"] = 25
        report: list[str] = []

        with mock.patch.object(
            system_engine,
            "_roll",
            side_effect=[([15], 15, "ÚNICO", "")],
        ) as player_roll:
            system_engine.action_naval_fire(
                character,
                combat,
                SimpleNamespace(),
                {},
                report,
            )

        self.assertEqual(enemy["escudos_atuais"], 0)
        self.assertEqual(enemy["hp_atual"], 15)
        self.assertTrue(combat["combate_ativo"])
        self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
        self.assertEqual(combat["turno_combate"], 1)
        self.assertEqual(player_roll.call_count, 1)

    def test_action_naval_fire_shields_and_hull_clamp_then_destruction(self):
        """Successful naval fire clamps shields or hull at zero, disabling combat only after hull destruction."""
        cases = (
            (8, 20, 0, 20, True, "escudos"),
            (0, 7, 0, 0, False, "DESTRUÍDO"),
        )

        for shields, hp, expected_shields, expected_hp, expected_active, report_fragment in cases:
            with self.subTest(shields=shields, hp=hp):
                character = _character()
                combat = _combat()
                enemy = combat["inimigo"]
                enemy["escudos_atuais"] = shields
                enemy["hp_atual"] = hp
                report: list[str] = []

                with mock.patch.object(
                    system_engine,
                    "_roll",
                    side_effect=[([15], 15, "ÚNICO", "")],
                ) as player_roll:
                    system_engine.action_naval_fire(
                        character,
                        combat,
                        SimpleNamespace(),
                        {},
                        report,
                    )

                self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
                self.assertEqual(enemy["escudos_atuais"], expected_shields)
                self.assertEqual(enemy["hp_atual"], expected_hp)
                self.assertEqual(combat["combate_ativo"], expected_active)
                self.assertEqual(combat["turno_combate"], 1)
                self.assertEqual(player_roll.call_count, 1)
                self.assertTrue(any(report_fragment in line for line in report))

    def test_action_naval_fire_natural_one_misses_and_natural_twenty_hits(self):
        """The live naval action treats natural 1 as a miss and natural 20 as a hit despite their totals."""
        cases = (
            # 1 + (DES 20 - 10) = 11 >= AC 10; only the natural-1 override makes this fail.
            (1, 20, 10, 20, "FALHA"),
            (20, 1, 99, 5, "SUCESSO"),
        )

        for raw_roll, dexterity, enemy_ac, expected_shields, outcome in cases:
            with self.subTest(raw_roll=raw_roll):
                character = _character()
                character["attributes"]["destreza"]["value"] = dexterity
                combat = _combat()
                combat["inimigo"]["ac"] = enemy_ac
                combat["inimigo"]["escudos_atuais"] = 20
                report: list[str] = []

                with mock.patch.object(
                    system_engine,
                    "_roll",
                    side_effect=[([raw_roll], raw_roll, "ÚNICO", "")],
                ) as player_roll:
                    system_engine.action_naval_fire(
                        character,
                        combat,
                        SimpleNamespace(),
                        {},
                        report,
                    )

                self.assertEqual(combat["inimigo"]["escudos_atuais"], expected_shields)
                self.assertEqual(character["vitals"]["energy_reserves"]["current"], 8)
                self.assertEqual(combat["turno_combate"], 1)
                self.assertEqual(player_roll.call_count, 1)
                self.assertTrue(any(f"Resultado: {outcome}" in line for line in report))
