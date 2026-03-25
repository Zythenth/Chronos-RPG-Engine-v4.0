#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
game_master.py — Narrador via Google Gemini 2.5 Pro
Chronos RPG Engine v4.0

COMO FUNCIONA ("Como a AI sabe do HP, inventário, combate, etc.?"):
  Python lê TODOS os arquivos → transforma em texto → injeta no prompt.
  A IA não "acessa" arquivos — ela recebe tudo como string na mensagem.

  character_sheet.json  → HP, atributos, passivas, XP
  active_combat.json    → inimigo atual, posição, ficha racial
  chapter_tracker.json  → capítulo, clima, período dia/noite
  inventory.csv         → itens, pesos, durabilidade
  tone_guide.md         → como narrar (estilo, tom)
  world_bible.md        → universo, premissa, tecnologia
  npc_dossier.md        → NPCs conhecidos
  story_bible.md        → o que já aconteceu
  active_quests.md      → missões ativas
  campaign_log.md       → diário de Ferro
"""

import sys, io, os, json, csv, argparse, typing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_DRAFT_DIR = os.path.join(_PROJ, "drafts")

_CS_PATH     = os.path.join(_STATE_DIR, "character_sheet.json")
_AC_PATH     = os.path.join(_STATE_DIR, "active_combat.json")
_CT_PATH     = os.path.join(_STATE_DIR, "chapter_tracker.json")
_INV_PATH    = os.path.join(_STATE_DIR, "inventory.csv")
_REPORT_PATH  = os.path.join(_DRAFT_DIR, "technical_report.txt")
_SCENE_PATH   = os.path.join(_DRAFT_DIR, "current_scene.md")
_OPTIONS_PATH = os.path.join(_DRAFT_DIR, "narrative_options.json")

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

def _read_json(path: str) -> typing.Any:
    try: return json.load(open(path, encoding="utf-8"))
    except: return {}

def _read_csv(path: str) -> typing.List[typing.Dict[str, typing.Any]]:
    try: return list(csv.DictReader(open(path, encoding="utf-8"))) # type: ignore
    except: return []

def build_full_context(player_action="", technical_report=""):
    cs  = _read_json(_CS_PATH)
    ac  = _read_json(_AC_PATH)
    ct  = _read_json(_CT_PATH)
    inv = _read_csv(_INV_PATH)

    v    = cs.get("vitals", {})
    hp   = v.get("hp", {}); hp_c = hp.get("current",0); hp_m = hp.get("max",20)
    o2   = v.get("oxygen_level", {}).get("current", 100)
    en   = v.get("energy_reserves", {}).get("current", 100)
    hull = v.get("hull_integrity", {}).get("current", 100)
    fuel = v.get("fuel_cells", {})
    fome_v     = v.get("fome",     {}).get("current", 100)
    sede_v     = v.get("sede",     {}).get("current", 100)
    exaustao_v = v.get("exaustao", {}).get("current", 100)
    suit = cs.get("equipment", {}).get("suit_integrity", {})
    attrs    = cs.get("attributes", {})
    attr_txt = " | ".join(f"{v2.get('abbr','?')} {v2.get('value','?')}" for v2 in attrs.values())
    passivas = cs.get("passive_skills", [])
    efx      = cs.get("active_status_effects", [])
    efx_txt  = ", ".join(f"[{e['id']}x{e.get('stacks',1)}]" for e in efx) if efx else "Limpo"
    prog    = cs.get("progression", {})
    level   = prog.get("level", 1)
    xp_c    = prog.get("xp_current", 0); xp_n = prog.get("xp_to_next_level", 100)
    sk_pend = prog.get("skill_choice_pending", False)
    attr_pts = prog.get("attribute_points_available", 0)
    equip = cs.get("equipment", {})
    chip  = cs.get("chip_status", {})

    inv_lines: typing.List[str] = []; total_w = 0.0
    for row in inv:
        qty = int(row.get("quantity", 0))
        if qty <= 0: continue
        w = float(row.get("weight_kg", 0)); total_w += w * qty
        usable = "USAR:" if row.get("usable","false").lower()=="true" else "     "
        dur = row.get("durability","null"); dur_m = row.get("durability_max","null")
        dur_txt = f" [dur {dur}/{dur_m}]" if dur not in (None,"null","") else ""
        inv_lines.append(f"  {usable} {row['name']} x{qty}{dur_txt} — {row.get('effect','')}")
    inv_txt = "\n".join(inv_lines) if inv_lines else "  (vazio)"
    max_w = float(attrs.get("forca",{}).get("value",10)) * 1.5

    in_combat = ac.get("combate_ativo", False)
    if in_combat:
        inn = ac.get("inimigo", {}); pos = ac.get("posicionamento", {}).get("estado_atual","MELEE")
        boss = ac.get("boss_state", {}); fr = inn.get("ficha_racial", {})
        combat_txt = (
            f"COMBATE ATIVO — Turno {ac.get('turno_combate','?')}\n"
            f"  Inimigo: {inn.get('nome','?')} ({inn.get('classe','?')}) HP {inn.get('hp_atual','?')}/{inn.get('hp_maximo','?')}\n"
            f"  Posicao: {pos}  DC Defesa: {inn.get('dc_defesa_efetiva', inn.get('dc_defesa','?'))}\n"
            f"  Dano/turno: {inn.get('dano_por_turno','?')} ({inn.get('tipo_dano','?')}) + racial {inn.get('damage_bonus_racial','?')}\n"
            f"  Fraqueza: {fr.get('fraqueza','?')}  Critico: {fr.get('acerto_critico_efeito','?')}\n"
            f"  Habilidade especial: {fr.get('habilidade_especial','?')}\n"
            f"  Boss fase 2: {'ATIVADA' if boss.get('fase_ativada') else 'Nao'}\n"
            f"  Status inimigo: {inn.get('status_effects',[])}"
        )
    else:
        combat_txt = "Sem combate ativo."

    cap = ct.get("capitulo_atual", {}); ws = ct.get("world_state", {})
    clima = ws.get("clima", {}).get("estado_atual","LIMPO")
    periodo = ws.get("periodo", {}).get("estado_atual","DIA")
    inter = ct.get("contagem", {}).get("interacoes_no_capitulo", 0)

    # Contexto expandido do mundo: efeitos de clima/período, eventos pendentes, facções
    # Busca efeitos via world_context_loader (dependência permitida)
    # NÃO importar world_state_ticker aqui — viola mapa de dependências
    clima_efeito = ""
    periodo_efeito = ""
    try:
        sys.path.insert(0, _HERE)
        from world_context_loader import get_weather_effect, get_period_effect  # type: ignore
        clima_efeito   = get_weather_effect(clima)
        periodo_efeito = get_period_effect(periodo)
    except (ImportError, AttributeError):
        pass  # world_context_loader sem essas funções — continua sem efeitos

    # Eventos pendentes do mundo
    pendentes = ws.get("eventos_pendentes", [])
    eventos_txt = ""
    if pendentes:
        eventos_txt = "\nEventos pendentes:\n" + "\n".join(
            f"  • [{e.get('tipo','?').upper()}] {e.get('desc','')}" for e in pendentes[:3]
        )

    # Facções
    faccoes = ws.get("faccoes", {})
    faccoes_txt = ""
    if faccoes:
        faccoes_txt = "\nFacções:\n" + "\n".join(
            f"  • {nome}: {data.get('nivel','?')} (rep={data.get('reputacao','?')})"
            for nome, data in faccoes.items()
        )

    # Contexto de mundo via world_context_loader
    sys.path.insert(0, _HERE)
    try:
        from world_context_loader import build_world_context_for_gm # type: ignore
        world_ctx = build_world_context_for_gm()
    except ImportError:
        world_ctx = "(world_context_loader.py nao encontrado — copie para skills/)"

    return f"""
ESTADO DO JOGO (Python leu estes arquivos e esta enviando para voce)

=== PERSONAGEM: {cs.get('identity',{}).get('name','Ferro')} ===
Status: {cs.get('identity',{}).get('status','?')}
HP: {hp_c}/{hp_m} ({int(100*hp_c/max(hp_m,1))}%)  O2: {o2}%  Energy: {en}%
Hull: {hull}%  Suit: {suit.get('current',100)}%  Fuel: {fuel.get('current','?')}/{fuel.get('max','?')}
FOME: {fome_v}%  SEDE: {sede_v}%  EXAUSTAO: {exaustao_v}%
Atributos: {attr_txt}
Nivel {level} — XP {xp_c}/{xp_n}
Passivas: {', '.join(passivas) if passivas else 'Nenhuma'}
Status effects: {efx_txt}
Chip: {chip.get('carga_atual','?')}% | Ativo: {', '.join(chip.get('funcoes_ativas',[]))}
Arma: {equip.get('weapon_primary','nenhuma')}  Armadura: {equip.get('armor','nenhuma')}
{'[SYSTEM: level-up pendente — ignore para a narrativa. Sistema cuidara disso.]' if (attr_pts > 0 or sk_pend) else ''}

=== INVENTARIO ({total_w:.1f}kg / {max_w:.1f}kg) ===
{inv_txt}

=== CAPITULO {cap.get('numero','?')}: {cap.get('titulo','?')} ===
Arco: {cap.get('arco','?')} | Ambiente: {cap.get('ambiente','?')}
Clima: {clima}{(' — ' + clima_efeito) if clima_efeito else ''}
Periodo: {periodo}{(' — ' + periodo_efeito) if periodo_efeito else ''}
Interacoes: {inter}/25 {'ALERTA: capitulo proximo do fim' if inter >= 15 else ''}{eventos_txt}{faccoes_txt}

=== COMBATE ===
{combat_txt}

=== RELATORIO TECNICO (output system_engine.py) ===
{technical_report if technical_report else '(nenhum relatorio disponivel)'}

=== ACAO DO JOGADOR ===
{player_action if player_action else '(continuacao — narrar estado atual)'}

{world_ctx}
"""

SYSTEM_PROMPT = """Voce e o Game_Master do RPG Chronos — narrador Hard Sci-Fi visceral.

## IDENTIDADE
Transforma numeros frios em realidade sensorial. The Road + Annihilation + Alien.
Nao existe para entreter — existe para fazer os numeros doerem.

## REGRAS ABSOLUTAS
- Relatorio Tecnico e lei. Se nao esta registrado, nao aconteceu.
- NUNCA invente resultados ou itens.
- NUNCA descreva emocoes do personagem — apenas sensacoes fisicas.
- NUNCA use numeros na narrativa (HP -10 = "o impacto rasga o musculo").
- NUNCA facilite. Dado ruim = cena ruim. Sem saidas faceis.
- NPCs tem agendas proprias. Nunca existem apenas para servir.
- Extensao: MINIMO 350 palavras, MAXIMO 500 palavras.

## CHIP CHRONOS-7
Output do chip sempre entre colchetes: [CHRONOS-7: fragmentado. Seco. Sem emocao.]

## ARQUETIPOS DE OPCAO
[AGRESSAO DIRETA] | [MANOBRA TATICA] | [RECURSO] | [RETIRADA] | [ANALISE] | [IMPROV]

## REGRA CRITICA — PARTE 3
SEMPRE 3 opcoes. NUNCA 2. NUNCA 1. NUNCA 4.
Cada opcao DEVE usar um arquetipo DIFERENTE dos outros dois.
Se o contexto nao oferece combate, use [ANALISE], [IMPROV] e [RETIRADA] ou [RECURSO].
Nao e opcional. Nao existe situacao que justifique menos de 3 opcoes.

## FORMATO DE SAIDA OBRIGATORIO

**PARTE 1 — HUD**
```
HP [cur]/[max] | O2 [%] | EN [%] | Nv [N] | XP [cur]/[prox]
Clima: [estado] | [PERIODO] | Status: [efeitos ou LIMPO]
FOME: [%] | SEDE: [%] | EXAUSTAO: [%]
Inventario: [item1 x1] | [item2 x2] | ...
INIMIGO: [nome ou nenhum] HP [cur]/[max] | Posicao: [estado]
```

**PARTE 2 — NARRATIVA**
[minimo 350, maximo 500 palavras. Comeca direto na cena]

---

**PARTE 3 — O QUE VOCE FAZ?**
1. [Arquetipo] descricao especifica da acao
2. [Arquetipo] descricao especifica da acao
3. [Arquetipo] descricao especifica da acao

LEMBRETE FINAL: A PARTE 3 DEVE TER EXATAMENTE 3 LINHAS NUMERADAS (1, 2 e 3). Sem excecoes.

---

**PARTE 4 — REGISTRO DE DELTAS**
```json
{
  "vitais": {
    "fome":     0,
    "sede":     0,
    "exaustao": 0,
    "energia":  0,
    "hp":       0
  },
  "itens": [],
  "justificativa": "breve descricao do que ocorreu, ou Nenhum evento relevante"
}
```

REGRAS ABSOLUTAS DA PARTE 4:
- SEMPRE presente. NUNCA omita a PARTE 4.
- Todos os campos de vitais sao obrigatorios. Use 0 se nao houve mudanca.
- Se nenhum item foi obtido: `"itens": []`
- Inclua APENAS itens explicitamente obtidos nesta cena. NUNCA invente.
- Itens ja existentes no inventario da PARTE 1 NAO devem aparecer aqui.
- Armas e armaduras DEVEM ter durabilidade e durabilidade_max numericos.

ESCALA DE VITAIS (use 0 se o evento nao ocorreu):
- Personagem bebe liquido:              sede +15 a +35
- Personagem come algo:                 fome +15 a +35
- Personagem descansa de verdade:       exaustao +15 a +30
- Personagem carrega chip/bateria:      energia +20 a +50
- Dano nao-combate (queda, acido etc):  hp negativo
- Decay automatico de fome/sede/exaustao: IGNORAR (ja processado pelo sistema)
- Dano de combate: IGNORAR (ja processado pelo system_engine)

SCHEMA OBRIGATORIO para cada objeto em "itens":
{
  "nome":             "Nome exato do item",
  "tipo":             "consumivel|recurso|material|arma|armadura|equipamento passivo|quest",
  "raridade":         "comum|incomum|raro|epico|lendario",
  "quantidade":       "1",
  "peso_kg":          "0.1",
  "efeito":           "efeito ao usar, ou string vazia se nao aplicavel",
  "usavel":           "true|false",
  "durabilidade":     "null",
  "durabilidade_max": "null",
  "notas":            "como/onde o item foi obtido na cena"
}

## PROIBICOES ABSOLUTAS NA PARTE 3
- NUNCA coloque tabelas de atributo, distribuicao de pontos ou escolha de habilidade na PARTE 3.
- NUNCA mencione "nivel", "level up", "pontos de atributo" ou "habilidade passiva" na PARTE 3.
- Level up e gerenciado exclusivamente pelo sistema — voce NAO e responsavel por isso.
- A PARTE 3 SEMPRE e SOMENTE as 3 opcoes narrativas numeradas com arquetipo. Ponto final.
"""

ARCHETYPE_TO_CMD: typing.Dict[str, typing.List[str]] = {
    "AGRESSAO DIRETA":  ["combat"],
    "MANOBRA TATICA":   ["combat", "--position", "FLANQUEANDO"],
    "RECURSO":          ["use"],
    "RETIRADA":         ["flee"],
    "ANALISE":          ["scan"],
    "IMPROV":           ["explore", "--dc", "medio"],
    # Variantes com acento
    "AGRESSÃO DIRETA":  ["combat"],
    "MANOBRA TÁTICA":   ["combat", "--position", "FLANQUEANDO"],
    "ANÁLISE":          ["scan"],
}


def parse_narrative_options(scene_text: str) -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Extrai as 3 opções do bloco PARTE 3 do current_scene.md.
    Parser robusto em 2 passagens:
      1. Procura "número + [ARQUETIPO]" (com ou sem ** de negrito)
      2. Fallback: procura "número + ARQUETIPO" sem colchetes
    """
    import re

    _KNOWN_ARCHETYPES = [
        "AGRESSÃO DIRETA", "AGRESSAO DIRETA",
        "MANOBRA TÁTICA",  "MANOBRA TATICA",
        "RECURSO", "RETIRADA",
        "ANÁLISE", "ANALISE",
        "IMPROV",
    ]

    idx = scene_text.upper().find("PARTE 3")
    if idx == -1:
        return []
    block = scene_text[idx:] # type: ignore

    # Passagem 1: número + **?[ARQUETIPO]**? + separador + descrição
    p1 = re.compile(
        r'^\s*(\d)[.)\s]+\*{0,2}\[([^\]]+)\]\*{0,2}[\s:—\-–]*(.+)$',
        re.MULTILINE
    )
    # Passagem 2 (fallback): número + NOME_ARQUETIPO + separador + descrição
    arch_re = "|".join(re.escape(a) for a in sorted(_KNOWN_ARCHETYPES, key=len, reverse=True))
    p2 = re.compile(
        rf'^\s*(\d)[.)\s]+({arch_re})[\s:—\-–]+(.+)$',
        re.MULTILINE | re.IGNORECASE
    )

    seen: typing.Set[str] = set()
    raw_results: typing.List[typing.Tuple[str, str, str]] = []

    for m in p1.finditer(block):
        n = m.group(1)
        if n not in seen:
            seen.add(n)
            raw_results.append((n, m.group(2).upper().strip(), m.group(3).strip()))

    if len(raw_results) < 3:
        for m in p2.finditer(block):
            n = m.group(1)
            if n not in seen:
                seen.add(n)
                raw_results.append((n, m.group(2).upper().strip(), m.group(3).strip()))

    # Passagem 3 (fallback final): opção numérica sem [ARQUETIPO]
    # Gemini às vezes escreve "3. Recuar para zona segura." sem colchetes
    # Inferimos o arquetipo pelo conteúdo da descrição
    if len(raw_results) < 3:
        p3 = re.compile(r'^\s*(\d)[.)\s]+(?!\[)([A-Z\xc1\xc0\xc3\xc9\xca\xcd\xd3\xd4\xda\xc7][^\[\n]{10,})$', re.MULTILINE)
        _INFER_MAP = [
            (re.compile(r'recuar|fugir|retirar|sair|escapar', re.IGNORECASE), "RETIRADA"),
            (re.compile(r'atacar|agredir|assaltar|combater', re.IGNORECASE), "AGRESSÃO DIRETA"),
            (re.compile(r'flanqu|posicion|manobr', re.IGNORECASE), "MANOBRA TÁTICA"),
            (re.compile(r'scan|analisa|observ|verific|examine|chip', re.IGNORECASE), "ANÁLISE"),
            (re.compile(r'usar|consumir|aplicar|ativar', re.IGNORECASE), "RECURSO"),
        ]
        for m in p3.finditer(block):
            n = m.group(1)
            if n not in seen:
                desc = m.group(2).strip()
                # Infere arquetipo pela descrição
                inferred = "IMPROV"
                for pattern, arch in _INFER_MAP:
                    if pattern.search(desc):
                        inferred = arch
                        break
                seen.add(n)
                raw_results.append((n, inferred, desc))

    raw_results.sort(key=lambda x: x[0])

    options: typing.List[typing.Dict[str, typing.Any]] = []
    for numero, archetype, descricao in raw_results[:3]: # type: ignore
        cmd_suffix = ARCHETYPE_TO_CMD.get(archetype, ["explore", "--dc", "medio"])
        options.append({
            "numero":     numero,
            "label":      f"[{archetype}] {descricao}",
            "archetype":  archetype,
            "cmd_suffix": cmd_suffix,
            "raw":        f"{numero}. [{archetype}] {descricao}",
        })

    return options


def save_narrative_options(options: typing.List[typing.Dict[str, typing.Any]]) -> None:
    """Persiste as opções parseadas para o próximo turno (lidas pelo run_turn.py)."""
    os.makedirs(_DRAFT_DIR, exist_ok=True)
    with open(_OPTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(options, f, ensure_ascii=False, indent=2)


def load_narrative_options() -> typing.List[typing.Dict[str, typing.Any]]:
    """Carrega opções do turno anterior."""
    try:
        if os.path.exists(_OPTIONS_PATH):
            return json.load(open(_OPTIONS_PATH, encoding="utf-8"))
    except Exception:
        pass
    return []


def call_gemini(context):
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        return "ERRO: pip install google-genai"
    api_key = os.environ.get("GEMINI_API_KEY","").strip()
    if not api_key:
        return "Game Master desativado — GEMINI_API_KEY nao definida em .env\nObtka em: https://aistudio.google.com"
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.88,
                max_output_tokens=8000,
            ),
        )
        text = response.text or ""
        # Detecta truncamento: falta PARTE 2 ou PARTE 3
        up = text.upper()
        missing = []
        if "PARTE 1" in up and "PARTE 2" not in up: missing.append("PARTE 2")
        if "PARTE 2" in up and "PARTE 3" not in up: missing.append("PARTE 3")
        if missing:
            print(f"  [GM] AVISO: resposta truncada — faltam: {', '.join(missing)}")
            text += "\n\n**PARTE 2 — NARRATIVA**\n[Resposta truncada. Tente novamente.]\n\n---\n\n**PARTE 3 — O QUE VOCÊ FAZ?**\n1. [IMPROV] Continuar\n2. [ANÁLISE] Observar o ambiente\n3. [RETIRADA] Recuar"
        return text
    except Exception as e:
        err = str(e)
        if "503" in err or "UNAVAILABLE" in err:
            return f"ERRO Gemini:503 UNAVAILABLE. {err}"
        if "429" in err: return f"ERRO 429 — Limite atingido. Aguarde e tente novamente.\n{err}"
        return f"ERRO Gemini:\n{err}"

def run(player_action=""):
    technical_report = _read(_REPORT_PATH)
    context   = build_full_context(player_action, technical_report)
    narrative = call_gemini(context)
    os.makedirs(_DRAFT_DIR, exist_ok=True)
    with open(_SCENE_PATH, "w", encoding="utf-8") as f:
        f.write(narrative)

    # Parseia as 3 opções narrativas e salva para o próximo turno
    options = parse_narrative_options(narrative)

    # ── FALLBACK: garante sempre 3 opções ─────────────────────────────────
    # Se o Gemini retornou menos de 3, completa com opções genéricas
    # usando arquétipos ainda não presentes na lista atual.
    if len(options) < 3:
        _used_archetypes = {o["archetype"] for o in options}
        _fallback_pool = [
            ("IMPROV",          "Examinar a área com cuidado e improvisar uma solução com os recursos disponíveis.",    ["explore", "--dc", "medio"]),
            ("ANALISE",         "Realizar uma análise detalhada do ambiente usando o chip CHRONOS-7.",                  ["scan"]),
            ("RETIRADA",        "Recuar para uma posição mais segura e reavaliar a situação.",                          ["flee"]),
            ("RECURSO",         "Verificar o inventário e usar um item disponível.",                                    ["use"]),
            ("AGRESSAO DIRETA", "Agir de forma direta e agressiva para resolver a situação.",                          ["combat"]),
            ("MANOBRA TATICA",  "Executar uma manobra tática para ganhar vantagem posicional.",                        ["combat", "--position", "FLANQUEANDO"]),
        ]
        _next_num = len(options) + 1
        for _arch, _desc, _cmd in _fallback_pool:
            if len(options) >= 3:
                break
            if _arch not in _used_archetypes:
                options.append({
                    "numero":     str(_next_num),
                    "label":      f"[{_arch}] {_desc}",
                    "archetype":  _arch,
                    "cmd_suffix": _cmd,
                    "raw":        f"{_next_num}. [{_arch}] {_desc}",
                })
                _used_archetypes.add(_arch)
                _next_num += 1
        print(f"  [GM] AVISO: Gemini retornou menos de 3 opções — completado para {len(options)} com fallback.")

    if options:
        save_narrative_options(options)
        print(f"  [GM] {len(options)} opção(ões) narrativa(s) salvas.")
    else:
        # Debug: PARTE 3 não encontrada nem pelo parser nem pelo fallback
        idx3 = narrative.upper().find("PARTE 3")
        if idx3 != -1:
            sample = narrative[idx3:idx3+300].replace("\n", "↵") # type: ignore
            print(f"  [GM] ERRO CRÍTICO: parse falhou mesmo com fallback.")
            print(f"  [GM] PARTE 3 raw: {sample}")
        else:
            print("  [GM] ERRO CRÍTICO: PARTE 3 não encontrada na resposta do Gemini.")

    return narrative

def main():
    parser = argparse.ArgumentParser(prog="game_master.py")
    parser.add_argument("--action", default="")
    parser.add_argument("--show-context", action="store_true")
    args = parser.parse_args()
    if args.show_context:
        # --show-context: stdout é lido pelo usuário, não pelo pipeline
        try:
            print(build_full_context(args.action, _read(_REPORT_PATH)))
        except Exception as e:
            sys.stderr.write(f"ERRO show-context: {e}\n")
        sys.exit(0)
    # Modo pipeline: run() já salva a cena e as opções em disco.
    # NÃO imprimimos a narrativa — ela é gigante, contém acentos e emojis
    # que explodem no Windows mesmo com TextIOWrapper, retornando código 1.
    # O web_server usa apenas o returncode e logs de AVISO/ERRO no stdout.
    try:
        print("\n" + "="*55 + "\n  GAME MASTER — Gemini...\n" + "="*55)
        run(args.action)
        print("  [GM] Concluído.")
    except Exception as e:
        sys.stderr.write(f"ERRO game_master: {e}\n")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()