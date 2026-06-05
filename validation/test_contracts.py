import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
sys.path.insert(0, str(SKILLS))


class ChronosContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
