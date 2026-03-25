#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_turn.py — Orquestrador CLI do Chronos RPG Engine v4.0

Alternativa ao web_server.py para executar o pipeline completo
via linha de comando, sem servidor Flask.

USO:
  python run_turn.py --action "explorar área"
  python run_turn.py --action "atacar inimigo"
  python run_turn.py --action "usar kit médico"
"""

import sys, io, os, json, subprocess, argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_DRAFT_DIR = os.path.join(_PROJ, "drafts")

_CS_PATH     = os.path.join(_STATE_DIR, "character_sheet.json")
_SCENE_PATH  = os.path.join(_DRAFT_DIR, "current_scene.md")
_REPORT_PATH = os.path.join(_DRAFT_DIR, "technical_report.txt")

_SE  = [sys.executable, os.path.join(_HERE, "system_engine.py")]
_AR  = [sys.executable, os.path.join(_HERE, "architect.py")]
_GM  = [sys.executable, os.path.join(_HERE, "game_master.py")]
_SP  = [sys.executable, os.path.join(_HERE, "scene_processor.py")]
_LA  = [sys.executable, os.path.join(_HERE, "lore_archivist.py")]
_WST = [sys.executable, os.path.join(_HERE, "world_state_ticker.py"), "--quiet"]


# ── .env ─────────────────────────────────────────────────────────────────────
def _load_env():
    path = os.path.join(_PROJ, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_env()


def run_script(cmd: list, label: str) -> str:
    """Executa um script filho e imprime o resultado."""
    print(f"\n⚙ {label}...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=False, timeout=180)
        raw_out = (r.stdout or b"") + (r.stderr or b"")
        out = raw_out.decode("utf-8", errors="replace")
        stderr_str = (r.stderr or b"").decode("utf-8", errors="replace")
        if r.returncode != 0:
            print(f"⚠ {label}: código {r.returncode}")
            if stderr_str:
                for line in stderr_str.strip().splitlines()[:5]:
                    if line.strip():
                        print(f"  ↳ {line.strip()[:120]}")
        else:
            print(f"✓ {label}")
        return out
    except subprocess.TimeoutExpired:
        print(f"✗ {label}: timeout (>180s)")
        return "TIMEOUT"
    except Exception as e:
        print(f"✗ {label}: {e}")
        return str(e)


def _read_json(path: str) -> dict:
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    return open(path, encoding="utf-8").read()


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot / Rollback (seção 18 — 10 arquivos de snapshot)
# ─────────────────────────────────────────────────────────────────────────────

_CTX_DIR = os.path.join(_PROJ, "world_context")

def _take_snapshot() -> dict:
    """Snapshot pré-turno para rollback em caso de 503.
    Captura os mesmos arquivos que web_server.py (seção 18)."""
    snapshot: dict = {}
    _snapshot_state_files = [
        "character_sheet.json", "active_combat.json",
        "chapter_tracker.json", "inventory.csv",
        "world_map.json", "active_quests.md",
    ]
    _snapshot_ctx_files = [
        "campaign_log.md", "story_bible.md",
        "npc_dossier.md", "bestiary.md",
    ]
    for fname in _snapshot_state_files:
        fpath = os.path.join(_STATE_DIR, fname)
        if os.path.exists(fpath):
            try:
                snapshot[fpath] = open(fpath, encoding="utf-8").read()
            except Exception:
                pass
    for fname in _snapshot_ctx_files:
        fpath = os.path.join(_CTX_DIR, fname)
        if os.path.exists(fpath):
            try:
                snapshot[fpath] = open(fpath, encoding="utf-8").read()
            except Exception:
                pass
    # Also snapshot drafts
    for dname in ["current_scene.md", "narrative_options.json"]:
        dpath = os.path.join(_DRAFT_DIR, dname)
        if os.path.exists(dpath):
            try:
                snapshot[dpath] = open(dpath, encoding="utf-8").read()
            except Exception:
                pass
    return snapshot


def _rollback(snapshot: dict):
    """Restaura o estado pré-turno a partir do snapshot."""
    for fpath, content in snapshot.items():
        try:
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
    print("↩ Estado pré-turno restaurado (rollback — todos os arquivos).")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def run_turn(action_label: str, cmd_args: list | None = None):
    """Executa o pipeline completo de um turno via CLI."""

    print("\n" + "=" * 55)
    print("  CHRONOS RPG ENGINE — Turno CLI")
    print("=" * 55)
    print(f"  Ação: {action_label}")

    # Verifica level up pendente
    cs = _read_json(_CS_PATH)
    prog = cs.get("progression", {})
    attr_pts = int(prog.get("attribute_points_available", 0))
    sk_pending = bool(prog.get("skill_choice_pending", False))
    if attr_pts > 0:
        print("⚠ BLOQUEADO: distribua os pontos de atributo antes de continuar.")
        return
    if sk_pending:
        print("⚠ BLOQUEADO: escolha uma habilidade passiva antes de continuar.")
        return

    # Snapshot pré-turno
    snapshot = _take_snapshot()

    # Monta comando do system_engine
    if cmd_args:
        se_cmd = _SE + cmd_args
    else:
        se_cmd = _SE + ["explore", "--dc", "medio"]

    # Passo 1 — System Engine
    se_out = run_script(se_cmd, "Passo 1 — System Engine")
    # Salva technical_report.txt
    try:
        os.makedirs(_DRAFT_DIR, exist_ok=True)
        with open(_REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(se_out or "")
    except Exception as e:
        print(f"⚠ Erro ao salvar technical_report: {e}")

    # Passo 1.5 — World State Ticker
    run_script(_WST, "Passo 1.5 — World Ticker")

    # Passo 2 — Architect (check + auto-loot)
    run_script(_AR + ["check"], "Passo 2 — Architect (check)")

    # Auto-loot: se combate acabou neste turno, aplica loot automaticamente
    try:
        _ac_now = _read_json(os.path.join(_STATE_DIR, "active_combat.json"))
        _combat_active = bool(_ac_now.get("combate_ativo", False))
        _enemy_name = _ac_now.get("inimigo", {}).get("nome", "")
        _enemy_hp = _ac_now.get("inimigo", {}).get("hp_atual", 1)
        if not _combat_active and _enemy_name and _enemy_hp <= 0:
            run_script(_AR + ["apply_loot"], "Passo 2.1 — Architect (loot)")
    except Exception:
        pass

    # Passo 3 — Game Master (Gemini 2.5 Pro)
    gm_out = run_script(_GM + ["--action", action_label], "Passo 3 — Game Master (Gemini)")

    # Detecção de 503
    if "503" in (gm_out or "") and "UNAVAILABLE" in (gm_out or ""):
        _rollback(snapshot)
        print("⚠ Gemini 503 UNAVAILABLE — turno NÃO contabilizado.")
        print("  Tente novamente em alguns segundos.")
        return

    # Passo 3.5 — Scene Processor
    run_script(_SP, "Passo 3.5 — Scene Processor")

    # Passo 4 — Lore Archivist (Gemini 2.5 Flash)
    la_out = run_script(_LA, "Passo 4 — Lore Archivist (Gemini)")
    if "503" in (la_out or "") and "UNAVAILABLE" in (la_out or ""):
        print("⚠ Lore Archivist 503 — arquivamento pulado. Narrativa OK.")

    # Checkpoint automático
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "checkpoint_manager",
            os.path.join(_HERE, "checkpoint_manager.py")
        )
        if spec and spec.loader:
            cm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cm)
            saved = cm.CheckpointManager().maybe_save(interval=5)
            if saved:
                print(f"💾 Checkpoint automático: {saved}")
    except Exception:
        pass

    # Exibe cena gerada
    scene = _read(_SCENE_PATH, "")
    if scene:
        print("\n" + "─" * 55)
        print("  CENA:")
        print("─" * 55)
        print(scene[:3000])  # Limita para não explodir o terminal
    else:
        print("\n⚠ Nenhuma cena gerada.")

    print("\n" + "=" * 55)
    print("  TURNO CONCLUÍDO")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        prog="run_turn.py",
        description="Chronos RPG Engine — Execução de turno via CLI"
    )
    parser.add_argument("--action", default="explorar área",
                        help="Descrição da ação do jogador")
    parser.add_argument("--cmd", nargs="*", default=None,
                        help="Argumentos para o system_engine (ex: explore --dc medio)")
    args = parser.parse_args()

    run_turn(action_label=args.action, cmd_args=args.cmd)


if __name__ == "__main__":
    main()
