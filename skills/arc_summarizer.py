#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arc_summarizer.py — Sumarizador de Arcos
Chronos RPG Engine v4.0

Resolve o problema de crescimento infinito da story_bible.md.
Quando um arco é encerrado, o Lore_Archivist chama este módulo para:

  1. Extrair todos os capítulos do arco fechado
  2. Enviar ao Gemini com prompt de compressão narrativa
  3. Substituir as entradas individuais por 1 bloco comprimido
  4. Preservar os "momentos imortais" (eventos marcados com ★ ou [KEY])
  5. Mover o texto raw para um arquivo de arquivo histórico

USO:
  from arc_summarizer import ArcSummarizer
  s = ArcSummarizer()
  s.summarize_arc("ARC 1 — ORIGEM TERRESTRE")

  # Ou via CLI:
  python arc_summarizer.py --arc "ARC 1 — ORIGEM TERRESTRE"
  python arc_summarizer.py --auto          # detecta arcos fechados automaticamente
  python arc_summarizer.py --preview       # mostra o que comprimiria
  python arc_summarizer.py --check         # mostra status da story_bible
"""

import os, sys, json, re, argparse, datetime
from typing import Optional

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_CTX_DIR   = os.path.join(_PROJ, "world_context")
_ARCHIVE_DIR = os.path.join(_PROJ, "story_archive")

_CT_PATH          = os.path.join(_STATE_DIR, "chapter_tracker.json")
_STORY_BIBLE_PATH = os.path.join(_CTX_DIR,   "story_bible.md")
_SUMMARY_INDEX    = os.path.join(_CTX_DIR,   "arc_summaries.md")

# Tamanho em chars acima do qual a story_bible é considerada "grande demais"
STORY_BIBLE_WARNING_SIZE = 8_000
STORY_BIBLE_CRITICAL_SIZE = 15_000

# ─────────────────────────────────────────────────────────────────────────────
# Helpers de IO
# ─────────────────────────────────────────────────────────────────────────────

def _read(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    return open(path, encoding="utf-8").read()


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _append(path: str, content: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


def _load_ct() -> dict:
    try:
        return json.load(open(_CT_PATH, encoding="utf-8"))
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Parser da story_bible
# ─────────────────────────────────────────────────────────────────────────────

def parse_story_bible(content: str) -> list[dict]:
    """
    Divide a story_bible.md em blocos por entrada (separadas por '---').
    Cada bloco tem:
      - raw: texto completo
      - turno: label do turno (ex: "TURNO_12")
      - arc: arco detectado (ex: "ARC 1")
      - is_key: True se contém ★ ou [KEY] — nunca comprimido
      - is_summary: True se já é um resumo de arco
    """
    blocks: list[dict] = []
    sections = re.split(r'\n---\n', content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Detecta label de turno
        turno_match = re.search(r'\*\*(TURNO[_\s\d]+|Cap\s*\d+[^*]*)\*\*', section)
        turno = turno_match.group(1).strip() if turno_match else "?"

        # Detecta arco
        arc_match = re.search(r'ARC\s+\d+[^\n]*', section, re.IGNORECASE)
        arc = arc_match.group(0).strip() if arc_match else None

        # Momentos imortais
        is_key = bool(re.search(r'[★\[KEY\]]', section))

        # Já é um resumo gerado por este módulo?
        is_summary = "## RESUMO DO ARCO" in section or "## ARC SUMMARY" in section

        blocks.append({
            "raw":        section,
            "turno":      turno,
            "arc":        arc,
            "is_key":     is_key,
            "is_summary": is_summary,
            "chars":      len(section),
        })

    return blocks


def get_story_bible_status() -> dict:
    """Retorna métricas da story_bible para diagnóstico."""
    content = _read(_STORY_BIBLE_PATH, "")
    blocks = parse_story_bible(content)
    total_chars = len(content)
    return {
        "total_chars":   total_chars,
        "total_blocks":  len(blocks),
        "key_blocks":    sum(1 for b in blocks if b["is_key"]),
        "summary_blocks": sum(1 for b in blocks if b["is_summary"]),
        "status":        ("CRÍTICO" if total_chars > STORY_BIBLE_CRITICAL_SIZE
                         else "ALERTA" if total_chars > STORY_BIBLE_WARNING_SIZE
                         else "OK"),
        "arcos_detectados": list({b["arc"] for b in blocks if b["arc"]}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Geração do resumo via Gemini
# ─────────────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> Optional[str]:
    """Chama a API Gemini para gerar resumo. Retorna None se falhar."""
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            env_path = os.path.join(_PROJ, ".env")
            if os.path.exists(env_path):
                for line in open(env_path, encoding="utf-8"):
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2000),
        )
        return resp.text
    except Exception as e:
        print(f"  [Gemini erro]: {e}")
        return None


def build_summary_prompt(arc_name: str, blocks: list[dict]) -> str:
    """Constrói o prompt de sumarização para o Gemini."""
    raw_text = "\n\n---\n\n".join(b["raw"] for b in blocks)
    key_moments = [b["raw"] for b in blocks if b["is_key"]]
    key_section = ""
    if key_moments:
        key_section = "\n\nMOMENTOS QUE DEVEM SER PRESERVADOS LITERALMENTE:\n" + "\n---\n".join(key_moments)

    raw_text_sliced = raw_text[:8000]  # type: ignore
    return f"""Você é o Lore_Archivist do jogo Chronos RPG. 
Sua tarefa é comprimir os registros do {arc_name} em um resumo narrativo compacto.

REGRAS DE COMPRESSÃO:
- O resumo deve ter NO MÁXIMO 800 palavras
- Preserve todos os nomes próprios, locais e eventos cruciais
- Use voz de diário íntimo de Ferro (1ª pessoa, Hard Sci-Fi, visceral)
- Marque com ★ os 3-5 momentos mais importantes
- Preserve INTEGRALMENTE os momentos marcados abaixo
- Termine com "Estado ao fim do arco:" seguido dos vitais de Ferro
- Formato: Markdown com headers ## para seções (Chegada, Conflito, Resolução)

{key_section}

REGISTROS COMPLETOS DO ARCO PARA COMPRIMIR:
{raw_text_sliced}

RESUMO COMPRIMIDO:"""


# ─────────────────────────────────────────────────────────────────────────────
# ArcSummarizer
# ─────────────────────────────────────────────────────────────────────────────

class ArcSummarizer:

    def check(self) -> None:
        """Imprime diagnóstico da story_bible."""
        status = get_story_bible_status()
        icon = {"OK": "✓", "ALERTA": "⚠", "CRÍTICO": "✗"}.get(status["status"], "?")
        print(f"\n{icon} story_bible.md — {status['status']}")
        print(f"  {status['total_chars']:,} chars | {status['total_blocks']} blocos | {status['key_blocks']} KEY | {status['summary_blocks']} resumos")
        if status["total_chars"] > STORY_BIBLE_WARNING_SIZE:
            needed = status["total_chars"] - STORY_BIBLE_WARNING_SIZE
            print(f"  Acima do limite em {needed:,} chars — recomendo sumarizar um arco.")
        if status["arcos_detectados"]:
            print(f"  Arcos detectados: {', '.join(status['arcos_detectados'])}")
        print(f"  Limite ALERTA: {STORY_BIBLE_WARNING_SIZE:,} | CRÍTICO: {STORY_BIBLE_CRITICAL_SIZE:,}")

    def summarize_arc(self, arc_name: str, preview: bool = False, force_manual: bool = False) -> bool:
        """
        Comprime todos os blocos do arc_name em um único resumo.
        Se preview=True, imprime o resumo mas não salva.
        Se force_manual=True, gera resumo local sem Gemini (fallback).
        """
        content = _read(_STORY_BIBLE_PATH, "")
        if not content:
            print("story_bible.md vazia ou não encontrada.")
            return False

        blocks = parse_story_bible(content)
        # Filtra blocos do arco (não comprime KEY nem outros resumos)
        arc_blocks      = [b for b in blocks if b.get("arc") == arc_name and not b["is_summary"]]
        preserve_blocks = [b for b in blocks if b.get("arc") != arc_name or b["is_summary"]]

        if not arc_blocks:
            print(f"Nenhum bloco encontrado para: {arc_name}")
            print(f"Arcos disponíveis: {[b['arc'] for b in blocks if b['arc']]}")
            return False

        print(f"\nComprimindo {arc_name}:")
        print(f"  {len(arc_blocks)} blocos → 1 resumo")
        print(f"  {sum(b['chars'] for b in arc_blocks):,} chars → ~800 palavras")
        key_count = sum(1 for b in arc_blocks if b["is_key"])
        if key_count:
            print(f"  {key_count} momentos KEY preservados literalmente.")

        # Gera resumo via Gemini
        summary_text: Optional[str] = None
        if not force_manual:
            print("  Chamando Gemini para sumarização...")
            prompt = build_summary_prompt(arc_name, arc_blocks)
            summary_text = _call_gemini(prompt)
            if summary_text:
                print(f"  ✓ Gemini gerou resumo ({len(summary_text):,} chars)")
            else:
                print("  ✗ Gemini indisponível — usando resumo automático local.")

        # Fallback: resumo automático sem Gemini
        if not summary_text:
            summary_text = self._build_fallback_summary(arc_name, arc_blocks)

        # Monta bloco final do resumo
        ts = datetime.datetime.now().strftime("%Y-%m-%d")
        summary_block = f"""## RESUMO DO ARCO — {arc_name}
*Comprimido em {ts} | {len(arc_blocks)} entradas → resumo*

{summary_text.strip()}
"""
        if preview:
            print(f"\n{'─'*55}")
            print("PREVIEW DO RESUMO GERADO:")
            print(f"{'─'*55}")
            summary_preview = summary_block[:2000]  # type: ignore
            print(summary_preview)
            if len(summary_block) > 2000:
                print(f"... [{len(summary_block)-2000} chars adicionais]")
            return True

        # Arquiva o texto original
        os.makedirs(_ARCHIVE_DIR, exist_ok=True)
        archive_name = re.sub(r'[^\w\-]', '_', arc_name) + f"_{ts}.md"
        archive_path = os.path.join(_ARCHIVE_DIR, archive_name)
        raw_archive  = f"# ARQUIVO RAW — {arc_name}\n*Arquivado em {ts}*\n\n"
        raw_archive += "\n\n---\n\n".join(b["raw"] for b in arc_blocks)
        _write(archive_path, raw_archive)
        print(f"  ✓ Texto original arquivado: {archive_path}")

        # Reconstrói a story_bible com os blocos preservados + resumo
        new_blocks = preserve_blocks + [{"raw": summary_block, "is_summary": True}]
        new_content = "\n\n---\n\n".join(b["raw"] for b in new_blocks)
        _write(_STORY_BIBLE_PATH, new_content)
        print(f"  ✓ story_bible.md reescrita: {len(new_content):,} chars (era {len(content):,})")

        # Atualiza o índice de resumos
        summary_text_sliced = summary_text[:400]  # type: ignore
        index_entry = f"\n\n---\n\n## {arc_name} ({ts})\n\n{summary_text_sliced.strip()}...\n"
        _append(_SUMMARY_INDEX, index_entry)
        print(f"  ✓ arc_summaries.md atualizado.")

        return True

    def auto_summarize(self, preview: bool = False) -> int:
        """
        Detecta arcos com status ENCERRADO no chapter_tracker e os sumariza.
        Retorna o número de arcos comprimidos.
        """
        ct = _load_ct()
        historico = ct.get("historico_capitulos", [])
        arcos_encerrados: set[str] = set()
        for cap in historico:
            arco = cap.get("arco", "")
            if arco:
                arcos_encerrados.add(arco)

        # Remove arcos que já têm resumo
        content = _read(_STORY_BIBLE_PATH, "")
        compressed = 0
        for arco in arcos_encerrados:
            if f"## RESUMO DO ARCO — {arco}" in content:
                print(f"  [SKIP] {arco} já resumido.")
                continue
            print(f"  [AUTO] Sumarizando: {arco}")
            ok = self.summarize_arc(arco, preview=preview)
            if ok:
                compressed += 1  # type: ignore

        if compressed == 0:
            print("  Nenhum arco pendente para sumarização automática.")

        return compressed

    def _build_fallback_summary(self, arc_name: str, blocks: list[dict]) -> str:
        """
        Gera um resumo estruturado localmente sem Gemini.
        Extrai frases-chave de cada bloco.
        """
        lines = [f"*Resumo gerado automaticamente (sem IA) — {len(blocks)} entradas.*\n"]

        key_moments = [b for b in blocks if b["is_key"]]
        regular     = [b for b in blocks if not b["is_key"]]

        if key_moments:
            lines.append("### ★ Momentos Decisivos\n")
            for b in key_moments:
                # Pega as primeiras 3 linhas não-vazias
                relevant = [ln for ln in b["raw"].split("\n") if ln.strip() and not ln.startswith("**")]
                relevant_sliced = relevant[:3]  # type: ignore
                lines.append("\n".join(relevant_sliced))
                lines.append("")

        if regular:
            lines.append("### Eventos Registrados\n")
            regular_sliced = regular[:8]  # type: ignore
            for b in regular_sliced:  # máximo 8 blocos no fallback
                # Primeira linha com conteúdo
                first = next((ln.strip() for ln in b["raw"].split("\n") if len(ln.strip()) > 20), "")
                if first:
                    turno = b.get("turno", "?")
                    first_sliced = first[:120]  # type: ignore
                    lines.append(f"- **{turno}**: {first_sliced}")

        lines.append(f"\n*Estado ao fim do arco: registrado em {len(blocks)} turnos.*")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Arc Summarizer — Chronos RPG v4.0")
    parser.add_argument("--arc",     help="Nome do arco para sumarizar (ex: 'ARC 1 — ORIGEM TERRESTRE')")
    parser.add_argument("--auto",    action="store_true", help="Sumariza arcos encerrados automaticamente")
    parser.add_argument("--preview", action="store_true", help="Mostra resumo sem salvar")
    parser.add_argument("--check",   action="store_true", help="Mostra status da story_bible")
    parser.add_argument("--manual",  action="store_true", help="Usa resumo local (sem Gemini)")
    args = parser.parse_args()

    s = ArcSummarizer()

    if args.check:
        s.check()
    elif args.auto:
        count = s.auto_summarize(preview=args.preview)
        print(f"\n{count} arco(s) comprimido(s).")
    elif args.arc:
        ok = s.summarize_arc(args.arc, preview=args.preview, force_manual=args.manual)
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()
        print("\n  Exemplo: python arc_summarizer.py --check")
        print("  Exemplo: python arc_summarizer.py --arc 'ARC 1 — ORIGEM TERRESTRE' --preview")


if __name__ == "__main__":
    main()