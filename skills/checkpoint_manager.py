#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
checkpoint_manager.py — Sistema de Checkpoints e Backups
Chronos RPG Engine v4.0

Salva snapshots completos do estado do jogo a cada 5 turnos.
Mantém os últimos 10 checkpoints.

O snapshot é montado em diretório temporário, recebe manifest com checksums
SHA-256 e só então é promovido para o ID final. Isso evita checkpoints
parcialmente gravados quando um turno falha no meio do caminho.

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

import os, sys, json, csv, shutil, datetime, argparse, hashlib
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
    "dynamic_items.json",
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
        with open(_LOG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_log(log: list) -> None:
    _atomic_json_write(_LOG_PATH, log, indent=2)


def _atomic_json_write(path: str, data, indent: int = 2) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file_with_manifest(src: str, dst: str, rel_path: str) -> dict:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = f"{dst}.tmp"
    shutil.copy2(src, tmp)
    checksum = _sha256_file(tmp)
    os.replace(tmp, dst)
    return {
        "path": rel_path.replace("\\", "/"),
        "bytes": os.path.getsize(dst),
        "sha256": checksum,
    }


def _manifest_errors(ckpt_dir: str, meta: dict) -> list[str]:
    """Valida checksums de checkpoints novos. Checkpoints antigos sem manifest passam."""
    manifest = meta.get("manifest", [])
    if not manifest:
        return []

    errors: list[str] = []
    for entry in manifest:
        rel = str(entry.get("path", ""))
        expected_hash = str(entry.get("sha256", ""))
        expected_size = entry.get("bytes")
        path = os.path.join(ckpt_dir, *rel.split("/"))

        if not os.path.exists(path):
            errors.append(f"AUSENTE_NO_CHECKPOINT: {rel}")
            continue

        try:
            actual_size = os.path.getsize(path)
            if expected_size is not None and int(expected_size) != actual_size:
                errors.append(f"TAMANHO_DIVERGENTE: {rel}")
            actual_hash = _sha256_file(path)
            if expected_hash and actual_hash != expected_hash:
                errors.append(f"SHA256_DIVERGENTE: {rel}")
        except Exception as e:
            errors.append(f"ERRO_VALIDANDO: {rel}: {e}")

    return errors


def _trim_log(log: list, protect_ids: Optional[set[str]] = None) -> list:
    """Mantém o limite de checkpoints sem apagar um alvo protegido por restore."""
    protected = protect_ids or set()
    while len(log) > MAX_CHECKPOINTS:
        remove_idx: Optional[int] = None
        for idx, entry in enumerate(log):
            if str(entry.get("id", "")) not in protected:
                remove_idx = idx
                break
        if remove_idx is None:
            break

        old = log.pop(remove_idx)
        old_dir = os.path.join(_CKPT_DIR, old["id"])
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir)
    return log


def _atomic_restore_file(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = f"{dst}.restore_tmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def _get_turno() -> int:
    """Lê o número do turno atual do chapter_tracker.json."""
    path = os.path.join(_STATE_DIR, "chapter_tracker.json")
    try:
        with open(path, encoding="utf-8") as f:
            ct = json.load(f)
        return ct.get("contagem", {}).get("interacoes_no_capitulo", 0)
    except Exception:
        return 0


def _get_chapter() -> str:
    """Lê o capítulo atual."""
    path = os.path.join(_STATE_DIR, "chapter_tracker.json")
    try:
        with open(path, encoding="utf-8") as f:
            ct = json.load(f)
        cap = ct.get("capitulo_atual", {})
        return f"Cap{cap.get('numero','?')}"
    except Exception:
        return "CapX"


def _get_hp() -> str:
    """Lê HP atual/max para o label do checkpoint."""
    path = os.path.join(_STATE_DIR, "character_sheet.json")
    try:
        with open(path, encoding="utf-8") as f:
            cs = json.load(f)
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

    def save_now(self, label: str = "", protect_ids: Optional[set[str]] = None) -> str:
        """
        Cria um snapshot completo agora.
        Retorna o ID do checkpoint (string).
        """
        log  = _load_log()
        now = datetime.datetime.now()
        ts   = now.strftime("%Y%m%d_%H%M%S_%f")
        turno = _get_turno()
        chapter = _get_chapter()
        hp = _get_hp()
        base_id = f"{ts}_{chapter}_T{turno}"
        if label:
            base_id = f"{ts}_{label}"

        ckpt_id = base_id
        suffix = 1
        while os.path.exists(os.path.join(_CKPT_DIR, ckpt_id)):
            ckpt_id = f"{base_id}_{suffix}"
            suffix += 1

        ckpt_dir = os.path.join(_CKPT_DIR, ckpt_id)
        tmp_dir = os.path.join(_CKPT_DIR, f".{ckpt_id}.tmp")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(os.path.join(tmp_dir, "current_state"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "world_context"), exist_ok=True)

        saved = []
        errors = []
        manifest = []

        try:
            # Copia arquivos de estado
            for fname in _STATE_FILES:
                src = os.path.join(_STATE_DIR, fname)
                rel = f"current_state/{fname}"
                if os.path.exists(src):
                    manifest.append(_copy_file_with_manifest(src, os.path.join(tmp_dir, "current_state", fname), rel))
                    saved.append(rel)
                else:
                    errors.append(f"AUSENTE: {rel}")

            # Copia arquivos de contexto
            for fname in _CTX_FILES:
                src = os.path.join(_CTX_DIR, fname)
                rel = f"world_context/{fname}"
                if os.path.exists(src):
                    manifest.append(_copy_file_with_manifest(src, os.path.join(tmp_dir, "world_context", fname), rel))
                    saved.append(rel)

            # Metadados do checkpoint
            meta = {
                "id":       ckpt_id,
                "ts":       ts,
                "created_at": now.isoformat(timespec="seconds"),
                "turno":    turno,
                "chapter":  chapter,
                "hp":       hp,
                "label":    label,
                "files":    saved,
                "manifest": manifest,
                "errors":   errors,
                "snapshot_version": 2,
            }
            _atomic_json_write(os.path.join(tmp_dir, "meta.json"), meta, indent=2)

            # Promove o snapshot apenas depois de todos os arquivos e meta existirem.
            os.replace(tmp_dir, ckpt_dir)

            # Adiciona ao log somente depois que o diretório final existe.
            log.append(meta)
            log = _trim_log(log, protect_ids=protect_ids)
            _save_log(log)
        except Exception:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            raise

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

        integrity_errors = _manifest_errors(ckpt_dir, meta)
        if integrity_errors:
            print("ERRO: checkpoint falhou na verificação de integridade.")
            for e in integrity_errors[:10]:
                print(f"  ⚠ {e}")
            return False

        # Backup do estado atual antes de restaurar
        print("  Criando backup do estado atual antes de restaurar...")
        self.save_now("pre_restore", protect_ids={str(meta["id"])})

        # Restaura arquivos de estado
        restored: int = 0
        for fname in _STATE_FILES:
            src = os.path.join(ckpt_dir, "current_state", fname)
            dst = os.path.join(_STATE_DIR, fname)
            if os.path.exists(src):
                _atomic_restore_file(src, dst)
                restored += 1  # type: ignore

        # Restaura arquivos de contexto
        for fname in _CTX_FILES:
            src = os.path.join(ckpt_dir, "world_context", fname)
            dst = os.path.join(_CTX_DIR, fname)
            if os.path.exists(src):
                _atomic_restore_file(src, dst)
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
