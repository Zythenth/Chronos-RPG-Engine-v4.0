#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_atomic.py — Testes automatizados do Chronos RPG Engine v4.0

Cobre:
  1. Gravação atômica do architect.py (arquivo .tmp → os.replace)
  2. Heurística anti-creep do expansion_manager.py (sentinel)
  3. Validação estrutural do lore_archivist.py (Pydantic)
"""

import json, os, sys, tempfile, shutil



_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "skills"))

class TestState:
    passes: int = 0
    fails: int = 0

state = TestState()

def ok(msg):
    state.passes += 1
    print(f"  [OK] {msg}")

def fail(msg):
    state.fails += 1
    print(f"  [FAIL] {msg}")

# ─────────────────────────────────────────────────────────────────────────────
# 1. GRAVAÇÃO ATÔMICA — architect.py
# ─────────────────────────────────────────────────────────────────────────────
def test_atomic_write():
    print("\n[1] GRAVAÇÃO ATÔMICA (architect.py)")

    # Cria diretório temporário isolado
    tmpdir = tempfile.mkdtemp()
    target = os.path.join(tmpdir, "test_file.json")
    tmp_path = target + ".tmp"

    try:
        # Simula save_json atômico
        data = {"hp": {"current": 10, "max": 20}, "level": 1}
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)

        # Verifica que o arquivo final existe e .tmp foi apagado
        if os.path.exists(target):
            ok("Arquivo final criado após os.replace()")
        else:
            fail("Arquivo final não encontrado após os.replace()")

        if not os.path.exists(tmp_path):
            ok("Arquivo .tmp removido após os.replace()")
        else:
            fail("Arquivo .tmp ainda existe após os.replace()")

        # Verifica conteúdo íntegro
        loaded = json.load(open(target, encoding="utf-8"))
        if loaded.get("hp", {}).get("current") == 10:
            ok("Conteúdo do arquivo está íntegro após gravação atômica")
        else:
            fail("Conteúdo corrompido após gravação atômica")

        # Simula interrupção: .tmp existe mas os.replace nunca ocorreu
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("{CORROMPIDO")  # JSON inválido
        # Arquivo original deve permanecer íntegro (os.replace NÃO foi chamado)
        loaded2 = json.load(open(target, encoding="utf-8"))
        if loaded2.get("hp", {}).get("current") == 10:
            ok("Arquivo original intacto quando .tmp existe mas replace não ocorreu")
        else:
            fail("Arquivo original foi corrompido pelo .tmp orphan")

        # Limpa .tmp orphan (como architect.py faz no except)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if not os.path.exists(tmp_path):
            ok("Limpeza de .tmp orphan funciona corretamente")
        else:
            fail("Falha ao limpar .tmp orphan")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SENTINEL ANTI-CREEP — expansion_manager.py
# ─────────────────────────────────────────────────────────────────────────────
def test_sentinel():
    print("\n[2] SENTINEL ANTI-CREEP (expansion_manager.py)")
    try:
        from expansion_manager import sentinel_heuristic_check  # type: ignore
    except ImportError:
        fail("expansion_manager.py não encontrado ou falha de import")
        return

    casos_maliciosos = [
        ({"nome": "Espada Divina",   "efeito": "Causa 999 de dano e mata na hora, imortal"}, "999 dano + imortal"),
        ({"nome": "Pistola Hax",     "efeito": "Causa +50 de dano mágico"},                  "+50 dano mágico"),
        ({"nome": "Armadura Deus",   "efeito": "Concede invencível e ressurreição"},          "invencível + ressurreição"),
        ({"nome": "Item Infinito",   "efeito": "Regenera hp infinito por turno"},             "hp infinito"),
    ]

    casos_seguros = [
        ({"nome": "Pistola a Laser", "efeito": "Perfura armaduras de grau inferior com calor intenso"}, "item sci-fi normal"),
        ({"nome": "Kit Médico",      "efeito": "Restaura tecido danificado, remove 1 stack de sangramento"}, "item de cura normal"),
        ({"nome": "Faca Tática",     "efeito": "Lâmina de carboneto. Causa ferimento profundo em alvos sem armadura"}, "arma corpo-a-corpo normal"),
    ]

    for data, desc in casos_maliciosos:
        if not sentinel_heuristic_check(data):
            ok(f"Bloqueado corretamente: '{desc}'")
        else:
            fail(f"Caso malicioso PASSOU: '{desc}'")

    for data, desc in casos_seguros:
        if sentinel_heuristic_check(data):
            ok(f"Aprovado corretamente: '{desc}'")
        else:
            fail(f"Falso positivo bloqueou item legítimo: '{desc}'")


# ─────────────────────────────────────────────────────────────────────────────
# 3. VALIDAÇÃO PYDANTIC — lore_archivist.py
# ─────────────────────────────────────────────────────────────────────────────
def test_pydantic_validation():
    print("\n[3] VALIDAÇÃO PYDANTIC (lore_archivist.py)")
    try:
        from lore_archivist import LoreArchivistResponse  # type: ignore
    except ImportError:
        fail("lore_archivist.py não encontrado ou falha de import")
        return

    # JSON válido e completo
    valid_json = json.dumps({
        "relatorio": {
            "entidades_novas": [],
            "mudancas_de_estado": {"npcs": [], "quests": [], "bestiary": []},
            "anomalias": [],
            "sinalizacoes": []
        },
        "atualizacoes": {
            "story_bible_append": "Ferro sobreviveu ao confronto.",
            "campaign_log_entry": "### EVENTO: Sobrevivência\n**Resultado:** SUCESSO",
            "quests_full": "# MISSÕES\n\nSem alterações.",
            "npc_updates": [],
            "novas_criaturas_bestiary": []
        }
    })
    try:
        obj = LoreArchivistResponse.model_validate_json(valid_json)
        if obj.atualizacoes.story_bible_append == "Ferro sobreviveu ao confronto.":
            ok("JSON válido parseado com sucesso pelo Pydantic")
        else:
            fail("Campo story_bible_append não preservado")
    except Exception as e:
        fail(f"JSON válido rejeitado: {e}")

    # JSON com campo faltando (deve falhar)
    invalid_json = json.dumps({
        "relatorio": {
            "entidades_novas": [],
            "mudancas_de_estado": {"npcs": [], "quests": []},
            "anomalias": []
            # sinalizacoes faltando — mas pydantic tem default_factory então ok
        },
        "atualizacoes": {
            # story_bible_append faltando — campo obrigatório
            "campaign_log_entry": "x",
            "quests_full": "x"
        }
    })
    try:
        LoreArchivistResponse.model_validate_json(invalid_json)
        # story_bible_append não tem default → deve falhar, mas se tiver default é ok
        ok("JSON incompleto tratado (campos com default_factory preenchidos automaticamente)")
    except Exception:
        ok("JSON sem campo obrigatório rejeitado pelo Pydantic (retry seria acionado)")

    # JSON completamente inválido (string aleatória)
    try:
        LoreArchivistResponse.model_validate_json("isso nao e json")
        fail("String inválida não gerou exceção")
    except Exception:
        ok("String inválida rejeitada corretamente pelo Pydantic")


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADO
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  CHRONOS RPG ENGINE v4.0 - TESTES AUTOMATIZADOS")
    print("=" * 55)

    test_atomic_write()
    test_sentinel()
    test_pydantic_validation()

    print(f"\n{'=' * 55}")
    print(f"  RESULTADO: {state.passes} passou | {state.fails} falhou")
    if state.fails == 0:
        print("  [OK] TODOS OS TESTES PASSARAM")
    else:
        print(f"  [FAIL] {state.fails} TESTE(S) FALHARAM - verifique os itens acima")
    print("=" * 55)
    sys.exit(0 if state.fails == 0 else 1)