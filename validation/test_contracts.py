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

    def test_api_state_rejects_unreadable_essential_sources(self):
        import web_server

        def read_source(path):
            if path == web_server._CS_PATH:
                return None
            return {"valid": True}

        with mock.patch.object(web_server, "_read_json_any", side_effect=read_source):
            response = web_server.app.test_client().get("/api/state")

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["error"], "state_unavailable")
        self.assertEqual(payload["unavailable_sources"], ["character_sheet"])
        self.assertNotIn("state", payload)

    def test_codex_bestiary_denies_entries_without_player_visible_evidence(self):
        import web_server

        bestiary = """
# BESTIÁRIO
## Nome: Predador Visível
- **Classe:** Biológico
- **Habitat:** Selva
- **Comportamento:** Emboscada
- **Fraqueza:** Luz

## Nome: Leviatã Futuro *(Boss — Cap. 40)*
- **Classe:** Oculto
- **Habitat:** Futuro
- **Comportamento:** Segredo
- **Fraqueza:** ???
"""
        with mock.patch.object(web_server, "_read", return_value=bestiary):
            parsed = web_server._parse_bestiary_for_codex(
                "O diário confirma que o Predador Visível foi encontrado."
            )

        self.assertEqual(list(parsed), ["Predador Visível"])
        self.assertNotIn("Leviatã Futuro", parsed)
        self.assertEqual(parsed["Predador Visível"]["descricao"], "")

    def test_codex_bestiary_never_exposes_gm_fields_or_editorial_suffixes(self):
        import web_server

        bestiary = """
# BESTIÁRIO
## Nome: Predador Alfa da Encosta *(Boss — Cap. 9)*
- **Classe:** Boss secreto
- **Habitat:** Encosta oculta
- **Comportamento:** Emboscada final
- **Fraqueza:** DC 18 em fogo
"""
        with mock.patch.object(web_server, "_read", return_value=bestiary):
            parsed = web_server._parse_bestiary_for_codex(
                "Ferro encontrou o Predador Alfa da Encosta."
            )

        self.assertEqual(
            parsed,
            {"Predador Alfa da Encosta": {"descricao": ""}},
        )
        serialized = json.dumps(parsed, ensure_ascii=False)
        self.assertNotIn("Boss", serialized)
        self.assertNotIn("Cap. 9", serialized)
        self.assertNotIn("DC 18", serialized)

    def test_codex_npc_parser_excludes_potential_contacts(self):
        import web_server

        dossier = """
# DOSSIÊ
## 1. O PROTAGONISTA
**"Ferro" (JOGADOR)**
- **Função:** Sucateiro.

## 4. CONTATOS POTENCIAIS
**"The Echo"**
- **Função:** Contato futuro.
"""
        with mock.patch.object(web_server, "_read", return_value=dossier):
            parsed = web_server._parse_npc_dossier_for_codex(
                "Ferro registrou o início da jornada."
            )

        self.assertEqual(parsed, {"Ferro": {"descricao": ""}})
        self.assertNotIn("The Echo", parsed)

    def test_current_codex_payload_contains_no_future_bestiary_entries(self):
        import web_server

        state = web_server.get_game_state()

        self.assertTrue(state["codex_meta"]["available"])
        self.assertEqual(state["bestiary"], {})
        self.assertEqual(set(state["npc_dossier"]), {"Ferro", "CHRONOS-7 ALPHA"})

    def test_api_state_returns_only_the_latest_chat_history_chunk(self):
        import web_server

        history = [
            {"role": "gm" if index % 2 == 0 else "player", "text": f"Mensagem {index}"}
            for index in range(105)
        ]

        def read_source(path):
            if path in {web_server._CS_PATH, web_server._CT_PATH}:
                return {"valid": True}
            if path == web_server._CHAT_HISTORY_PATH:
                return history
            return {}

        with (
            mock.patch.object(web_server, "_read_json_any", side_effect=read_source),
            mock.patch.object(web_server, "get_game_state", return_value={}),
            mock.patch.object(web_server, "get_menu_options", return_value=[]),
            mock.patch.object(web_server, "_read", return_value=""),
            mock.patch.object(
                web_server.os.path,
                "exists",
                side_effect=lambda path: path == web_server._CHAT_HISTORY_PATH,
            ),
        ):
            response = web_server.app.test_client().get("/api/state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["chat_history"], history[-web_server._HISTORY_CHUNK_SIZE:])
        self.assertEqual(
            payload["chat_history_page"],
            {
                "start": 65,
                "end": 105,
                "total": 105,
                "has_older": True,
                "has_newer": False,
            },
        )

    def test_api_history_returns_a_requested_bounded_chunk(self):
        import web_server

        history = [
            {"role": "gm" if index % 2 == 0 else "player", "text": f"Mensagem {index}"}
            for index in range(130)
        ]

        with (
            mock.patch.object(web_server, "_read_json_any", return_value=history),
            mock.patch.object(web_server.os.path, "exists", return_value=True),
        ):
            response = web_server.app.test_client().get("/api/history?start=40&limit=1000")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["chat_history"]), web_server._HISTORY_MAX_LIMIT)
        self.assertEqual(payload["chat_history"], history[40:120])
        self.assertEqual(
            payload["chat_history_page"],
            {
                "start": 40,
                "end": 120,
                "total": 130,
                "has_older": True,
                "has_newer": True,
            },
        )

    def test_api_history_rejects_invalid_window_parameters(self):
        import web_server

        response = web_server.app.test_client().get("/api/history?start=-1&limit=nope")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_history_window")

    def test_api_turn_returns_conflict_when_level_up_is_pending(self):
        import web_server

        sheet = self._base_character_sheet(attribute_points=1)
        fake_state = {
            "inventory": [],
            "combat": {"ativo": False, "posicao": ""},
            "character": {
                "level_up_pending": True,
                "skill_pending": False,
                "attr_pts": 1,
            },
        }

        with (
            mock.patch.object(web_server, "get_game_state", return_value=fake_state),
            mock.patch.object(web_server, "get_menu_options", return_value=[]),
            mock.patch.object(web_server, "_read_json", return_value=sheet),
            mock.patch.object(web_server, "_read_json_any", return_value=[]),
            mock.patch.object(web_server, "_atomic_write_text") as atomic_write,
        ):
            response = web_server.app.test_client().post(
                "/api/turn",
                json={
                    "type": "narrative_explore",
                    "action_label": "Examinar os arredores",
                    "cmd": web_server._SE + ["explore", "--dc", "medio"],
                },
            )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "level_up_required")
        self.assertIn("pontos de atributo", payload["message"])
        atomic_write.assert_not_called()
        self.assertTrue(web_server.pipeline_lock.acquire(blocking=False))
        web_server.pipeline_lock.release()

    def test_api_turn_persists_raw_player_command_only_after_success(self):
        import importlib.util
        import web_server

        sheet = self._base_character_sheet()
        existing_history = [
            {"role": "gm", "text": "A porta se abre."},
            {"role": "player", "text": "Entro no corredor."},
        ]
        history_after_player = [
            *existing_history,
            {"role": "player", "text": "Examinar os arredores"},
        ]
        history_reads = iter((existing_history, history_after_player))
        fake_state = {
            "inventory": [],
            "combat": {"ativo": False, "posicao": ""},
            "character": {
                "level_up_pending": False,
                "skill_pending": False,
                "attr_pts": 0,
            },
        }
        scene = """
**PARTE 2 — NARRATIVA**
O corredor permanece em silêncio.
**PARTE 3 — O QUE VOCÊ FAZ?**
1. Avançar.
"""

        def read_json(path):
            if path == web_server._CS_PATH:
                return sheet
            if path == web_server._AC_PATH:
                return self._base_active_combat(active=False)
            return {}

        with (
            mock.patch.object(web_server, "get_game_state", return_value=fake_state),
            mock.patch.object(web_server, "get_menu_options", return_value=[]),
            mock.patch.object(web_server, "_read_json", side_effect=read_json),
            mock.patch.object(
                web_server,
                "_read_json_any",
                side_effect=lambda path: [
                    dict(message) for message in next(history_reads)
                ]
                if path == web_server._CHAT_HISTORY_PATH
                else [],
            ),
            mock.patch.object(web_server, "_read", return_value=scene),
            mock.patch.object(web_server, "run_script", return_value=""),
            mock.patch.object(
                web_server.os.path,
                "exists",
                side_effect=lambda path: path == web_server._CHAT_HISTORY_PATH,
            ),
            mock.patch.object(web_server, "_atomic_write_text") as atomic_write,
            mock.patch.object(importlib.util, "spec_from_file_location", return_value=None),
        ):
            response = web_server.app.test_client().post(
                "/api/turn",
                json={"action": "Examinar os arredores"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(atomic_write.call_count, 2)
        player_history = json.loads(atomic_write.call_args_list[0].args[1])
        self.assertEqual(player_history, history_after_player)
        complete_history = json.loads(atomic_write.call_args_list[1].args[1])
        self.assertEqual(complete_history[:2], existing_history)
        self.assertEqual(complete_history[-2], history_after_player[-1])
        self.assertEqual(
            complete_history[-1],
            {"role": "gm", "text": "O corredor permanece em silêncio."},
        )
        self.assertEqual(payload["chat_history"], complete_history)
        self.assertEqual(
            payload["chat_history_page"],
            {
                "start": 0,
                "end": 4,
                "total": 4,
                "has_older": False,
                "has_newer": False,
            },
        )

    def test_api_turn_503_does_not_persist_player_command(self):
        import importlib.util
        import web_server

        sheet = self._base_character_sheet()
        fake_state = {
            "inventory": [],
            "combat": {"ativo": False, "posicao": ""},
            "character": {
                "level_up_pending": False,
                "skill_pending": False,
                "attr_pts": 0,
            },
        }

        def read_json(path):
            if path == web_server._CS_PATH:
                return sheet
            if path == web_server._AC_PATH:
                return self._base_active_combat(active=False)
            return {}

        def run_script(_cmd, label, **_kwargs):
            return "503 UNAVAILABLE" if "Game Master" in label else ""

        with (
            mock.patch.object(web_server, "get_game_state", return_value=fake_state),
            mock.patch.object(web_server, "_read_json", side_effect=read_json),
            mock.patch.object(web_server, "run_script", side_effect=run_script),
            mock.patch.object(web_server.os.path, "exists", return_value=False),
            mock.patch.object(web_server, "_atomic_write_text") as atomic_write,
            mock.patch.object(importlib.util, "spec_from_file_location", return_value=None),
        ):
            response = web_server.app.test_client().post(
                "/api/turn",
                json={"action": "Examinar os arredores"},
            )

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "gemini_503")
        atomic_write.assert_not_called()

    def test_checkpoint_manifest_detects_hash_mismatch(self):
        import checkpoint_manager

        meta = {
            "manifest": [
                {
                    "path": "current_state/character_sheet.json",
                    "bytes": 10,
                    "sha256": "expected",
                }
            ]
        }

        with (
            mock.patch.object(checkpoint_manager.os.path, "exists", return_value=True),
            mock.patch.object(checkpoint_manager.os.path, "getsize", return_value=10),
            mock.patch.object(checkpoint_manager, "_sha256_file", return_value="actual"),
        ):
            errors = checkpoint_manager._manifest_errors("checkpoint", meta)

        self.assertIn("SHA256_DIVERGENTE: current_state/character_sheet.json", errors)

    def test_checkpoint_trim_preserves_restore_target(self):
        import checkpoint_manager

        log = [{"id": "keep"}, {"id": "old"}, {"id": "new"}]

        with (
            mock.patch.object(checkpoint_manager, "MAX_CHECKPOINTS", 2),
            mock.patch.object(checkpoint_manager.os.path, "exists", return_value=True),
            mock.patch.object(checkpoint_manager.shutil, "rmtree") as rmtree,
        ):
            trimmed = checkpoint_manager._trim_log(log, protect_ids={"keep"})

        self.assertEqual([entry["id"] for entry in trimmed], ["keep", "new"])
        rmtree.assert_called_once()
        self.assertIn("old", rmtree.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
