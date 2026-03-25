#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
checkpoint_manager.py — Sistema de Checkpoints e Backups
Chronos RPG Engine v4.0

Salva snapshots completos do estado do jogo a cada 5 turnos.
Mantém os últimos 10 checkpoints (rota compacta com shutil.copy).

USO:
  from checkpoint_manager import CheckpointManager
  ckpt = CheckpointManager()
  ckpt.maybe_save()          # salva se turno % 5 == 0
  ckpt.save_now("pre_boss")  # salva com label manual
  ckpt.restore(3)            # restaura checkpoint 3
  ckpt.list_checkpoints()    # lista todos

CLI:
  python checkpoint_manager.py list
  python checkpoint_manager.py save --label pre_boss
  python checkpoint_manager.py restore --id 3
  python checkpoint_manager.py diff --id 3
"""

import os, sys, json, csv, shutil, datetime, argparse
from typing import Optional

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_CTX_DIR   = os.path.join(_PROJ, "world_context")
_CKPT_DIR  = os.path.join(_PROJ, "checkpoints")
_LOG_PATH  = os.path.join(_CKPT_DIR, "checkpoint_log.json")

# Arquivos de estado que entram no snapshot
_STATE_FILES = [
    "character_sheet.json",
    "active_combat.json",
    "chapter_tracker.json",
    "world_map.json",
    "inventory.csv",
    "active_quests.md",
]

# Arquivos de world_context que entram (a narrativa importa)
_CTX_FILES = [
    "campaign_log.md",
    "story_bible.md",
    "npc_dossier.md",
    "bestiary.md",
]

MAX_CHECKPOINTS = 10


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_log() -> list:
    """Carrega o log de checkpoints (lista de dicts)."""
    if not os.path.exists(_LOG_PATH):
        return []
    try:
        return json.load(open(_LOG_PATH, encoding="utf-8"))
    except Exception:
        return []


def _save_log(log: list) -> None:
    os.makedirs(_CKPT_DIR, exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _get_turno() -> int:
    """Lê o número do turno atual do chapter_tracker.json."""
    path = os.path.join(_STATE_DIR, "chapter_tracker.json")
    try:
        ct = json.load(open(path, encoding="utf-8"))
        return ct.get("contagem", {}).get("interacoes_no_capitulo", 0)
    except Exception:
        return 0


def _get_chapter() -> str:
    """Lê o capítulo atual."""
    path = os.path.join(_STATE_DIR, "chapter_tracker.json")
    try:
        ct = json.load(open(path, encoding="utf-8"))
        cap = ct.get("capitulo_atual", {})
        return f"Cap{cap.get('numero','?')}"
    except Exception:
        return "CapX"


def _get_hp() -> str:
    """Lê HP atual/max para o label do checkpoint."""
    path = os.path.join(_STATE_DIR, "character_sheet.json")
    try:
        cs = json.load(open(path, encoding="utf-8"))
        hp = cs.get("vitals", {}).get("hp", {})
        return f"HP{hp.get('current','?')}/{hp.get('max','?')}"
    except Exception:
        return "HP?/?"


# ─────────────────────────────────────────────────────────────────────────────
# CheckpointManager
# ─────────────────────────────────────────────────────────────────────────────

class CheckpointManager:

    def maybe_save(self, interval: int = 5) -> Optional[str]:
        """
        Salva checkpoint se turno_atual % interval == 0.
        Retorna o ID do checkpoint salvo ou None.
        """
        turno = _get_turno()
        if turno > 0 and turno % interval == 0:
            return self.save_now(f"auto_turno{turno}")
        return None

    def save_now(self, label: str = "") -> str:
        """
        Cria um snapshot completo agora.
        Retorna o ID do checkpoint (string).
        """
        log  = _load_log()
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        turno = _get_turno()
        ckpt_id = f"{ts}_{_get_chapter()}_T{turno}"
        if label:
            ckpt_id = f"{ts}_{label}"

        ckpt_dir = os.path.join(_CKPT_DIR, ckpt_id)
        os.makedirs(ckpt_dir, exist_ok=True)
        os.makedirs(os.path.join(ckpt_dir, "current_state"), exist_ok=True)
        os.makedirs(os.path.join(ckpt_dir, "world_context"), exist_ok=True)

        saved = []
        errors = []

        # Copia arquivos de estado
        for fname in _STATE_FILES:
            src = os.path.join(_STATE_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ckpt_dir, "current_state", fname))
                saved.append(f"current_state/{fname}")
            else:
                errors.append(f"AUSENTE: {fname}")

        # Copia arquivos de contexto
        for fname in _CTX_FILES:
            src = os.path.join(_CTX_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ckpt_dir, "world_context", fname))
                saved.append(f"world_context/{fname}")

        # Metadados do checkpoint
        meta = {
            "id":      ckpt_id,
            "ts":      ts,
            "turno":   turno,
            "chapter": _get_chapter(),
            "hp":      _get_hp(),
            "label":   label,
            "files":   saved,
            "errors":  errors,
        }
        with open(os.path.join(ckpt_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Adiciona ao log
        log.append(meta)

        # Mantém apenas os últimos MAX_CHECKPOINTS
        if len(log) > MAX_CHECKPOINTS:
            old = log.pop(0)
            old_dir = os.path.join(_CKPT_DIR, old["id"])
            if os.path.exists(old_dir):
                shutil.rmtree(old_dir)

        _save_log(log)

        print(f"✓ Checkpoint salvo: {ckpt_id}")
        print(f"  Arquivos: {len(saved)} | Erros: {len(errors)}")
        if errors:
            for e in errors:
                print(f"  ⚠ {e}")

        return ckpt_id

    def restore(self, index_or_id) -> bool:
        """
        Restaura um checkpoint pelo índice (0=mais novo, -1=mais antigo)
        ou pelo ID string.
        Faz backup do estado atual antes de restaurar.
        """
        log = _load_log()
        if not log:
            print("ERRO: Nenhum checkpoint encontrado.")
            return False

        # Resolve qual checkpoint
        meta: Optional[dict] = None
        if isinstance(index_or_id, int):
            idx = index_or_id
            if idx < 0 or idx >= len(log):
                # Aceita índice reverso
                idx = len(log) + idx if index_or_id < 0 else idx
            if 0 <= idx < len(log):
                meta = log[idx]
        else:
            for entry in log:
                if entry["id"] == index_or_id or entry["id"].startswith(str(index_or_id)):
                    meta = entry
                    break

        if not meta:
            print(f"ERRO: Checkpoint '{index_or_id}' não encontrado.")
            return False

        ckpt_dir = os.path.join(_CKPT_DIR, meta["id"])
        if not os.path.exists(ckpt_dir):
            print(f"ERRO: Diretório do checkpoint não encontrado: {ckpt_dir}")
            return False

        # Backup do estado atual antes de restaurar
        print("  Criando backup do estado atual antes de restaurar...")
        self.save_now("pre_restore")

        # Restaura arquivos de estado
        restored: int = 0
        for fname in _STATE_FILES:
            src = os.path.join(ckpt_dir, "current_state", fname)
            dst = os.path.join(_STATE_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                restored += 1  # type: ignore

        # Restaura arquivos de contexto
        for fname in _CTX_FILES:
            src = os.path.join(ckpt_dir, "world_context", fname)
            dst = os.path.join(_CTX_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                restored += 1  # type: ignore

        print(f"✓ Checkpoint restaurado: {meta['id']}")
        print(f"  Turno: {meta['turno']} | {meta['chapter']} | {meta['hp']}")
        print(f"  {restored} arquivos restaurados.")
        return True

    def list_checkpoints(self) -> None:
        """Imprime lista de checkpoints disponíveis."""
        log = _load_log()
        if not log:
            print("Nenhum checkpoint salvo ainda.")
            return
        print(f"\n{'─'*60}")
        print(f"  CHECKPOINTS ({len(log)}/{MAX_CHECKPOINTS} slots)")
        print(f"{'─'*60}")
        for i, meta in enumerate(log):
            label_str = f" [{meta['label']}]" if meta.get("label") else ""
            errors_str = f" ⚠{len(meta.get('errors',[]))}err" if meta.get("errors") else ""
            print(f"  [{i:>2}] {meta['ts'][:16]}  {meta['chapter']:<8}  T{meta['turno']:<4}  {meta['hp']:<12}{label_str}{errors_str}")
        print(f"{'─'*60}")
        print(f"  Restaurar: python checkpoint_manager.py restore --id <índice>")

    def diff(self, index_or_id) -> None:
        """
        Mostra diferenças de HP/XP/inventário entre um checkpoint e o estado atual.
        """
        log = _load_log()
        meta = None
        if isinstance(index_or_id, int) and 0 <= index_or_id < len(log):
            meta = log[index_or_id]
        else:
            for entry in log:
                if entry["id"] == str(index_or_id):
                    meta = entry
                    break
        if not meta:
            print(f"Checkpoint não encontrado: {index_or_id}")
            return

        ckpt_dir = os.path.join(_CKPT_DIR, meta["id"])

        # Compara character_sheet
        try:
            cs_old = json.load(open(os.path.join(ckpt_dir, "current_state", "character_sheet.json"), encoding="utf-8"))
            cs_now = json.load(open(os.path.join(_STATE_DIR, "character_sheet.json"), encoding="utf-8"))

            v_old = cs_old.get("vitals", {})
            v_now = cs_now.get("vitals", {})
            p_old = cs_old.get("progression", {})
            p_now = cs_now.get("progression", {})

            hp_old = v_old.get("hp", {}).get("current", "?")
            hp_now = v_now.get("hp", {}).get("current", "?")
            xp_old = p_old.get("xp_current", "?")
            xp_now = p_now.get("xp_current", "?")
            lv_old = p_old.get("level", "?")
            lv_now = p_now.get("level", "?")

            print(f"\n  DIFF: {meta['id']}")
            print(f"  {'Campo':<20} {'Checkpoint':>12} {'Agora':>12} {'Delta':>10}")
            print(f"  {'─'*58}")
            for campo, v1, v2 in [("HP", hp_old, hp_now), ("XP", xp_old, xp_now), ("Nível", lv_old, lv_now)]:
                try:
                    delta = f"{int(v2)-int(v1):+}"  # type: ignore[arg-type]
                except Exception:
                    delta = "?"
                print(f"  {campo:<20} {str(v1):>12} {str(v2):>12} {delta:>10}")
        except Exception as e:
            print(f"  ERRO ao comparar: {e}")

        # Compara inventário (contagem de linhas)
        try:
            inv_old = list(csv.DictReader(open(os.path.join(ckpt_dir, "current_state", "inventory.csv"), encoding="utf-8")))
            inv_now = list(csv.DictReader(open(os.path.join(_STATE_DIR, "inventory.csv"), encoding="utf-8")))
            print(f"  {'Inventário (linhas)':<20} {len(inv_old):>12} {len(inv_now):>12} {len(inv_now)-len(inv_old):>+10}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Checkpoint Manager — Chronos RPG v4.0")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="Lista todos os checkpoints")

    p_save = sub.add_parser("save", help="Salva checkpoint agora")
    p_save.add_argument("--label", default="manual", help="Label do checkpoint")

    p_restore = sub.add_parser("restore", help="Restaura checkpoint")
    p_restore.add_argument("--id", required=True, help="Índice (0,1,2...) ou ID string")

    p_diff = sub.add_parser("diff", help="Mostra diferenças de um checkpoint")
    p_diff.add_argument("--id", required=True, help="Índice ou ID")

    args = parser.parse_args()
    ckpt = CheckpointManager()

    if args.cmd == "list":
        ckpt.list_checkpoints()
    elif args.cmd == "save":
        ckpt.save_now(args.label)
    elif args.cmd == "restore":
        try:
            idx = int(args.id)
        except ValueError:
            idx = args.id  # type: ignore[assignment]
        ckpt.restore(idx)
    elif args.cmd == "diff":
        try:
            idx = int(args.id)
        except ValueError:
            idx = args.id  # type: ignore[assignment]
        ckpt.diff(idx)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()