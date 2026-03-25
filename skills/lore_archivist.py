#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lore_archivist.py — Guardiao da Memoria via Gemini 2.5 Flash
Chronos RPG Engine v4.0

COMO SALVA NOVOS NPCs/ITENS:
  Gemini analisa a cena → retorna JSON → Python escreve nos arquivos reais.

  Fluxo de salvamento:
  story_bible.md   → append do resumo do turno
  active_quests.md → reescrita completa se quest mudou
  npc_dossier.md   → append/update de NPCs novos ou alterados
  bestiary.md      → append de criaturas novas (via expansion_manager)
  campaign_log.md  → append de entrada do diario

  Para ITENS novos → delega ao expansion_manager.py (PROTOCOLO DE EXPANSAO)
"""

import sys, io, os, json, re, argparse
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

_HERE    = os.path.dirname(os.path.abspath(__file__))
_PROJ    = os.path.join(_HERE, "..")
_DRAFT_DIR = os.path.join(_PROJ, "drafts")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_CTX_DIR   = os.path.join(_PROJ, "world_context")

_SCENE_PATH  = os.path.join(_DRAFT_DIR, "current_scene.md")
_REPORT_PATH = os.path.join(_DRAFT_DIR, "technical_report.txt")
_LOG_PATH    = os.path.join(_DRAFT_DIR, "lore_report.txt")

def _load_env():
    path = os.path.join(_PROJ, ".env")
    if not os.path.exists(path): return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ: os.environ[k] = v
_load_env()

def _read(path, default=""):
    if not os.path.exists(path): return default
    return open(path, encoding="utf-8").read()

def build_archivist_context():
    sys.path.insert(0, _HERE)
    try:
        from world_context_loader import build_world_context_for_archivist # type: ignore
        world_ctx = build_world_context_for_archivist()
    except ImportError:
        world_ctx = "(world_context_loader.py nao encontrado)"

    scene  = _read(_SCENE_PATH,  "(Nenhuma cena gerada ainda)")
    report = _read(_REPORT_PATH, "(Nenhum relatorio tecnico)")

    return f"""
CENA ATUAL (output do Game_Master):
{scene}

RELATORIO TECNICO (output do System_Engine):
{report}

{world_ctx}
"""

try:
    from pydantic import BaseModel, Field # type: ignore
    from typing import Optional
except ImportError:
    print("ERRO: pip install pydantic")
    sys.exit(1)

class EntidadeNova(BaseModel):
    nome: str
    tipo: str
    descricao: str

class NpcStatus(BaseModel):
    nome: str
    novo_status: str
    motivo: str

class QuestStatus(BaseModel):
    nome: str
    novo_status: str
    detalhe: str

class BestiaryObs(BaseModel):
    criatura: str
    observacao: str

class MudancasEstado(BaseModel):
    npcs: list[NpcStatus] = Field(default_factory=list)
    quests: list[QuestStatus] = Field(default_factory=list)
    bestiary: list[BestiaryObs] = Field(default_factory=list)

class Relatorio(BaseModel):
    entidades_novas: list[EntidadeNova] = Field(default_factory=list)
    mudancas_de_estado: MudancasEstado = Field(default_factory=MudancasEstado)
    anomalias: list[str] = Field(default_factory=list)
    sinalizacoes: list[str] = Field(default_factory=list)

class NpcUpdate(BaseModel):
    nome: str
    bloco_markdown: str

class NovaCriatura(BaseModel):
    nome: str
    bloco_markdown: str

class Atualizacoes(BaseModel):
    story_bible_append: Optional[str] = ""
    campaign_log_entry: Optional[str] = ""
    quests_full: Optional[str] = ""
    npc_updates: list[NpcUpdate] = Field(default_factory=list)
    novas_criaturas_bestiary: list[NovaCriatura] = Field(default_factory=list)

class LoreArchivistResponse(BaseModel):
    relatorio: Relatorio
    atualizacoes: Atualizacoes

SYSTEM_PROMPT = """Voce e o Lore_Archivist do RPG Chronos.

## MISSAO
Analise a cena e extraia fatos para arquivamento permanente.

## REGRAS ABSOLUTAS
- Registre APENAS fatos explicitamente narrados. Nunca especule.
- Nunca contradiga registros anteriores sem marcar ANOMALIA.
- Maximo 2000 caracteres no resumo da story_bible.
- story_bible_append e campaign_log_entry sao SEMPRE preenchidos.

## RESPONDA SOMENTE EM JSON VALIDO (sem texto antes/depois, sem ```json```):

{
  "relatorio": {
    "entidades_novas": [
      {"nome": "str", "tipo": "NPC|Criatura|Local|Item|Faccao", "descricao": "str"}
    ],
    "mudancas_de_estado": {
      "npcs": [{"nome": "str", "novo_status": "Morto|Neutro|Hostil|Aliado|Desaparecido", "motivo": "str"}],
      "quests": [{"nome": "str", "novo_status": "Iniciada|Atualizada|Completada|Falhada", "detalhe": "str"}],
      "bestiary": [{"criatura": "str", "observacao": "str"}]
    },
    "anomalias": ["str"],
    "sinalizacoes": ["str"]
  },
  "atualizacoes": {
    "story_bible_append": "str — resumo max 2000 chars. Inclui: mudancas status, novos itens, mortes, locais, resultados criticos. SEM coreografia detalhada.",
    "campaign_log_entry": "str — entrada curta no diario de Ferro. Formato EXATO (Python adiciona o numero automaticamente):\n### EVENTO: TITULO_CURTO_UNICO\n**Capitulo:** N — titulo do capitulo\n**Resultado:** SUCESSO|FALHA|CRITICO|NEUTRO\n**Resumo:** 1-2 linhas factuais do que aconteceu\n**Deltas:** HP -X | XP +Y | Item adicionado/removido (ou Nenhum)\nMAX 300 chars total. Titulo deve ser UNICO e descritivo (nao repetir titulos ja existentes no historico).",
    "quests_full": "str — conteudo COMPLETO do active_quests.md. Se nenhuma mudanca: copie o original exato.",
    "npc_updates": [
      {"nome": "str", "bloco_markdown": "str — entrada completa em Markdown para npc_dossier.md"}
    ],
    "novas_criaturas_bestiary": [
      {"nome": "str", "bloco_markdown": "str — ficha completa no formato do bestiary.md"}
    ]
  }
}

IMPORTANTE:
- quests_full e story_bible_append sao SEMPRE preenchidos mesmo sem mudancas.
- campaign_log_entry e SEMPRE preenchido com os fatos deste turno.
- O titulo do EVENTO deve ser unico — verifique o DIARIO RECENTE no contexto para nao repetir titulos.
- Nao inclua numero sequencial no titulo — o sistema adiciona automaticamente.
- Deltas OBRIGATORIOS: liste TODOS os recursos alterados (HP, XP, itens, energia). Se nenhum, escreva "Nenhum"."""

def _normalize_data(raw_data: dict) -> dict:
    """Garante estrutura mínima válida no dict retornado pelo Gemini."""
    if "atualizacoes" not in raw_data:
        raw_data["atualizacoes"] = {}
    at = raw_data["atualizacoes"]
    for campo in ("story_bible_append", "campaign_log_entry", "quests_full"):
        if campo not in at or at[campo] is None:
            at[campo] = ""
    for lista in ("npc_updates", "novas_criaturas_bestiary"):
        if lista not in at or at[lista] is None:
            at[lista] = []
    if "relatorio" not in raw_data:
        raw_data["relatorio"] = {}
    rel = raw_data["relatorio"]
    for campo in ("entidades_novas", "anomalias", "sinalizacoes"):
        if campo not in rel or rel[campo] is None:
            rel[campo] = []
    if "mudancas_de_estado" not in rel or rel["mudancas_de_estado"] is None:
        rel["mudancas_de_estado"] = {"npcs": [], "quests": [], "bestiary": []}
    return raw_data


def call_gemini(context):
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        print("ERRO: pip install google-genai"); return {}
    api_key = os.environ.get("GEMINI_API_KEY","").strip()
    if not api_key:
        print("ERRO: GEMINI_API_KEY nao definida"); return {}
    client = genai.Client(api_key=api_key)

    last_text = ""
    response = None

    for attempt in range(3):
        try:
            temp = 0.2
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=context,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=temp,
                    max_output_tokens=2500,
                    response_mime_type="application/json",
                    # SEM response_schema — evita JSON corrompido/truncado pelo Gemini
                ),
            )
            raw = (response.text or "").strip()
            # Remove markdown fences se existirem
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"```$", "", raw).strip()
            data = json.loads(raw)
            return _normalize_data(data)
        except Exception as e:
            err_str = str(e)
            try: last_text = getattr(response, "text", "") or ""
            except: last_text = ""
            preview = last_text[:400].replace("\n", " ") if last_text else err_str  # type: ignore
            # 503 UNAVAILABLE: não adianta tentar de novo — Gemini sobrecarregado
            if "503" in err_str or "UNAVAILABLE" in err_str:
                print(f"ERRO Gemini:503 UNAVAILABLE. {err_str}")
                print("  Arquivamento cancelado — turno já foi revertido pelo web_server.")
                return {}
            print(f"Tentativa {attempt+1} falhou: {e}")
            print(f"  Preview: {preview}")

    print("TODAS AS TENTATIVAS FALHARAM.")
    os.makedirs(_DRAFT_DIR, exist_ok=True)
    fail_path = os.path.join(_DRAFT_DIR, "lore_archivist_raw_fail.txt")
    with open(fail_path, "w", encoding="utf-8") as f:
        f.write(last_text)
    print(f"  Raw salvo em: {fail_path}")
    return {}

def apply_updates(data, dry_run=False):
    sys.path.insert(0, _HERE)
    from world_context_loader import ( # type: ignore
        append_to_story_bible, append_to_campaign_log,
        update_npc_dossier, update_active_quests, append_to_bestiary
    )

    updates  = data.get("atualizacoes", {})
    relatorio = data.get("relatorio", {})
    os.makedirs(_DRAFT_DIR, exist_ok=True)

    # Relatorio legivel
    lines = ["# RELATORIO LORE_ARCHIVIST"]
    entidades = relatorio.get("entidades_novas", [])
    lines.append(f"\nEntidades novas: {len(entidades) if entidades else 'NENHUMA'}")
    for e in entidades:
        lines.append(f"  + {e['nome']} ({e['tipo']}): {e['descricao']}")
    for npc in relatorio.get("mudancas_de_estado",{}).get("npcs",[]):
        lines.append(f"  NPC: {npc['nome']} -> {npc['novo_status']}: {npc['motivo']}")
    for q in relatorio.get("mudancas_de_estado",{}).get("quests",[]):
        lines.append(f"  Quest: [{q['novo_status']}] {q['nome']}: {q['detalhe']}")
    for a in relatorio.get("anomalias",[]):
        lines.append(f"  ANOMALIA: {a}")
    report_txt = "\n".join(lines)
    print(report_txt)

    # Turno atual
    cs_path = os.path.join(_STATE_DIR, "character_sheet.json")
    turno = "?"
    try:
        cs = json.load(open(cs_path, encoding="utf-8"))
        turno = cs.get("meta",{}).get("last_updated","?")
    except: pass

    # --- SALVAMENTO NOS ARQUIVOS REAIS ---
    # 1. story_bible.md (append)
    bible_app = (updates.get("story_bible_append") or "").strip()
    if bible_app:
        label = "story_bible.md" + (" [DRY RUN]" if dry_run else "")
        print(f"  -> {label}")
        if not dry_run:
            append_to_story_bible(bible_app, turno)

    # 2. campaign_log.md (append)
    log_entry = (updates.get("campaign_log_entry") or "").strip()
    if log_entry:
        label = "campaign_log.md" + (" [DRY RUN]" if dry_run else "")
        print(f"  -> {label}")
        if not dry_run:
            append_to_campaign_log(log_entry)

    # 3. active_quests.md (sobrescreve)
    quests_full = (updates.get("quests_full") or "").strip()
    if quests_full:
        label = "active_quests.md" + (" [DRY RUN]" if dry_run else "")
        print(f"  -> {label}")
        if not dry_run:
            update_active_quests(quests_full)

    # 4. npc_dossier.md (update/append por NPC — com detecção de duplicatas)
    _npc_path = os.path.join(_CTX_DIR, "npc_dossier.md")
    _npc_content = _read(_npc_path, "").lower() if os.path.exists(_npc_path) else ""
    for npc_u in updates.get("npc_updates",[]):
        nome  = npc_u.get("nome","?")
        bloco = npc_u.get("bloco_markdown","")
        if bloco:
            # Detecção de duplicata: verifica se o NPC já existe com o mesmo conteúdo
            _bloco_check = bloco.strip().lower()[:100]
            if _bloco_check and _bloco_check in _npc_content:
                print(f"  SKIP npc_dossier.md [{nome}] — conteúdo duplicado detectado")
                continue
            label = f"npc_dossier.md [{nome}]" + (" [DRY RUN]" if dry_run else "")
            print(f"  -> {label}")
            if not dry_run:
                update_npc_dossier(nome, bloco)

    # 5. bestiary.md — novas criaturas (append, com detecção de duplicatas)
    _bst_path = os.path.join(_CTX_DIR, "bestiary.md")
    _bst_content = _read(_bst_path, "").lower() if os.path.exists(_bst_path) else ""
    for c in updates.get("novas_criaturas_bestiary",[]):
        nome  = c.get("nome","?")
        bloco = c.get("bloco_markdown","")
        if bloco:
            # Detecção de duplicata: verifica se a criatura já existe no bestiary
            if nome.lower() in _bst_content:
                print(f"  SKIP bestiary.md [{nome}] — criatura já registrada")
                continue
            label = f"bestiary.md [{nome}]" + (" [DRY RUN]" if dry_run else "")
            print(f"  -> {label}")
            if not dry_run:
                append_to_bestiary(bloco)

    # Salva relatorio
    if not dry_run:
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(report_txt)

def run(dry_run=False):
    print("\n" + "="*55 + "\n  LORE ARCHIVIST — Arquivando via Gemini...\n" + "="*55)
    scene = _read(_SCENE_PATH)
    if not scene or "Nenhuma cena" in scene:
        print("  Nenhuma cena. Execute game_master.py primeiro."); return
    context = build_archivist_context()
    data = call_gemini(context)
    if not data:
        print("  Gemini nao retornou dados."); return
    print()
    apply_updates(data, dry_run=dry_run)
    print(f"\n  Arquivamento {'simulado' if dry_run else 'concluido'}.")

def main():
    parser = argparse.ArgumentParser(prog="lore_archivist.py")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)

if __name__ == "__main__":
    main()