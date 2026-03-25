#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
world_context_loader.py — Carregador de Contexto de Mundo
Chronos RPG Engine v4.0

Utilitário central: lê todos os arquivos de contexto do mundo e retorna
strings formatadas para injeção nos prompts do Gemini.

Origem dos arquivos:
  bestiary.md      → bestiary.md       (Architect cria novas entradas)
  world_bible.md   → world_bible.md    (estático)
  npc_dossier.md   → npc_dossier.md    (Lore_Archivist atualiza)
  story_bible.md   → story_bible.md    (Lore_Archivist faz append)
  tone_guide.md    → tone_guide.md     (estático)
  campaign_log.md  → campaign_log.md   (Lore_Archivist faz append)
  active_quests.md → active_quests.md  (Lore_Archivist atualiza)
"""

import os

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_CTX_DIR   = os.path.join(_PROJ, "world_context")
_STATE_DIR = os.path.join(_PROJ, "current_state")

# Caminhos canônicos
PATHS = {
    "bestiary":      os.path.join(_CTX_DIR,   "bestiary.md"),
    "world_bible":   os.path.join(_CTX_DIR,   "world_bible.md"),
    "npc_dossier":   os.path.join(_CTX_DIR,   "npc_dossier.md"),
    "story_bible":   os.path.join(_CTX_DIR,   "story_bible.md"),
    "tone_guide":    os.path.join(_CTX_DIR,   "tone_guide.md"),
    "campaign_log":  os.path.join(_CTX_DIR,   "campaign_log.md"),
    "active_quests": os.path.join(_STATE_DIR, "active_quests.md"),
}


def _read(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    return open(path, encoding="utf-8").read()


# ─────────────────────────────────────────────────────────────────────────────
# Efeitos de clima/período — dados inline (sem import de outros módulos)
# world_context_loader é leaf: NÃO deve importar outros módulos do projeto.
# ─────────────────────────────────────────────────────────────────────────────

_WEATHER_EFFECTS = {
    "LIMPO":         "",
    "NEBLINA":       "Visibilidade reduzida. Testes de Percepção com desvantagem.",
    "CHUVA":         "Solo escorregadio. Testes de DES com penalidade. Trilhas apagadas.",
    "TEMPESTADE":    "Vento forte. Barulho encobre movimentos. Combate à distância prejudicado.",
    "RADIAÇÃO":      "Zona contaminada. -1 HP por turno sem proteção. Chip alerta.",
    "CALOR EXTREMO": "Desidratação acelerada. SEDE decai 2x mais rápido.",
    "FRIO INTENSO":  "Hipotermia ameaça. EXAUSTÃO decai 2x mais rápido sem abrigo.",
    "VENTOS ÁCIDOS": "Equipamentos sofrem desgaste. Durabilidade -1 por exposição.",
}

_PERIOD_EFFECTS = {
    "DIA":        "",
    "TARDE":      "Calor do sol no ápice. Vigilância humana no pico.",
    "NOITE":      "Visibilidade reduzida. Criaturas noturnas ativas. Patrulhas intensificadas.",
    "MADRUGADA":  "Menor vigilância. Temperatura mínima. Névoa provável.",
}

def get_weather_effect(clima: str) -> str:
    """Retorna descrição do efeito de clima atual (string vazia se LIMPO)."""
    return _WEATHER_EFFECTS.get(clima, "")


def get_period_effect(periodo: str) -> str:
    """Retorna descrição do efeito do período atual (string vazia se DIA)."""
    return _PERIOD_EFFECTS.get(periodo, "")



def _clip(s: str, n: int) -> str:
    """Retorna os primeiros n caracteres. Helper Pyre2-safe."""
    length = max(0, n)
    return s[:length]  # type: ignore[return-value]


def _tail(s: str, n: int) -> str:
    """Retorna os últimos n caracteres. Helper Pyre2-safe."""
    length = max(0, n)
    return s[-length:] if length else ""  # type: ignore[return-value]

def load_bestiary(max_chars: int = 6000) -> str:
    """
    Carrega o bestiário. Limita a max_chars para não explodir o contexto.
    Sempre inclui o TEMPLATE completo + criaturas do arco atual no início.
    """
    raw: str = _read(PATHS["bestiary"], "")
    if not raw:
        return "(bestiary.md não encontrado)"
    # Se couber, retorna tudo
    if len(raw) <= max_chars:
        return raw
    # Senão, retorna início + fim (template + últimas criaturas adicionadas)
    half = max_chars // 2
    return _clip(raw, half) + "\n\n[...bestiary truncado...]\n\n" + _tail(raw, half)


def load_world_bible(max_chars: int = 3000) -> str:
    raw: str = _read(PATHS["world_bible"], "(world_bible.md não encontrado)")
    return _clip(raw, max_chars) if len(raw) > max_chars else raw


def load_npc_dossier(max_chars: int = 2000) -> str:
    raw: str = _read(PATHS["npc_dossier"], "(npc_dossier.md não encontrado)")
    return _clip(raw, max_chars) if len(raw) > max_chars else raw


def load_story_bible_recent(max_chars: int = 2000) -> str:
    """Carrega apenas as entradas mais recentes da story_bible (últimas N chars)."""
    raw: str = _read(PATHS["story_bible"], "(story_bible.md vazia)")
    if len(raw) <= max_chars:
        return raw
    return "[...entradas anteriores omitidas...]\n\n" + _tail(raw, max_chars)


def load_tone_guide() -> str:
    return _read(PATHS["tone_guide"], "Tom: Hard Sci-Fi, visceral, sombrio. Show don't tell.")


def load_campaign_log_recent(max_chars: int = 1500) -> str:
    """Últimas entradas do diário de Ferro."""
    raw: str = _read(PATHS["campaign_log"], "(campaign_log.md vazio)")
    if len(raw) <= max_chars:
        return raw
    return "[...entradas anteriores omitidas...]\n\n" + _tail(raw, max_chars)


def load_campaign_log_for_archivist() -> str:
    """
    Carrega o campaign_log de forma otimizada para o Lore_Archivist:
    - ÍNDICE COMPLETO: todas as linhas ### (títulos) — para evitar duplicatas
    - ENTRADAS RECENTES COMPLETAS: últimas 8 entradas — para contexto narrativo
    Muito mais eficiente que truncar por chars (cobre 100+ eventos sem explodir o contexto).
    """
    import re as _re
    raw: str = _read(PATHS["campaign_log"], "(campaign_log.md vazio)")

    # Remove blocos de template/exemplo (dentro de ```)
    no_code = _re.sub(r"```.*?```", "", raw, flags=_re.DOTALL)

    # Extrai todos os títulos de eventos reais
    titles = _re.findall(
        r"(###\s*(?:\[EVENTO\s+\d+:[^\]\n]+\]|EVENTO\s*:[^\n]+))",
        no_code, _re.IGNORECASE
    )

    # Extrai as últimas 8 entradas completas
    parts = _re.split(
        r"(?=###\s*(?:\[EVENTO|\bEVENTO\s*:))",
        no_code, flags=_re.IGNORECASE
    )
    real_entries: list[str] = [
        str(p).strip() for p in parts
        if _re.match(r"###\s*(?:\[EVENTO|\bEVENTO\s*:)", str(p).strip(), _re.IGNORECASE)
    ]
    start_idx = max(0, len(real_entries) - 8)
    last_entries: list[str] = [real_entries[i] for i in range(start_idx, len(real_entries))]

    total = len(real_entries)
    idx_block = "\n".join(titles) if titles else "(nenhum evento registrado)"
    recent_block = "\n\n".join(last_entries) if last_entries else "(sem entradas)"

    return (
        f"── ÍNDICE DE EVENTOS ({total} total — use para evitar títulos repetidos) ──\n"
        f"{idx_block}\n\n"
        f"── ÚLTIMAS {len(last_entries)} ENTRADAS COMPLETAS ──\n"
        f"{recent_block}"
    )


def load_active_quests() -> str:
    return _read(PATHS["active_quests"], "# LOG DE MISSÕES\n\n(Sem missões registradas)")


def build_world_context_for_gm() -> str:
    """
    Constrói o bloco de contexto de mundo para o Game_Master.
    Inclui: tone_guide, world_bible resumida, NPCs, story_bible recente, quests.
    NÃO inclui o bestiário completo (muito grande) — inclui apenas criaturas em combate ativo.
    """
    return f"""
═══════════════════════════════════════════════════════
  CONTEXTO DE MUNDO
═══════════════════════════════════════════════════════

── TOM E ESTILO ────────────────────────────────────────
{load_tone_guide()}

── BÍBLIA DO UNIVERSO (resumo) ─────────────────────────
{load_world_bible(max_chars=2000)}

── NPCS CONHECIDOS ──────────────────────────────────────
{load_npc_dossier(max_chars=1500)}

── HISTÓRIA RECENTE (story_bible) ──────────────────────
{load_story_bible_recent(max_chars=1500)}

── MISSÕES ATIVAS ───────────────────────────────────────
{load_active_quests()}

── DIÁRIO RECENTE (campaign_log) ────────────────────────
{load_campaign_log_recent(max_chars=1000)}
"""


def build_world_context_for_archivist() -> str:
    """
    Contexto de mundo para o Lore_Archivist.
    Inclui tudo para que ele possa detectar contradições e novidades.
    """
    return f"""
═══════════════════════════════════════════════════════
  CONTEXTO DE MUNDO COMPLETO (para arquivamento)
═══════════════════════════════════════════════════════

── NPCS REGISTRADOS ─────────────────────────────────────
{load_npc_dossier(max_chars=3000)}

── BESTIÁRIO (criaturas conhecidas) ─────────────────────
{load_bestiary(max_chars=4000)}

── HISTÓRIA ARQUIVADA ───────────────────────────────────
{load_story_bible_recent(max_chars=2000)}

── MISSÕES ATIVAS ───────────────────────────────────────
{load_active_quests()}

── DIÁRIO DE FERRO (campaign_log) ───────────────────────
{load_campaign_log_for_archivist()}

── BÍBLIA DO UNIVERSO ───────────────────────────────────
{load_world_bible(max_chars=1500)}
"""


def build_world_context_for_expansion() -> str:
    """
    Contexto para o PROTOCOLO DE EXPANSÃO.
    Precisa do bestiário completo, world_bible e loot schemas.
    """
    return f"""
── BESTIÁRIO COMPLETO (para verificar se entidade já existe) ──
{load_bestiary(max_chars=8000)}

── BÍBLIA DO UNIVERSO (plausibilidade Hard Sci-Fi) ────────────
{load_world_bible(max_chars=3000)}
"""


def get_creature_from_bestiary(name: str) -> str:
    """
    Busca uma criatura específica no bestiário por nome.
    Retorna o bloco completo da entrada ou string vazia.
    """
    raw: str = _read(PATHS["bestiary"], "")
    if not raw:
        return ""

    # Busca case-insensitive pela linha "## Nome: X"
    lines = raw.split("\n")
    name_lower = name.lower().strip()

    start_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        # Aceita "## nome: predador selva" ou "## predador selva"
        if stripped.startswith("## nome:") and name_lower in stripped:
            start_idx = i
            break
        elif stripped.startswith("##") and name_lower in stripped:
            start_idx = i
            break

    if start_idx == -1:
        # Busca parcial
        for i, line in enumerate(lines):
            if name_lower in line.lower() and line.strip().startswith("##"):
                start_idx = i
                break

    if start_idx == -1:
        return ""

    # Extrai até a próxima entrada "##" ou "---" de separação entre criaturas
    block_lines = []
    for j in range(start_idx, len(lines)):
        if j > start_idx and lines[j].strip().startswith("##"):
            break
        if j > start_idx and lines[j].strip() == "---" and j < start_idx + 3:
            continue  # separador logo após o início, faz parte da ficha
        block_lines.append(lines[j])

    return "\n".join(block_lines).strip()


def append_to_bestiary(new_entry: str) -> None:
    """Adiciona nova entrada ao final do bestiário."""
    path = PATHS["bestiary"]
    existing = _read(path, "# BESTIÁRIO & AMEAÇAS CONHECIDAS\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(existing.rstrip() + "\n\n---\n" + new_entry.strip() + "\n")


def append_to_campaign_log(entry: str) -> None:
    """Adiciona entrada ao campaign_log.md. Cria o arquivo com header se não existir."""
    path = PATHS["campaign_log"]
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# DIÁRIO DE FERRO — CHRONOS-7\n\n---\n\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + entry.strip() + "\n")


def append_to_story_bible(summary: str, turno: str = "?") -> None:
    """Faz append do resumo do turno na story_bible."""
    path = PATHS["story_bible"]
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n**{turno}**\n{summary.strip()}\n")


def update_npc_dossier(nome: str, bloco_markdown: str) -> None:
    """Substitui ou adiciona entrada de NPC no dossier."""
    import re
    path = PATHS["npc_dossier"]
    existing = _read(path, "# DOSSIÊ DE PESSOAS\n\n---\n\n")
    # Tenta substituir entrada existente
    pattern = rf'(\*\*{re.escape(nome)}\*\*.*?)(?=\n---\n\*\*|\Z)'
    if re.search(pattern, existing, re.DOTALL):
        existing = re.sub(pattern, bloco_markdown.strip(), existing, flags=re.DOTALL)
    else:
        existing = existing.rstrip() + "\n\n---\n" + bloco_markdown.strip() + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(existing)


def update_active_quests(full_content: str) -> None:
    """Sobrescreve o arquivo de missões ativas."""
    path = PATHS["active_quests"]
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_content)