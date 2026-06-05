import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
sys.path.insert(0, str(SKILLS))


class ChronosContractTests(unittest.TestCase):
    @staticmethod
    def _base_character_sheet(attribute_points: int = 0) -> dict:
        return {
            "meta": {"version": "test", "last_updated": "TURNO_0"},
            "identity": {"name": "Ferro", "status": "STABLE"},
            "vitals": {
                "hp": {"current": 10, "max": 20},
                "oxygen_level": {"current": 100, "max": 100},
                "energy_reserves": {"current": 80, "max": 100},
                "hull_integrity": {"current": 100, "max": 100},
                "fuel_cells": {"current": 0, "max": 10},
                "fome": {"current": 90, "max": 100},
                "sede": {"current": 90, "max": 100},
                "exaustao": {"current": 90, "max": 100},
            },
            "attributes": {
                "forca": {"abbr": "FOR", "value": 12},
                "destreza": {"abbr": "DES", "value": 12},
                "inteligencia": {"abbr": "INT", "value": 10},
                "sobrevivencia": {"abbr": "SOB", "value": 10},
                "percepcao": {"abbr": "PER", "value": 10},
                "carisma": {"abbr": "CAR", "value": 8},
            },
            "skills": {
                "combat": {"bonus": 0},
                "engineering": {"bonus": 0},
                "piloting": {"bonus": 0},
                "survival": {"bonus": 0},
                "stealth": {"bonus": 0},
                "chip_interface": {"bonus": 0},
            },
            "chip_status": {"carga_atual": 100, "funcoes_ativas": []},
            "active_status_effects": [],
            "equipment": {
                "armor": None,
                "weapon_primary": None,
                "weapon_secondary": None,
                "suit_integrity": {"current": 100, "max": 100},
            },
            "progression": {
                "level": 1,
                "xp_current": 0,
                "xp_to_next_level": 100,
                "attribute_points_available": attribute_points,
                "total_attribute_points_spent": 0,
                "skill_choice_pending": False,
            },
            "passive_skills": [],
        }

    @staticmethod
    def _base_active_combat(active: bool = False) -> dict:
        return {
            "combate_ativo": active,
            "turno_combate": 0,
            "jogador": {"arma_equipada": None, "armadura_equipada": None},
            "posicionamento": {"estado_atual": "MELEE"},
            "inimigo": {
                "nome": "Drone de Teste",
                "classe": "teste",
                "hp_atual": 20,
                "hp_maximo": 20,
                "dc_defesa": 15,
                "velocidade": 0,
                "damage_bonus_racial": 0,
                "tipo_dano": "Físico",
                "status_effects": [],
                "ficha_racial": {"drop": "Sucata", "pode_fugir": False},
            },
        }

    @staticmethod
    def _base_chapter_tracker() -> dict:
        return {
            "meta": {"version": "test", "last_updated": "TURNO_0"},
            "contagem": {"interacoes_no_capitulo": 0, "maximo_obrigatorio": 25},
            "world_state": {},
        }

    def test_current_state_json_files_are_valid(self):
        for path in (ROOT / "current_state").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_weather_and_period_names_match_runtime_tables(self):
        import world_state_ticker

        tracker = json.loads((ROOT / "current_state" / "chapter_tracker.json").read_text(encoding="utf-8"))
        world_state = tracker["world_state"]

        valid_weather = {
            s.strip()
            for s in world_state["clima"]["_estados_validos"].split("|")
        }
        valid_periods = {
            s.strip()
            for s in world_state["periodo"]["_estados_validos"].split("|")
        }

        self.assertEqual(valid_weather, set(world_state_ticker.WEATHER_EFFECTS.keys()))
        self.assertEqual(valid_periods, set(world_state_ticker.PERIOD_EFFECTS.keys()))

    def test_web_command_validation_allows_only_known_system_commands(self):
        import web_server

        state = web_server.get_game_state()
        allowed = web_server._validate_system_cmd(web_server._SE + ["explore", "--dc", "medio"], state)
        denied = web_server._validate_system_cmd(["cmd.exe", "/c", "whoami"], state)

        self.assertEqual(allowed, web_server._SE + ["explore", "--dc", "medio"])
        self.assertIsNone(denied)

    def test_narrative_option_parser_extracts_three_structured_options(self):
        import game_master

        scene = """
**PARTE 3 — O QUE VOCE FAZ?**
1. [ANALISE] Examinar o terreno antes de agir.
2. [IMPROV] Usar sucata próxima para criar apoio.
3. [RETIRADA] Recuar para uma posição mais segura.
"""
        options = game_master.parse_narrative_options(scene)

        self.assertEqual(len(options), 3)
        self.assertEqual(options[0]["cmd_suffix"], ["scan"])
        self.assertEqual(options[1]["cmd_suffix"], ["explore", "--dc", "medio"])
        self.assertEqual(options[2]["cmd_suffix"], ["flee"])

    def test_dynamic_item_registry_shape(self):
        import loot_manager

        registry_path = ROOT / "world_context" / "dynamic_items.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertIsInstance(registry.get("items"), dict)

        for name, schema in registry["items"].items():
            with self.subTest(item=name):
                self.assertIsInstance(schema, dict)
                for key in ("type", "rarity", "weight_kg", "effect", "usable", "notes"):
                    self.assertIn(key, schema)
                self.assertIn(name, loot_manager.ITEM_SCHEMA)

    def test_relevant_story_memory_has_recent_fallback(self):
        import world_context_loader

        result = world_context_loader.load_story_bible_relevant("termo-inexistente-xyz", max_chars=500)
        self.assertTrue(result.strip())

    def test_system_engine_use_item_updates_inventory_and_vitals(self):
        import system_engine

        sheet = self._base_character_sheet()
        sheet["vitals"]["hp"]["current"] = 5
        combat = self._base_active_combat(active=False)
        inventory = [{
            "id": "1",
            "name": "Med Gel",
            "type": "consumivel",
            "rarity": "comum",
            "quantity": "1",
            "weight_kg": "0.1",
            "effect": "+10 HP",
            "usable": "true",
            "durability": "",
            "durability_max": "",
            "notes": "teste",
        }]
        report: list[str] = []
        args = SimpleNamespace(item="Med Gel")

        updated_inventory = system_engine.action_use(sheet, combat, args, {}, report, inventory)

        self.assertEqual(sheet["vitals"]["hp"]["current"], 15)
        self.assertEqual(updated_inventory[0]["quantity"], "0")
        self.assertTrue(any("Item usado" in line for line in report))

    def test_system_engine_combat_updates_enemy_player_and_position_deterministically(self):
        import system_engine

        sheet = self._base_character_sheet()
        sheet["vitals"]["hp"]["current"] = 20
        combat = self._base_active_combat(active=True)
        report: list[str] = []
        args = SimpleNamespace(position="FLANQUEANDO", weapon=None)

        with (
            mock.patch.object(system_engine, "_roll", return_value=([20], 20, "ÚNICO", "")),
            mock.patch.object(system_engine._d20, "rolar_d20", return_value=10),
            mock.patch.object(system_engine._d4, "rolar_d4", return_value=2),
        ):
            system_engine.action_combat(sheet, combat, args, {}, report)

        self.assertEqual(combat["posicionamento"]["estado_atual"], "FLANQUEANDO")
        self.assertEqual(combat["turno_combate"], 1)
        self.assertLess(combat["inimigo"]["hp_atual"], 20)
        self.assertLess(sheet["vitals"]["hp"]["current"], 20)
        self.assertTrue(any("RESULTADO" in line for line in report))

    def test_api_levelup_spends_attribute_points_without_touching_real_sheet(self):
        import web_server

        sheet = self._base_character_sheet(attribute_points=2)
        fake_open = mock.mock_open()

        with (
            mock.patch.object(web_server, "_read_json", return_value=sheet),
            mock.patch("builtins.open", fake_open),
            mock.patch.object(web_server.os, "replace"),
        ):
            response = web_server.app.test_client().post(
                "/api/levelup",
                json={"spent": {"forca": 1, "destreza": 1}},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["pontos_restantes"], 0)
        self.assertEqual(sheet["attributes"]["forca"]["value"], 13)
        self.assertEqual(sheet["attributes"]["destreza"]["value"], 13)
        self.assertEqual(sheet["progression"]["total_attribute_points_spent"], 2)
        self.assertTrue(fake_open.called)

    def test_api_turn_rejects_untrusted_command_payload(self):
        import web_server

        fake_state = {
            "inventory": [],
            "combat": {"ativo": False, "posicao": ""},
            "character": {"skill_pending": False, "attribute_points_available": 0},
        }

        with mock.patch.object(web_server, "get_game_state", return_value=fake_state):
            response = web_server.app.test_client().post(
                "/api/turn",
                json={
                    "type": "narrative_explore",
                    "action_label": "payload inseguro",
                    "cmd": ["cmd.exe", "/c", "whoami"],
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_action")
        self.assertTrue(web_server.pipeline_lock.acquire(blocking=False))
        web_server.pipeline_lock.release()


if __name__ == "__main__":
    unittest.main()
