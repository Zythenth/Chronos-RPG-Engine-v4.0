#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_server.py — Interface Web do Chronos RPG Engine v4.0
Substitui run_turn.py como ponto de entrada quando rodando no navegador.

USO:
  python web_server.py
  Abre http://localhost:5000 no navegador.
"""

import sys, io, os, json, csv, subprocess, threading, time
from typing import Any, Dict, List, cast
from flask import Flask, jsonify, request, send_from_directory  # type: ignore

# Import mechanics_engine for passive skills
import importlib.util as _ilu
def _load_me():
    spec = _ilu.spec_from_file_location("mechanics_engine",
               os.path.join(os.path.dirname(os.path.abspath(__file__)), "mechanics_engine.py"))
    if spec and spec.loader:
        m = _ilu.module_from_spec(spec)
        spec.loader.exec_module(m)  # type: ignore
        return m
    return None
_ME = _load_me()

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__, static_folder="web_ui", static_url_path="")

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_DRAFT_DIR = os.path.join(_PROJ, "drafts")
_CTX_DIR   = os.path.join(_PROJ, "world_context")

_CS_PATH     = os.path.join(_STATE_DIR, "character_sheet.json")
_AC_PATH     = os.path.join(_STATE_DIR, "active_combat.json")
_CT_PATH     = os.path.join(_STATE_DIR, "chapter_tracker.json")
_INV_PATH    = os.path.join(_STATE_DIR, "inventory.csv")
_SCENE_PATH  = os.path.join(_DRAFT_DIR, "current_scene.md")
_REPORT_PATH = os.path.join(_DRAFT_DIR, "technical_report.txt")
_OPTIONS_PATH = os.path.join(_DRAFT_DIR, "narrative_options.json")
_MAP_PATH    = os.path.join(_STATE_DIR, "world_map.json")
_QUEST_PATH  = os.path.join(_STATE_DIR, "active_quests.md")

_SE = [sys.executable, os.path.join(_HERE, "system_engine.py")]
_AR = [sys.executable, os.path.join(_HERE, "architect.py")]
_GM = [sys.executable, os.path.join(_HERE, "game_master.py")]
_LA  = [sys.executable, os.path.join(_HERE, "lore_archivist.py")]
_SP  = [sys.executable, os.path.join(_HERE, "scene_processor.py")]
_WST = [sys.executable, os.path.join(_HERE, "world_state_ticker.py"), "--quiet"]

# Estado global da sessão
pipeline_lock = threading.Lock()
pipeline_log: list[str] = []


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


def _read_json(path: str) -> dict:
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_csv(path: str) -> list:
    try:
        return list(csv.DictReader(open(path, encoding="utf-8")))
    except Exception:
        return []


def _read(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    return open(path, encoding="utf-8").read()


def run_script(cmd: list, label: str, capture: bool = True) -> str:
    pipeline_log.append(f"⚙ {label}...")
    try:
        # Captura em modo BINÁRIO para evitar UnicodeDecodeError no Windows
        # (o _readerthread do subprocess explode com encoding="utf-8" quando
        #  algum script filho emite bytes em cp1252 antes de reconfigurar o stdout).
        r = subprocess.run(cmd, capture_output=capture, text=False, timeout=180)
        raw_out = (r.stdout or b"") + (r.stderr or b"")
        # Decodifica com errors="replace": bytes inválidos viram "?" em vez de crash
        out = raw_out.decode("utf-8", errors="replace")
        stderr_str = (r.stderr or b"").decode("utf-8", errors="replace")
        if r.returncode != 0:
            pipeline_log.append(f"⚠ {label}: código {r.returncode}")
            if stderr_str:
                for line in stderr_str.strip().splitlines()[:5]:
                    if line.strip():
                        pipeline_log.append(f"  ↳ {line.strip()[:120]}")
        else:
            pipeline_log.append(f"✓ {label}")
            for line in out.splitlines():
                if any(w in line.upper() for w in ("AVISO", "WARN", "TRUNCAD", "ERRO")):
                    pipeline_log.append(f"  ↳ {line.strip()[:120]}")
        return out
    except subprocess.TimeoutExpired:
        pipeline_log.append(f"✗ {label}: timeout (>180s)")
        return "TIMEOUT"
    except Exception as e:
        pipeline_log.append(f"✗ {label}: {e}")
        return str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Leitura de estado
# ─────────────────────────────────────────────────────────────────────────────

def _parse_last_roll(report: str) -> dict:
    """Extrai o último d20 rolado do technical_report.txt.

    Retorna dict com:
      dado      — valor do dado usado (int)
      bonus     — bônus do atributo (int | None)
      attr_nome — nome do atributo, ex: "SOB" (str | None)
      total     — dado + bonus (int)
      dc        — DC do teste (int | None)
      all_rolls — lista completa de dados rolados ex: [14,7,3] (list | None)
      criterio  — "MELHOR" | "PIOR" | "ÚNICO" (str | None)

    Retorna {} quando não há rolagem (uso de item, status, erro de ação).
    """
    import re
    if not report:
        return {}

    # Padrão: d20 + bonus(ATRIBUTO) = total [vs DC N]
    _p_dc  = re.compile(
        r'(\d+)\s*\+\s*(\d+)\s*\(([^)]+)\)(?:[+\-]\d+)*(?:\s*\([^)]*\))?\s*=\s*(\d+)\s*vs\s*DC\s*(\d+)',
        re.IGNORECASE
    )
    _p_ndc = re.compile(
        r'(\d+)\s*\+\s*(\d+)\s*\(([^)]+)\)(?:[+\-]\d+)*(?:\s*\([^)]*\))?\s*=\s*(\d+)',
        re.IGNORECASE
    )

    def _try_match(text: str) -> dict:
        m = _p_dc.search(text)
        if m:
            try:
                return {"dado": int(m.group(1)), "bonus": int(m.group(2)),
                        "attr_nome": m.group(3).strip().upper(),
                        "total": int(m.group(4)), "dc": int(m.group(5))}
            except (ValueError, IndexError):
                pass
        m2 = _p_ndc.search(text)
        if m2:
            try:
                return {"dado": int(m2.group(1)), "bonus": int(m2.group(2)),
                        "attr_nome": m2.group(3).strip().upper(),
                        "total": int(m2.group(4)), "dc": None}
            except (ValueError, IndexError):
                pass
        return {}

    # Extrai D20_ROLLS da linha: D20_ROLLS : [14, 7, 3] → USADO: 14 (MELHOR)
    def _extract_all_rolls(report_text: str) -> tuple:
        """Retorna (all_rolls: list, criterio: str, usado: int) ou (None, None, None)."""
        m = re.search(
            r'D20_ROLLS\s*:.*?\[([\d,\s]+)\].*?USADO:\s*(\d+)\s*\(([^)]+)\)',
            report_text, re.IGNORECASE
        )
        if m:
            try:
                rolls = [int(x.strip()) for x in m.group(1).split(",") if x.strip().isdigit()]
                usado = int(m.group(2))
                criterio = m.group(3).strip().upper()
                return rolls, criterio, usado
            except (ValueError, IndexError):
                pass
        return None, None, None

    all_rolls, criterio, _ = _extract_all_rolls(report)

    # Camada 1: linha DADO_D20
    m_hud = re.search(r'DADO_D20\s*:(.+)', report, re.IGNORECASE)
    if m_hud:
        hud_line = m_hud.group(1).strip()
        if hud_line and hud_line != "—":
            result = _try_match(hud_line)
            if result:
                result["all_rolls"] = all_rolls
                result["criterio"]  = criterio
                return result

    # Camada 2: linha Total / Total ataque
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("total"):
            result = _try_match(stripped)
            if result:
                result["all_rolls"] = all_rolls
                result["criterio"]  = criterio
                return result

    # Camada 3: D20_ROLLS puro (sem bônus/total)
    m_d20 = re.search(r'D20_ROLLS\s*:.*?USADO:\s*(\d+)', report, re.IGNORECASE)
    if m_d20:
        try:
            dado = int(m_d20.group(1))
            if dado > 0:
                return {"dado": dado, "bonus": None, "attr_nome": None,
                        "total": dado, "dc": None,
                        "all_rolls": all_rolls, "criterio": criterio}
        except ValueError:
            pass

    return {}


def _parse_map(world_map: dict) -> list:
    """Extrai áreas descobertas do world_map.json para o frontend."""
    areas = []
    for area in world_map.get("areas", []):
        pois = []
        for poi in area.get("pontos_de_interesse", []):
            pois.append({
                "tipo":   poi.get("tipo", ""),
                "nome":   poi.get("nome", ""),
                "status": poi.get("status", ""),
            })
        areas.append({
            "id":      area.get("id", ""),
            "nome":    area.get("nome", ""),
            "status":  area.get("status", ""),
            "clima":   area.get("clima_no_momento", ""),
            "periodo": area.get("periodo_no_momento", ""),
            "notas":   area.get("notas", ""),
            "pois":    pois,
        })
    return areas


def _parse_quests(quest_md: str) -> list:
    """Extrai missões e objetivos do active_quests.md."""
    import re
    quests = []
    if not quest_md:
        return quests
    # Split by quest blocks (lines starting with **[)
    blocks = re.split(r'(?=\*\*\[)', quest_md)
    for block in blocks:
        if not block.strip():
            continue
        # Title line: **[PRINCIPAL] CAPÍTULO 1 — SALTO NO TEMPO**
        title_m = re.search(r'\*\*\[([^\]]+)\]\s*([^*]+)\*\*', block)
        if not title_m:
            continue
        tipo  = title_m.group(1).strip()
        nome  = title_m.group(2).strip()
        # Objectives: lines with [ ] or [x]
        objectives = []
        for obj_m in re.finditer(r'\[\s*([xX ]?)\s*\]\s*(.+)', block):
            done = obj_m.group(1).strip().lower() in ('x',)
            objectives.append({"texto": obj_m.group(2).strip(), "feito": done})
        if nome and objectives:
            quests.append({"tipo": tipo, "nome": nome, "objetivos": objectives})
    return quests


def _get_available_skills(nivel: int, atributos: dict, adquiridas: list) -> list:
    """Retorna lista de habilidades passivas elegíveis para o nível e atributos atuais."""
    if _ME is None:
        return []
    try:
        # Convert full attr keys to abbr format (forca -> FOR)
        abbr_map = {"forca":"FOR","destreza":"DES","inteligencia":"INT",
                    "sobrevivencia":"SOB","percepcao":"PER","carisma":"CAR"}
        attrs_abbr = {abbr_map.get(k, k.upper()[:3]): v for k, v in atributos.items()}
        skills = _ME.get_available_passive_skills(nivel, attrs_abbr, adquiridas)
        return [{
            "id":        s["id"],
            "nome":      s["nome"],
            "categoria": s["categoria"],
            # s["descricao"] causava KeyError silencioso (except retornava [])
            # porque PASSIVE_SKILLS não tem chave top-level "descricao" —
            # a descrição fica dentro de s["efeito"]["descricao"].
            "descricao": s.get("descricao", s.get("efeito", {}).get("descricao", "")),
            "efeito":    s["efeito"].get("descricao", ""),
            "requisito": {k: v for k, v in s.get("requisito", {}).items()},
        } for s in skills]
    except Exception as e:
        return []


def get_game_state() -> dict:
    cs  = _read_json(_CS_PATH)
    ac  = _read_json(_AC_PATH)
    ct  = _read_json(_CT_PATH)
    inv = _read_csv(_INV_PATH)

    v = cast(dict[str, Any], cs.get("vitals", {}))
    hp = cast(dict[str, Any], v.get("hp", {}))
    prog = cast(dict[str, Any], cs.get("progression", {}))
    attrs = cast(dict[str, Any], cs.get("attributes", {}))
    chip = cast(dict[str, Any], cs.get("chip_status", {}))
    equip = cast(dict[str, Any], cs.get("equipment", {}))
    efx = cast(list[Any], cs.get("active_status_effects", []))
    passivas = cast(list[Any], cs.get("passive_skills", []))
    ws = cast(dict[str, Any], ct.get("world_state", {}))
    cap = cast(dict[str, Any], ct.get("capitulo_atual", {}))
    contagem = cast(dict[str, Any], ct.get("contagem", {}))
    
    clima_dict = cast(dict[str, Any], ws.get("clima", {}))
    periodo_dict = cast(dict[str, Any], ws.get("periodo", {}))

    in_combat = bool(ac.get("combate_ativo", False))
    raw_inimigo = ac.get("inimigo", {})
    inimigo = cast(dict[str, Any], raw_inimigo) if in_combat else {}
    raw_pos = ac.get("posicionamento", {})
    pos_dict = cast(dict[str, Any], raw_pos)
    pos_estado = str(pos_dict.get("estado_atual", "MELEE")) if in_combat else ""

    inv_items = []
    for row in inv:
        if not isinstance(row, dict):
            continue
        qty = int(row.get("quantity", 0))
        # Itens com qty=0: só mostra se for arma/armadura/equipamento (podem ser reparados)
        # Consumíveis/Recursos com qty=0 são omitidos (gastos definitivamente)
        _item_type_low = str(row.get("type", "")).lower()
        _DURÁVEIS = {"arma", "armadura", "equipamento passivo"}
        if qty <= 0 and _item_type_low not in _DURÁVEIS:
            continue
        dur_raw: Any = row.get("durability", "")
        durm_raw: Any = row.get("durability_max", "")
        dur_raw_str = str(dur_raw)
        durm_raw_str = str(durm_raw)
        dur_val = None if dur_raw_str in ("", "null", "None") else dur_raw_str
        durm_val = None if durm_raw_str in ("", "null", "None") else durm_raw_str
        
        name_val = row.get("name", "?")
        type_val = row.get("type", "")
        rarity_val = row.get("rarity", "")
        usable_val = row.get("usable", "false")
        effect_val = row.get("effect", "")
        
        inv_items.append({
            "name":       str(name_val) if name_val is not None else "?",
            "qty":        qty,
            "type":       str(type_val) if type_val is not None else "",
            "rarity":     str(rarity_val) if rarity_val is not None else "",
            "usable":     str(usable_val).lower() == "true",
            "effect":     str(effect_val) if effect_val is not None else "",
            "durability": dur_val,
            "dur_max":    durm_val,
        })

    attr_list: list[dict[str, Any]] = []
    for key, raw_val in dict(attrs).items():
        val = cast(dict[str, Any], raw_val)
        val_abbr = str(val.get("abbr", ""))
        if not val_abbr:
            # Contornar pyre overload bug com type: ignore
            key_str = str(key)
            val_abbr = key_str[:3].upper()  # type: ignore
            
        attr_list.append({
            "key":   key,
            "abbr":  val_abbr,
            "value": int(val.get("value", 0)),
        })

    identity_dict = cast(dict[str, Any], cs.get("identity", {}))
    o2_dict = cast(dict[str, Any], v.get("oxygen_level", {}))
    energy_dict = cast(dict[str, Any], v.get("energy_reserves", {}))
    hull_dict = cast(dict[str, Any], v.get("hull_integrity", {}))
    suit_dict = cast(dict[str, Any], equip.get("suit_integrity", {}))
    fuel_dict = cast(dict[str, Any], v.get("fuel_cells", {}))
    # Sobrevivência — com defaults 100 para retrocompatibilidade
    fome_dict     = cast(dict[str, Any], v.get("fome",     {"current": 100, "max": 100}))
    sede_dict     = cast(dict[str, Any], v.get("sede",     {"current": 100, "max": 100}))
    exaustao_dict = cast(dict[str, Any], v.get("exaustao", {"current": 100, "max": 100}))

    return {
        "character": {
            "name":        str(identity_dict.get("name", "Ferro")),
            "hp_cur":      int(hp.get("current", 0)),
            "hp_max":      int(hp.get("max", 20)),
            "o2":          int(o2_dict.get("current", 100)),
            "energy":      int(energy_dict.get("current", 100)),
            "hull":        int(hull_dict.get("current", 100)),
            "suit":        int(suit_dict.get("current", 100)),
            "fuel_cur":    int(fuel_dict.get("current", 0)),
            "fuel_max":    int(fuel_dict.get("max", 100)),
            "fome":        int(fome_dict.get("current", 100)),
            "sede":        int(sede_dict.get("current", 100)),
            "exaustao":    int(exaustao_dict.get("current", 100)),
            "level":       int(prog.get("level", 1)),
            "xp_cur":      int(prog.get("xp_current", 0)),
            "xp_next":     int(prog.get("xp_to_next_level", 100)),
            "chip_carga":  int(chip.get("carga_atual", 0)),
            "weapon":      str(equip.get("weapon_primary", "—")),
            "armor":       str(equip.get("armor", "—")),
            "attrs":       attr_list,
            "passivas":    passivas,
            "status_effects": [{"id": e["id"], "stacks": e.get("stacks", 1)} for e in efx],
            "level_up_pending": prog.get("attribute_points_available", 0) > 0,
            "attr_pts":         prog.get("attribute_points_available", 0),
            "skill_pending":    prog.get("skill_choice_pending", False),
            "skill_choices_count": (2 if int(prog.get("level", 1)) >= 6 else 1),
            "available_skills":  _get_available_skills(
                int(prog.get("level", 1)),
                {k: int(v.get("value", 0)) for k, v in dict(attrs).items()},
                list(cs.get("passive_skills", [])),
            ),
        },
        "world": {
            "clima":    str(clima_dict.get("estado_atual", "LIMPO")),
            "periodo":  str(periodo_dict.get("estado_atual", "DIA")),
            "capitulo": str(cap.get("numero", "?")),
            "titulo":   str(cap.get("titulo", "")),
            "arco":     str(cap.get("arco", "")),
            "ambiente": str(cap.get("ambiente", "")),
            "interacoes": int(contagem.get("interacoes_no_capitulo", 0)),
        },
        "combat": {
            "ativo":       in_combat,
            "nome":        str(inimigo.get("nome", "")),
            "hp_cur":      int(inimigo.get("hp_atual", 0)),
            "hp_max":      int(inimigo.get("hp_maximo", 0)),
            "posicao":     str(pos_estado),
            "turno":       int(ac.get("turno_combate", 0)),
        },
        "inventory": inv_items,
        "mapa":      _parse_map(_read_json(_MAP_PATH)),
        "quests":    _parse_quests(_read(_QUEST_PATH, "")),
        "last_roll": _parse_last_roll(_read(_REPORT_PATH, "")),
    }


def get_menu_options(state: dict) -> list[dict]:
    in_combat  = state["combat"]["ativo"]
    inv        = state["inventory"]
    char       = state["character"]
    skill_pending = char.get("skill_pending", False)
    # Usáveis = itens consumíveis/recursos com usable=true E qty > 0
    # Armas, armaduras e equipamentos passivos NÃO entram aqui (são usados via combat)
    _TIPOS_NAO_CONSUMIVEIS = {"arma", "armadura", "equipamento passivo"}
    usaveis = [
        i["name"] for i in inv
        if i["usable"]
        and i["qty"] > 0
        and i.get("type", "").lower() not in _TIPOS_NAO_CONSUMIVEIS
    ]
    pos_atual  = state["combat"].get("posicao", "MELEE")

    options: list[dict] = []

    # Opções narrativas do GM
    # IMPORTANTE: quando skill_choice_pending=True, o GM gerou as habilidades como
    # opções narrativas (PARTE 3). Essas NÃO devem aparecer na grade de ações —
    # a escolha de skill usa o modal dedicado (botão 🎓 no HUD).
    # Apagamos também o arquivo para não reutilizá-lo no próximo turno.
    narrative_opts = []
    if skill_pending:
        # Limpa opções antigas geradas pelo GM (contêm nomes de skills, não ações)
        try:
            if os.path.exists(_OPTIONS_PATH):
                os.remove(_OPTIONS_PATH)
        except Exception:
            pass
    elif os.path.exists(_OPTIONS_PATH):
        try:
            narrative_opts = json.load(open(_OPTIONS_PATH, encoding="utf-8"))
        except Exception:
            pass

    if narrative_opts:
        options.append({"label": "── DECISÃO ──", "type": "separator"})
        icons = {
            "AGRESSAO DIRETA": "⚔",  "AGRESSÃO DIRETA": "⚔",
            "MANOBRA TATICA":  "🎯", "MANOBRA TÁTICA":  "🎯",
            "RECURSO": "💊", "RETIRADA": "🏃",
            "ANALISE": "📡", "ANÁLISE": "📡", "IMPROV": "🔧",
        }
        for opt in narrative_opts:
            arch = opt.get("archetype", "")
            icon = icons.get(arch, "▶")
            cmd_suffix = opt.get("cmd_suffix", ["explore", "--dc", "medio"])
            cmd = _SE + cmd_suffix
            # Resolve RECURSO:
            # Se há item usável → usa o primeiro disponível.
            # Se NÃO há item → executa explore (ação narrativa genérica).
            # NUNCA descarta a opção — [RECURSO] é uma ação narrativa, não depende de inventário.
            if cmd_suffix[0] == "use":
                if usaveis:
                    cmd = _SE + ["use", "--item", usaveis[0]]
                else:
                    cmd = _SE + ["explore", "--dc", "medio"]
            options.append({
                "label":        f"{icon} {opt.get('label', '')}",
                "type":         f"narrative_{cmd_suffix[0]}",
                "cmd":          cmd,
                "action_label": opt.get("label", ""),
                "narrative":    True,
            })
        options.append({"label": "── AÇÕES ──", "type": "separator"})

    # Ações mecânicas
    if in_combat:
        nome_ini = state["combat"]["nome"] or "Inimigo"
        options.append({"label": f"⚔  Atacar {nome_ini}", "type": "combat", "cmd": _SE + ["combat"]})
        nova_pos = "FLANQUEANDO" if pos_atual != "FLANQUEANDO" else "MELEE"
        options.append({"label": f"🎯 Mudar posição → {nova_pos} e atacar", "type": "combat",
                        "cmd": _SE + ["combat", "--position", nova_pos]})
        for item in usaveis:
            options.append({"label": f"💊 Usar {item}", "type": "use",
                            "cmd": _SE + ["use", "--item", item]})
        options.append({"label": "🏃 Fugir do combate (DES DC 15)", "type": "flee", "cmd": _SE + ["flee"]})
    else:
        options.append({"label": "🗺  Explorar área (SOB DC 15)",       "type": "explore", "cmd": _SE + ["explore", "--dc", "medio"]})
        options.append({"label": "🗺  Explorar área difícil (SOB DC 20)","type": "explore", "cmd": _SE + ["explore", "--dc", "dificil"]})
        options.append({"label": "📡 Scan / Análise (INT DC 15)",        "type": "scan",    "cmd": _SE + ["scan"]})
        for item in usaveis:
            options.append({"label": f"💊 Usar {item}", "type": "use", "cmd": _SE + ["use", "--item", item]})

    options.append({"label": "── SISTEMA ──", "type": "separator"})
    options.append({"label": "💾 Salvar checkpoint",       "type": "checkpoint_save"})
    options.append({"label": "📚 Status da story_bible",   "type": "arc_check"})

    return options


# ─────────────────────────────────────────────────────────────────────────────
# Rotas da API
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/state")
def api_state():
    state = get_game_state()
    options = get_menu_options(state)
    scene = _read(_SCENE_PATH, "")

    # Extrai narrativa (PARTE 2) e opções (PARTE 3) da cena
    narrative = ""
    if scene:
        sc_lines_raw = str(scene).splitlines()
        try:
            # Itera UMA vez: encontra idx2 e então continua o mesmo iterador para idx3.
            # Resetar para enumerate(sc_lines_raw) faria PARTE 3 ser encontrada antes de PARTE 2
            # se houver referência anterior no texto (ex: "ver PARTE 3" em PARTE 1).
            enum_lines = enumerate(sc_lines_raw)
            idx2 = next(i for i, line in enum_lines if "PARTE 2" in str(line).upper())
            # Continua o iterador a partir de onde parou (após idx2)
            try:
                idx3 = next(i for i, line in enum_lines if "PARTE 3" in str(line).upper())
                end_idx = idx3
            except StopIteration:
                end_idx = len(sc_lines_raw)
                
            block_lines = []
            for i in range(idx2, end_idx):
                block_lines.append(str(sc_lines_raw[i]))
            
            block = "\n".join(block_lines)
            lines = block.split("\n")
            
            content_lines: list[Any] = []
            skip = True
            for l_raw in lines:
                l_str = str(l_raw)
                if skip and ("PARTE 2" in l_str.upper() or l_str.strip().startswith("**")):
                    skip = False
                    continue
                content_lines.append(l_str)
            narrative = "\n".join([str(c) for c in content_lines]).strip()
        except StopIteration:
            narrative = str(scene)
            
    recent_logs = []
    log_size = len(pipeline_log)
    start_idx = max(0, log_size - 20)
    for i in range(start_idx, log_size):
        recent_logs.append(str(pipeline_log[i]))
            
    return jsonify({
        "state":     state,
        "options":   options,
        "narrative": narrative,
        "log":       recent_logs,
    })


@app.route("/api/scene")
def api_scene():
    return jsonify({"scene": _read(_SCENE_PATH, ""), "log": _read(_REPORT_PATH, "")})


@app.route("/api/turn", methods=["POST"])
def api_action():
    if not pipeline_lock.acquire(blocking=False):
        return jsonify({"error": "Pipeline em execução — aguarde."}), 429

    pipeline_log.clear()

    try:
        body         = request.get_json() or {}
        action_type  = body.get("type", "explore")
        action_label = body.get("action_label", action_type)
        cmd          = body.get("cmd", _SE + ["explore", "--dc", "medio"])

        # Converte lista (vinda do JSON) em lista de strings
        if isinstance(cmd, list):
            cmd = [str(c) for c in cmd]
        else:
            cmd = _SE + ["explore", "--dc", "medio"]

        # Ações de sistema (sem pipeline)
        if action_type == "checkpoint_save":
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "checkpoint_manager",
                    os.path.join(_HERE, "checkpoint_manager.py")
                )
                if spec is not None:
                    loader = spec.loader
                    if loader is not None:
                        cm = importlib.util.module_from_spec(spec)
                        loader.exec_module(cm)
                        ckpt_id = cm.CheckpointManager().save_now("manual_web")
                        pipeline_log.append(f"💾 Checkpoint salvo: {ckpt_id}")
                    else:
                        pipeline_log.append("⚠ Erro no checkpoint: loader is None")
                else:
                    pipeline_log.append("⚠ Erro no checkpoint: spec is None")
            except Exception as e:
                pipeline_log.append(f"⚠ Erro no checkpoint: {e}")
            return jsonify({"ok": True, "log": pipeline_log})

        if action_type == "arc_check":
            try:
                story_path = os.path.join(_CTX_DIR, "story_bible.md")
                size = len(_read(story_path))
                status = "OK"
                if size >= 15000:
                    status = "CRÍTICO"
                elif size >= 8000:
                    status = "ALERTA"
                pipeline_log.append(f"📚 story_bible: {size} chars — {status}")
            except Exception as e:
                pipeline_log.append(f"⚠ {e}")
            return jsonify({"ok": True, "log": pipeline_log})

        # Pipeline completo: 4 passos
        pipeline_log.append(f"▶ Ação: {action_label}")

        # ── BLOQUEIO POR LEVEL UP PENDENTE ────────────────────────────────────
        # Se há pontos de atributo ou escolha de skill pendentes, o turno não avança.
        # O jogador precisa resolver o level up antes de continuar.
        try:
            _cs_check = _read_json(_CS_PATH)
            _prog_check = _cs_check.get("progression", {})
            _attr_pts   = int(_prog_check.get("attribute_points_available", 0))
            _sk_pending = bool(_prog_check.get("skill_choice_pending", False))
            if _attr_pts > 0:
                pipeline_log.append("⚠ BLOQUEADO: distribua os pontos de atributo antes de continuar.")
                state   = get_game_state()
                options = get_menu_options(state)
                return jsonify({"ok": False, "state": state, "options": options,
                                "log": pipeline_log})
            if _sk_pending:
                pipeline_log.append("⚠ BLOQUEADO: escolha uma habilidade passiva antes de continuar.")
                pipeline_log.append("  Clique em '🎓 HABILIDADE PASSIVA — ESCOLHER' no painel.")
                state   = get_game_state()
                options = get_menu_options(state)
                return jsonify({"ok": False, "state": state, "options": options,
                                "log": pipeline_log})
        except Exception:
            pass

        # ── SNAPSHOT PRÉ-TURNO (para rollback em caso de 503) ────────────────
        _ckpt_id = None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "checkpoint_manager",
                os.path.join(_HERE, "checkpoint_manager.py")
            )
            if spec and spec.loader:
                cm = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cm)
                _ckpt_id = cm.CheckpointManager().save_now("pre_turn")
        except Exception as e:
            pipeline_log.append(f"⚠ Erro no snapshot pré-turno: {e}")

        def _rollback_turn():
            """Restaura o estado pré-turno a partir do snapshot."""
            if _ckpt_id:
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "checkpoint_manager",
                        os.path.join(_HERE, "checkpoint_manager.py")
                    )
                    if spec and spec.loader:
                        cm = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(cm)
                        cm.CheckpointManager().restore(_ckpt_id)
                        pipeline_log.append("↩ Estado pré-turno restaurado (rollback).")
                except Exception as e:
                    pipeline_log.append(f"⚠ Erro no rollback: {e}")

        # Passo 1 — system_engine
        se_out = run_script(cmd, "Passo 1 — System Engine")
        # Salva stdout do system_engine em technical_report.txt (lido por GM, Archivist e /api/state)
        try:
            os.makedirs(_DRAFT_DIR, exist_ok=True)
            with open(_REPORT_PATH, "w", encoding="utf-8") as _f:
                _f.write(se_out or "")
        except Exception as _e:
            pipeline_log.append(f"⚠ Erro ao salvar technical_report: {_e}")

        # Passo 1.5 — world_state_ticker (ciclo dia/noite, clima, eventos)
        run_script(_WST, "Passo 1.5 — World Ticker")

        # Passo 2 — architect (check + auto-loot)
        run_script(_AR + ["check"], "Passo 2 — Architect (check)")

        # Auto-loot: se combate acabou neste turno, aplica loot automaticamente
        try:
            _ac_now = _read_json(_AC_PATH)
            _combat_active = bool(_ac_now.get("combate_ativo", False))
            _enemy_name = _ac_now.get("inimigo", {}).get("nome", "")
            _enemy_hp = _ac_now.get("inimigo", {}).get("hp_atual", 1)
            if not _combat_active and _enemy_name and _enemy_hp <= 0:
                run_script(_AR + ["apply_loot"], "Passo 2.1 — Architect (loot)")
        except Exception:
            pass

        # Passo 3 — game_master
        # Apaga opções antigas para evitar que opções velhas reapareçam se parse falhar
        try:
            if os.path.exists(_OPTIONS_PATH):
                os.remove(_OPTIONS_PATH)
        except Exception:
            pass
        gm_out = run_script(_GM + ["--action", action_label], "Passo 3 — Game Master (Gemini)")

        # ── DETECÇÃO DE 503 UNAVAILABLE — rollback completo ──────────────────
        _is_503 = ("503" in (gm_out or "") and "UNAVAILABLE" in (gm_out or ""))
        if _is_503:
            _rollback_turn()
            pipeline_log.append("⚠ Gemini 503 UNAVAILABLE — Gemini sobrecarregado.")
            pipeline_log.append("  O turno NÃO foi contabilizado. Tente novamente em alguns segundos.")
            return jsonify({
                "ok":    False,
                "error": "gemini_503",
                "log":   pipeline_log,
            }), 503

        # Se GM não gerou opções (parse falhou), tenta parsear diretamente a cena
        if not os.path.exists(_OPTIONS_PATH):
            # Fallback: parseia a cena diretamente sem depender do game_master
            try:
                import sys as _sys
                _sys.path.insert(0, _HERE)
                from game_master import parse_narrative_options as _pno, save_narrative_options as _sno  # type: ignore
                _scene_txt = _read(_SCENE_PATH, "")
                _opts = _pno(_scene_txt)
                if _opts:
                    _sno(_opts)
                    pipeline_log.append(f"  ↳ [GM] {len(_opts)} opções parseadas (fallback)")
                else:
                    pipeline_log.append("  ↳ [GM] AVISO: PARTE 3 não encontrada na cena")
            except Exception as _e:
                pipeline_log.append(f"  ↳ [GM] fallback parse erro: {_e}")

        # Passo 3.5 — scene_processor (extrai deltas da PARTE 4)
        run_script(_SP, "Passo 3.5 — Scene Processor")

        # Passo 4 — lore_archivist
        la_out = run_script(_LA, "Passo 4 — Lore Archivist (Gemini)")
        # 503 no Archivist: narrativa já foi gerada, apenas loga aviso (não faz rollback)
        if "503" in (la_out or "") and "UNAVAILABLE" in (la_out or ""):
            pipeline_log.append("⚠ Lore Archivist 503 — arquivamento pulado. Narrativa OK.")

        # Consome opções narrativas APÓS pipeline concluído (novo arquivo já gerado pelo GM)
        if action_type.startswith("narrative_") and os.path.exists(_OPTIONS_PATH):
            pass  # já foi gerado novo _OPTIONS_PATH pelo game_master no passo 3

        # Checkpoint automático
        try:
            import importlib.util
            s = importlib.util.spec_from_file_location("cm", os.path.join(_HERE, "checkpoint_manager.py"))
            if s is not None:
                loader = s.loader
                if loader is not None:
                    m = importlib.util.module_from_spec(s)
                    loader.exec_module(m)
                    saved = m.CheckpointManager().maybe_save(interval=5)
                    if saved:
                        pipeline_log.append(f"💾 Checkpoint automático: {saved}")
        except Exception:
            pass

        state   = get_game_state()
        options = get_menu_options(state)
        scene   = _read(_SCENE_PATH, "")

        return jsonify({
            "ok":      True,
            "state":   state,
            "options": options,
            "scene":   scene,
            "log":     pipeline_log,
        })

    except Exception as e:
        pipeline_log.append(f"✗ Erro fatal: {e}")
        return jsonify({"error": str(e), "log": pipeline_log}), 500
    finally:
        pipeline_lock.release()


@app.route("/api/levelup", methods=["POST"])
def api_levelup():
    """Recebe {atributo: pontos_gastos} e aplica no character_sheet.json."""
    VALID_ATTRS = {"forca", "destreza", "inteligencia", "sobrevivencia", "percepcao", "carisma"}
    try:
        body = request.get_json(force=True) or {}
        raw_spent = body.get("spent", {}) if isinstance(body, dict) else {}
        spent = cast(dict[str, Any], raw_spent)
        total   = sum(int(v) for v in spent.values())

        sheet   = _read_json(_CS_PATH)
        prog = cast(dict[str, Any], sheet.get("progression", {}))
        avail   = int(prog.get("attribute_points_available", 0))

        if total <= 0:
            return jsonify({"error": "Nenhum ponto distribuído."}), 400
        if total > avail:
            return jsonify({"error": f"Tentando gastar {total} pontos mas só há {avail} disponíveis."}), 400

        attrs_db = cast(dict[str, Any], sheet.get("attributes", {}))
        for attr, pts_raw in spent.items():
            pts = int(pts_raw)
            if pts <= 0 or attr not in VALID_ATTRS:
                continue
            
            # Ensure proper typing inside attrs dictionary
            attr_dict = cast(dict[str, Any], attrs_db.get(attr, {}))
            
            if "value" not in attr_dict:
                attr_dict["value"] = 0
            
            attr_dict["value"] = int(attr_dict.get("value", 0)) + pts
            attrs_db[attr] = attr_dict

        avail_pts = int(prog.get("attribute_points_available", 0) or 0)
        spent_pts = int(prog.get("total_attribute_points_spent", 0) or 0)
        
        prog["attribute_points_available"]  = int(avail_pts) - int(total)
        prog["total_attribute_points_spent"] = int(spent_pts) + int(total)
        sheet["attributes"]  = attrs_db
        sheet["progression"] = prog

        # Gravação atômica
        tmp = _CS_PATH + ".tmp"
        import json
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sheet, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _CS_PATH)
        
        rem_raw = prog.get("attribute_points_available", 0)
        return jsonify({"ok": True, "pontos_restantes": int(cast(Any, rem_raw))})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/skill", methods=["POST"])
def api_skill():
    """Recebe {skill_ids: [str]} e aplica no character_sheet.json."""
    try:
        body       = request.get_json(force=True) or {}
        skill_ids  = body.get("skill_ids", [])
        if not skill_ids or not isinstance(skill_ids, list):
            return jsonify({"error": "Envie skill_ids como lista."}), 400

        sheet      = _read_json(_CS_PATH)
        prog       = cast(dict[str, Any], sheet.get("progression", {}))
        attrs_raw  = cast(dict[str, Any], sheet.get("attributes", {}))
        nivel      = int(prog.get("level", 1))
        adquiridas = list(sheet.get("passive_skills", []))

        # Quantas escolhas são permitidas
        choices_allowed = 2 if nivel >= 6 else 1
        if len(skill_ids) > choices_allowed:
            return jsonify({"error": f"Nível {nivel} permite {choices_allowed} habilidade(s)."}), 400

        # Validar cada skill
        abbr_map = {"forca":"FOR","destreza":"DES","inteligencia":"INT",
                    "sobrevivencia":"SOB","percepcao":"PER","carisma":"CAR"}
        attrs_abbr: dict[str, int] = {}
        for k, v in attrs_raw.items():
            k_str = str(k)
            abbr = k_str[:3].upper()  # type: ignore
            attrs_abbr[abbr_map.get(k_str, abbr)] = int(v.get("value", 0))

        if _ME is None:
            return jsonify({"error": "mechanics_engine não carregado — reinicie o servidor."}), 500

        elegiveis_ids: set[str] = set()
        try:
            elegiveis_ids = {s["id"] for s in _ME.get_available_passive_skills(nivel, attrs_abbr, adquiridas)}
        except Exception as e:
            return jsonify({"error": f"Erro ao verificar elegibilidade: {e}"}), 500

        for sid in skill_ids:
            if sid in adquiridas:
                return jsonify({"error": f"Habilidade '{sid}' já adquirida."}), 400
            if sid not in elegiveis_ids:
                return jsonify({"error": f"Habilidade '{sid}' não elegível para nível {nivel} e atributos atuais."}), 400

        # Aplicar
        for sid in skill_ids:
            adquiridas.append(sid)

        sheet["passive_skills"] = adquiridas
        prog["skill_choice_pending"] = False
        sheet["progression"] = prog

        # Gravação atômica
        tmp = _CS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sheet, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _CS_PATH)

        return jsonify({"ok": True, "passive_skills": adquiridas})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(os.path.join(_HERE, "web_ui"), exist_ok=True)
    print("\n" + "="*55)
    print("  CHRONOS RPG ENGINE — Interface Web")
    print("="*55)
    print(f"  Acesse: http://localhost:5000")
    print(f"  Projeto: {_PROJ}")
    print("  Ctrl+C para encerrar\n")
    app.run(debug=False, host="0.0.0.0", port=5000)