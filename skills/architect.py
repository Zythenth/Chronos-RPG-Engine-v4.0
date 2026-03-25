#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
architect.py — Guardião do Estado & Expansão do Mundo
Chronos RPG Engine v4.0

Substitui o agente Architect (IA) por Python puro.
Persiste estado, inicia/encerra combates, aplica loot e level-up.

COMANDOS:
  python architect.py start_combat --enemy "Nome Exato"
  python architect.py apply_loot
  python architect.py choose_skill --skill SKILL_ID
  python architect.py loot --d20 N
  python architect.py add_item --item "Nome Exato" [--qty N]
  python architect.py remove_item --item "Nome Exato" [--qty N]
  python architect.py check
  python architect.py list_skills
"""

import sys
import io
import os
import json
import csv
import re
import argparse

# ── Encoding Windows ──────────────────────────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Caminhos ──────────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_STATE_DIR = os.path.join(_HERE, "..", "current_state")
_CTX_DIR   = os.path.join(_HERE, "..", "world_context")
_CS_PATH   = os.path.join(_STATE_DIR, "character_sheet.json")
_AC_PATH   = os.path.join(_STATE_DIR, "active_combat.json")
_INV_PATH  = os.path.join(_STATE_DIR, "inventory.csv")
_BST_PATH  = os.path.join(_CTX_DIR,   "bestiary.md")

# ── Importa mechanics_engine e loot_manager ──────────────────────────────────
import importlib.util as _ilu

def _load_module(name: str, path: str):
    spec = _ilu.spec_from_file_location(name, path)
    mod  = _ilu.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)         # type: ignore
    return mod

_me = _load_module("mechanics_engine", os.path.join(_HERE, "mechanics_engine.py"))
_lm = _load_module("loot_manager",     os.path.join(_HERE, "loot_manager.py"))

# ─────────────────────────────────────────────────────────────────────────────
# 1. I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def validate_character_sheet(cs: dict) -> list[str]:
    erros = []
    vitals = cs.get("vitals", {})
    hp = vitals.get("hp", {})
    en = vitals.get("energy_reserves", {})
    prog = cs.get("progression", {})
    
    if not isinstance(hp.get("current"), int) or hp.get("current", -1) < 0:
        erros.append(f"hp.current = {hp.get('current')}")
    if not isinstance(hp.get("max"), int) or hp.get("max", -1) < 0:
        erros.append(f"hp.max = {hp.get('max')}")
    if not isinstance(en.get("current"), int) or not (0 <= en.get("current", -1) <= 100):
        erros.append(f"energy_reserves.current = {en.get('current')}")
    if not isinstance(prog.get("level"), int) or prog.get("level", 0) < 1:
        erros.append(f"level = {prog.get('level')}")
    if not isinstance(prog.get("xp_current"), int) or prog.get("xp_current", -1) < 0:
        erros.append(f"xp_current = {prog.get('xp_current')}")
    
    return erros

def save_json(path: str, data: dict) -> None:
    if os.path.basename(path) == "character_sheet.json":
        erros = validate_character_sheet(data)
        if erros:
            for erro in erros:
                print(f"ERRO DE VALIDAÇÃO: {erro}")
            print("Tentando recuperar do checkpoint mais recente...")
            try:
                _cm = _load_module("checkpoint_manager", os.path.join(_HERE, "checkpoint_manager.py"))
                ckpt = _cm.CheckpointManager()
                ckpt.restore(-1)  # -1 = mais recente (0 seria o mais antigo)
            except Exception as e:
                print(f"Falha ao recuperar checkpoint: {e}")
            return

    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def load_inventory() -> list[dict]:
    with open(_INV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def save_inventory(rows: list[dict]) -> None:
    # Nunca retorna cedo: se o inventário ficou vazio, limpa o CSV corretamente.
    # DEVE incluir "durability" e "durability_max" — colunas idênticas ao system_engine.
    # Se omitidas aqui, cada cmd_apply_loot/add_item/remove_item corrompe o CSV
    # silenciosamente, apagando a durabilidade de todos os itens.
    fields = ["id","name","type","rarity","quantity","weight_kg","effect","usable","durability","durability_max","notes"]
    temp_path = f"{_INV_PATH}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k,"") for k in fields})
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, _INV_PATH)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

# ─────────────────────────────────────────────────────────────────────────────
# 2. PARSER DO BESTIARY.MD
# ─────────────────────────────────────────────────────────────────────────────

def _parse_bestiary(path: str) -> dict:
    """
    Lê bestiary.md e retorna dict { nome_canônico → dados_da_ficha }.
    Nome canônico = texto após '## Nome:' sem sufixos de boss/capítulo.
    """
    if not os.path.exists(path):
        return {}

    text   = open(path, encoding="utf-8").read()
    blocks = re.split(r'\n---\n', text)
    result = {}

    for block in blocks:
        m_nome = re.search(r'## Nome:\s*(.+)', block)
        if not m_nome:
            continue
        nome_raw = m_nome.group(1).strip()
        # Remove sufixos como " *(Boss — Cap. 9)*"
        nome_canon = re.sub(r'\s*\*.*?\*\s*$', '', nome_raw).strip()
        if nome_canon == '_______________________':
            continue  # template

        def _get(pattern, default=None):
            m = re.search(pattern, block, re.IGNORECASE)
            return m.group(1).strip() if m else default

        # HP
        hp_max = int(_get(r'\*\*HP:\*\*\s*\d+\s*/\s*(\d+)', 0) or 0)

        # Combate
        dc_raw    = _get(r'\*\*DC de Defesa:\*\*\s*(\d+)')
        dano_raw  = _get(r'\*\*Dano por Turno:\*\*\s*(\d+)')
        racial_raw = _get(r'\*\*B[oô]nus Racial de Dano:\*\*\s*(\d+)')
        tipo_dano  = _get(r'tipo:\s*([\w\s]+?)(?:\s*—|\s*\*|\))', 'Físico')
        crit_efeito = _get(r'\*\*Acerto Cr[ií]tico:\*\*\s*(.+?)(?:\n|$)')
        threshold  = _get(r'\*\*Threshold Moral:\*\*\s*(.+?)(?:\n|$)', 'Nunca')
        fase2_txt  = _get(r'\*\*Fase 2 \(Boss\):\*\*\s*(.+?)(?:\n|$)', 'Não')
        classe     = _get(r'\*\*Classe:\*\*\s*(.+?)(?:\n|$)', 'Biológico')
        habitat    = _get(r'\*\*Habitat:\*\*\s*(.+?)(?:\n|$)')
        comportamento = _get(r'\*\*Comportamento:\*\*\s*(.+?)(?:\n|$)')
        fraqueza   = _get(r'\*\*Fraqueza:\*\*\s*(.+?)(?:\n|$)')
        drop_txt   = _get(r'\*\*Drop \(Loot\):\*\*\s*(.+?)(?:\n|$)', '')
        imunidade  = _get(r'\*\*Imunidade:\*\*\s*(.+?)(?:\n|$)')
        resistencia = _get(r'\*\*Resist[eê]ncia:\*\*\s*(.+?)(?:\n|$)')
        hab_esp    = _get(r'\*\*Habilidade Especial:\*\*\s*(.+?)(?:\n|$)')

        # Bônus racial: se não explícito no MD, calcula por FOR
        if racial_raw is None:
            for_raw = _get(r'FOR\s*\|\s*(\d+)')
            for_val = int(for_raw) if for_raw else 10
            racial  = max(0, (for_val - 10) // 2)
        else:
            racial = int(racial_raw)

        # Threshold de fuga
        threshold_pct = 0.0
        if threshold and threshold.lower() != 'nunca':
            m_pct = re.search(r'(\d+)', threshold)
            if m_pct:
                threshold_pct = int(m_pct.group(1)) / 100.0

        # Boss
        e_boss = 'sim' in (fase2_txt or '').lower()

        result[nome_canon] = {
            "nome":         nome_canon,
            "classe":       classe or "Biológico",
            "raca":         nome_raw,
            "hp_maximo":    hp_max,
            "dc_defesa":    int(dc_raw) if dc_raw else 12,
            "dano_por_turno": int(dano_raw) if dano_raw else 2,
            "damage_bonus_racial": racial,
            "tipo_dano":    (tipo_dano or "Físico").strip(),
            "is_territorial": classe != "Mecânico",
            "ficha_racial": {
                "descricao_curta": comportamento or "???",
                "habitat":         habitat or "???",
                "comportamento":   comportamento or "???",
                "fraqueza":        fraqueza or "???",
                "imunidade":       imunidade,
                "resistencia":     resistencia,
                "acerto_critico_efeito": crit_efeito or "Dano duplo.",
                "habilidade_especial":   hab_esp,
                "drop":            drop_txt or "Nenhum.",
            },
            "_threshold_pct": threshold_pct,
            "_e_boss":       e_boss,
        }

    return result


def _find_enemy(name: str, bestiary: dict) -> tuple[str, dict]:
    """
    Busca tolerante: tenta match exato, depois case-insensitive, depois parcial.
    Retorna (nome_encontrado, dados) ou levanta ValueError.
    """
    if name in bestiary:
        return name, bestiary[name]
    name_l = name.lower()
    for k, v in bestiary.items():
        if k.lower() == name_l:
            return k, v
    for k, v in bestiary.items():
        if name_l in k.lower():
            return k, v
    raise ValueError(
        f"Inimigo '{name}' não encontrado no bestiário.\n"
        f"  Inimigos disponíveis: {list(bestiary.keys())}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# 3. TEMPLATE VAZIO DE ACTIVE_COMBAT
# ─────────────────────────────────────────────────────────────────────────────

def _empty_combat_template(turno: int) -> dict:
    return {
        "meta": {
            "version": "4.0",
            "last_updated": f"TURNO_{turno}",
            "instrucao": "Zerado pelo Architect após morte do inimigo."
        },
        "combate_ativo": False,
        "turno_combate": 0,
        "posicionamento": {
            "estado_atual": "MELEE",
            "_estados_validos": "MELEE | DISTANCIA | COBERTO | FLANQUEANDO",
            "_instrucao": "Atualizado quando jogador declara mudança de posição."
        },
        "inimigo": {
            "nome": None, "classe": None, "raca": None,
            "hp_atual": None, "hp_maximo": None,
            "dc_defesa": None, "dc_defesa_efetiva": None,
            "dano_por_turno": None, "damage_bonus_racial": None,
            "_damage_bonus_racial_instrucao": "int — max(0,(FOR-10)//2).",
            "tipo_dano": None, "is_territorial": None,
            "status_effects": [],
            "ficha_racial": {
                "descricao_curta": None, "habitat": None, "comportamento": None,
                "fraqueza": None, "imunidade": None, "resistencia": None,
                "acerto_critico_efeito": None, "habilidade_especial": None,
                "drop": None,
            }
        },
        "moral": {
            "fugiu": False,
            "_instrucao": "Atualizado por check_enemy_morale() após cada dano."
        },
        "multi_inimigos": {
            "ativo": False, "lista": [],
            "_lista_schema": {"nome":"str","classe":"str","hp_atual":"int","hp_maximo":"int",
                              "dano_por_turno":"int","damage_bonus_racial":"int",
                              "dc_defesa":"int","tipo_dano":"str"},
            "_instrucao": "Se ativo=true, todos os inimigos em lista contra-atacam por turno."
        },
        "boss_state": {
            "e_boss": False, "fase_atual": 1, "fase_ativada": False,
            "dano_bonus_fase2": 0, "dc_bonus_fase2": 0, "habilidade_fase2": None,
            "_instrucao": "check_boss_phase() chamado após cada dano."
        },
        "jogador": {
            "arma_equipada": None, "armadura_equipada": None, "tem_armadura": False
        },
        "historico_dano": []
    }

# ─────────────────────────────────────────────────────────────────────────────
# 4. HELPERS DE INVENTÁRIO
# ─────────────────────────────────────────────────────────────────────────────

def _add_item_to_inv(inv: list[dict], name: str, qty: int = 1) -> list[dict]:
    """Adiciona ou incrementa item. Usa ITEM_SCHEMA do loot_manager."""
    for row in inv:
        if row["name"] == name:
            row["quantity"] = str(int(row["quantity"]) + qty)
            return inv

    schema = _lm.ITEM_SCHEMA.get(name)
    if not schema:
        # Item desconhecido — adiciona como genérico
        print(f"  ⚠ AVISO: '{name}' não encontrado em ITEM_SCHEMA. Adicionado como genérico.")
        schema = {"type":"Material","rarity":"Comum","weight_kg":0.5,
                  "effect":"Item desconhecido.","usable":False,"notes":"Adicionado manualmente."}

    next_id = max((int(r.get("id",0)) for r in inv if str(r.get("id","0")).isdigit()), default=0) + 1
    # Determina durabilidade: presente para arma/armadura, vazio para outros
    _item_type = schema.get("type", "Material").lower()
    _has_dur = _item_type in ("arma", "armadura")
    _dur_val = str(schema.get("durabilidade", 10)) if _has_dur else ""
    _dur_max = str(schema.get("durabilidade", 10)) if _has_dur else ""

    inv.append({
        "id": str(next_id), "name": name, "quantity": str(qty),
        "type":           schema.get("type","Material"),
        "rarity":         schema.get("rarity","Comum"),
        "weight_kg":      str(schema.get("weight_kg",0.5)),
        "effect":         schema.get("effect",""),
        "usable":         str(schema.get("usable",False)).lower(),
        "durability":     _dur_val,
        "durability_max": _dur_max,
        "notes":          schema.get("notes",""),
    })
    return inv

def _remove_item_from_inv(inv: list[dict], name: str, qty: int = 1) -> list[dict]:
    for row in inv:
        if row["name"] == name:
            cur = int(row["quantity"])
            if cur < qty:
                raise ValueError(f"Quantidade insuficiente de '{name}': disponível={cur}, pedido={qty}")
            row["quantity"] = str(cur - qty)
            return [r for r in inv if int(r["quantity"]) > 0]
    raise ValueError(f"Item '{name}' não encontrado no inventário.")

def _get_current_turn(cs: dict) -> int:
    raw = cs.get("meta", {}).get("last_updated", "TURNO_0")
    try:
        return int(raw.split("_")[1])
    except Exception:
        return 0

# ─────────────────────────────────────────────────────────────────────────────
# 5. COMANDOS
# ─────────────────────────────────────────────────────────────────────────────

# ── 5.1 START COMBAT ─────────────────────────────────────────────────────────

def cmd_start_combat(args) -> None:
    bestiary = _parse_bestiary(_BST_PATH)
    enemy_name = args.enemy

    nome_encontrado, dados = _find_enemy(enemy_name, bestiary)

    cs    = load_json(_CS_PATH)
    ac    = load_json(_AC_PATH)
    turno = _get_current_turn(cs)

    if ac.get("combate_ativo"):
        print(f"⚠ AVISO: Já existe combate ativo com '{ac['inimigo']['nome']}'. Encerre antes de iniciar outro.")
        return

    # Posição padrão ao iniciar
    position = (args.position or "MELEE").upper()

    # Arma/armadura do jogador
    weapon  = args.weapon  or cs.get("equipment",{}).get("weapon_primary")
    armor   = cs.get("equipment",{}).get("armor")

    ac_novo = _empty_combat_template(turno)
    ac_novo["combate_ativo"]  = True
    ac_novo["turno_combate"]  = 0
    ac_novo["posicionamento"]["estado_atual"] = position

    # Inimigo
    ac_novo["inimigo"].update({
        "nome":               dados["nome"],
        "classe":             dados["classe"],
        "raca":               dados["raca"],
        "hp_atual":           dados["hp_maximo"],
        "hp_maximo":          dados["hp_maximo"],
        "dc_defesa":          dados["dc_defesa"],
        "dc_defesa_efetiva":  dados["dc_defesa"],
        "dano_por_turno":     dados["dano_por_turno"],
        "damage_bonus_racial":dados["damage_bonus_racial"],
        "tipo_dano":          dados["tipo_dano"],
        "is_territorial":     dados["is_territorial"],
        "status_effects":     [],
        "ficha_racial":       dados["ficha_racial"],
    })

    # Boss state
    if dados.get("_e_boss"):
        ac_novo["boss_state"]["e_boss"] = True

    # Jogador
    ac_novo["jogador"].update({
        "arma_equipada":   weapon,
        "armadura_equipada": armor,
        "tem_armadura":    armor is not None,
    })

    save_json(_AC_PATH, ac_novo)

    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. COMBATE INICIADO")
    print(f"   Inimigo:    {dados['nome']}")
    print(f"   HP:         {dados['hp_maximo']} / {dados['hp_maximo']}")
    print(f"   DC Defesa:  {dados['dc_defesa']}")
    print(f"   Dano/Turno: {dados['dano_por_turno']} (tipo: {dados['tipo_dano']})")
    print(f"   Racial:     +{dados['damage_bonus_racial']}")
    print(f"   Posição:    {position}")
    print(f"   Boss:       {'SIM' if dados.get('_e_boss') else 'Não'}")
    print(f"\n   Fraqueza:    {dados['ficha_racial']['fraqueza']}")
    print(f"   Comportamento: {dados['ficha_racial']['comportamento']}")
    print(f"   Drop:        {dados['ficha_racial']['drop']}")
    print(f"\n2. active_combat.json → atualizado (combate_ativo: true)")
    print()

# ── 5.2 APPLY LOOT ───────────────────────────────────────────────────────────

def cmd_apply_loot(args) -> None:
    ac  = load_json(_AC_PATH)
    inv = load_inventory()
    cs  = load_json(_CS_PATH)
    turno = _get_current_turn(cs)

    # O inimigo pode já ter sido zerado pelo system_engine — guarda o nome no histórico
    # Tenta ler do combate atual ou do histórico mais recente
    enemy_name = ac.get("inimigo", {}).get("nome")

    if ac.get("combate_ativo"):
        print("⚠ AVISO: Combate ainda ativo. Execute 'python system_engine.py combat' até o inimigo morrer.")
        return

    if not enemy_name:
        print("⚠ AVISO: Nenhum inimigo registrado em active_combat.json → inimigo.nome.")
        print("   Use: python architect.py add_item --item 'Nome do Item' --qty N")
        return

    drops = _lm.get_combat_drops(enemy_name)

    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. LOOT DO INIMIGO: {enemy_name}")

    if not drops:
        print(f"   Nenhum drop definido para '{enemy_name}'.")
    else:
        for item_name, qty in drops:
            inv = _add_item_to_inv(inv, item_name, qty)
            print(f"   + {item_name} × {qty} → inventário")

    save_inventory(inv)

    # Zera o nome do inimigo no active_combat para não aplicar loot duas vezes
    ac["inimigo"]["nome"] = None
    save_json(_AC_PATH, ac)

    print(f"\n2. inventory.csv → atualizado")
    print(f"   active_combat.json → inimigo.nome zerado (anti-duplicata)")

    _print_alerts(cs, ac)
    print()

# ── 5.3 CHOOSE SKILL ─────────────────────────────────────────────────────────

def cmd_choose_skill(args) -> None:
    cs    = load_json(_CS_PATH)
    turno = _get_current_turn(cs)

    if not cs.get("progression", {}).get("skill_choice_pending"):
        print("⚠ skill_choice_pending = false. Nenhuma habilidade pendente.")
        return

    skill_id = args.skill
    if skill_id not in _me.PASSIVE_SKILLS:
        print(f"⚠ ERRO: id '{skill_id}' não encontrado em PASSIVE_SKILLS.")
        print(f"  Use 'python architect.py list_skills' para ver os disponíveis.")
        return

    passive_list = cs.get("passive_skills", [])
    if skill_id in passive_list:
        print(f"⚠ ERRO: '{skill_id}' já está em passive_skills.")
        return

    nivel = cs["progression"]["level"]
    atributos = {abbr: cs["attributes"][k]["value"]
                 for abbr, k in _me.ATTRIBUTE_MAP.items()
                 if k in cs["attributes"]}

    available = _me.get_available_passive_skills(nivel, atributos, passive_list)
    ids_available = [s["id"] for s in available]

    if skill_id not in ids_available:
        skill_def = _me.PASSIVE_SKILLS.get(skill_id, {})
        print(f"⚠ ERRO: '{skill_id}' não elegível agora.")
        print(f"  Nível mínimo: {skill_def.get('nivel_minimo','?')} (atual: {nivel})")
        print(f"  Requisitos:   {skill_def.get('requisito',{})}")
        print(f"  Elegíveis agora: {ids_available}")
        return

    passive_list.append(skill_id)
    cs["passive_skills"] = passive_list
    cs["progression"]["skill_choice_pending"] = False

    save_json(_CS_PATH, cs)

    skill_def = _me.PASSIVE_SKILLS[skill_id]
    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. HABILIDADE PASSIVA ADQUIRIDA")
    print(f"   ID:           {skill_id}")
    print(f"   Nome:         {skill_def['nome']}")
    print(f"   Categoria:    {skill_def['categoria']}")
    print(f"   Efeito:       {skill_def['efeito']['descricao']}")
    print(f"\n2. character_sheet.json → passive_skills: {passive_list}")
    print(f"   skill_choice_pending: true → false")
    print()

# ── 5.4 LOOT (exploração) ────────────────────────────────────────────────────

def cmd_loot(args) -> None:
    cs    = load_json(_CS_PATH)
    inv   = load_inventory()
    turno = _get_current_turn(cs)
    d20   = int(args.d20)

    if d20 < 1 or d20 > 20:
        print("⚠ ERRO: d20 deve estar entre 1 e 20.")
        return

    result = _lm.roll_loot(d20)

    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. LOOT DE EXPLORAÇÃO")
    print(f"   d20 bruto: {d20} → Tabela {result['table']}")

    if result["item_name"] is None:
        print(f"   Resultado: EXPANSÃO — d20={d20} ≥ 17 e item não existe.")
        print(f"   Condição: Avalie PROTOCOLO DE EXPANSÃO manualmente.")
        print(f"   (Crie o novo item em loot_manager.py → ITEM_SCHEMA e LOOT_TABLE)")
    else:
        qty = int(args.qty) if args.qty else 1
        inv = _add_item_to_inv(inv, result["item_name"], qty)
        save_inventory(inv)
        print(f"   Item:      {result['item_name']} × {qty}")
        if result["schema"]:
            print(f"   Tipo:      {result['schema']['type']} ({result['schema']['rarity']})")
            print(f"   Efeito:    {result['schema']['effect']}")
        print(f"\n2. inventory.csv → atualizado")

        # Protocolo de Expansão: d20 >= 17 é Raro/Lendário
        if d20 >= 17:
            print(f"\n⚠ PROTOCOLO DE EXPANSÃO: d20={d20} ≥ 17.")
            print(f"   Verifique se o item '{result['item_name']}' justifica nova entrada no bestiário ou lore.")
    print()

# ── 5.5 ADD ITEM ─────────────────────────────────────────────────────────────

def cmd_add_item(args) -> None:
    cs    = load_json(_CS_PATH)
    inv   = load_inventory()
    turno = _get_current_turn(cs)
    qty   = int(args.qty) if args.qty else 1

    inv = _add_item_to_inv(inv, args.item, qty)
    save_inventory(inv)

    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. ITEM ADICIONADO")
    print(f"   {args.item} × {qty} → inventário")
    print(f"\n2. inventory.csv → atualizado")
    print()

# ── 5.6 REMOVE ITEM ──────────────────────────────────────────────────────────

def cmd_remove_item(args) -> None:
    cs    = load_json(_CS_PATH)
    inv   = load_inventory()
    turno = _get_current_turn(cs)
    qty   = int(args.qty) if args.qty else 1

    try:
        inv = _remove_item_from_inv(inv, args.item, qty)
    except ValueError as e:
        print(f"⚠ ERRO: {e}")
        return

    save_inventory(inv)
    print(f"{'='*55}")
    print(f"  RELATÓRIO DE COMMIT — Turno {turno}")
    print(f"{'='*55}")
    print(f"\n1. ITEM REMOVIDO")
    print(f"   {args.item} × {qty} ← inventário")
    print(f"\n2. inventory.csv → atualizado")
    print()

# ── 5.7 CHECK (alertas) ──────────────────────────────────────────────────────

def cmd_check(args) -> None:
    cs = load_json(_CS_PATH)
    ac = load_json(_AC_PATH)
    print(f"{'='*55}")
    print(f"  VERIFICAÇÃO DE ESTADO")
    print(f"{'='*55}")

    # Vitals
    vitals = cs.get("vitals", {})
    hp     = vitals.get("hp", {})
    o2     = vitals.get("oxygen_level", {})
    en     = vitals.get("energy_reserves", {})
    hull   = vitals.get("hull_integrity", {})
    fuel   = vitals.get("fuel_cells", {})

    def pct(v): return (v.get("current",0) / v.get("max",1)) * 100 if v.get("max",1) > 0 else 0

    print(f"\n── Vitals ──────────────────────────────────────────")
    print(f"  HP:     {hp.get('current','?')}/{hp.get('max','?')}  ({pct(hp):.0f}%)")
    print(f"  O2:     {o2.get('current','?')}%")
    print(f"  Energy: {en.get('current','?')}%")
    print(f"  Hull:   {hull.get('current','?')}%")
    print(f"  Fuel:   {fuel.get('current','?')}/{fuel.get('max','?')}")

    # Progressão
    prog = cs.get("progression", {})
    print(f"\n── Progressão ──────────────────────────────────────")
    print(f"  Nível:  {prog.get('level','?')}  XP: {prog.get('xp_current','?')}/{prog.get('xp_to_next_level','?')}")
    skills = cs.get("passive_skills", [])
    print(f"  Passivas: {skills if skills else 'Nenhuma'}")

    # Status effects
    efx = cs.get("active_status_effects", [])
    if efx:
        print(f"\n── Status Effects (Jogador) ─────────────────────────")
        for e in efx:
            print(f"  [{e['id']}] stacks={e['stacks']} turnos_restantes={e.get('turno_restante','∞')}")

    # Combate ativo
    if ac.get("combate_ativo"):
        inimigo = ac["inimigo"]
        print(f"\n── Combate Ativo ────────────────────────────────────")
        print(f"  Inimigo: {inimigo.get('nome')}  HP: {inimigo.get('hp_atual')}/{inimigo.get('hp_maximo')}")
        print(f"  Posição: {ac['posicionamento']['estado_atual']}")
        hp_pct = (inimigo.get('hp_atual',0) / inimigo.get('hp_maximo',1)) * 100
        threshold = inimigo.get('ficha_racial',{}).get('comportamento','')
        print(f"  HP%: {hp_pct:.0f}%")

    # Skill choice pendente
    if prog.get("skill_choice_pending"):
        nivel   = prog.get("level", 1)
        atribs  = {abbr: cs["attributes"][k]["value"]
                   for abbr, k in _me.ATTRIBUTE_MAP.items()
                   if k in cs["attributes"]}
        available = _me.get_available_passive_skills(nivel, atribs, skills)
        print(f"\n★ SKILL CHOICE PENDENTE — Nível {nivel}")
        print(f"  Habilidades disponíveis:")
        for sk in available:
            print(f"    [{sk['id']}] {sk['nome']} ({sk['categoria']}) — {sk['efeito']['descricao']}")
        print(f"  → Use: python architect.py choose_skill --skill SKILL_ID")

    # ── Verifica level up pendente ────────────────────────────────────────────
    xp_cur   = prog.get("xp_current", 0)
    xp_level = prog.get("level", 1)
    lv_result = _me.check_level_up(xp_cur, xp_level)
    if lv_result["level_up"]:
        new_lv = lv_result["new_level"]
        cs["progression"]["level"]                      = new_lv
        cs["vitals"]["hp"]["max"]                       = lv_result["new_hp_max"]
        cs["vitals"]["hp"]["current"]                   = min(
            cs["vitals"]["hp"].get("current", 0) + 4, lv_result["new_hp_max"])
        cs["progression"]["skill_choice_pending"]       = True
        pts_pending = cs["progression"].get("attribute_points_available", 0)
        cs["progression"]["attribute_points_available"] = pts_pending + lv_result["attr_points"]
        cs["progression"]["xp_to_next_level"]           = lv_result["xp_to_next"]
        save_json(_CS_PATH, cs)
        print(f"\n★ LEVEL UP DETECTADO → Nível {new_lv}!")
        print(f"  attribute_points_available: {pts_pending} + {lv_result['attr_points']} = {pts_pending + lv_result['attr_points']}")
        print(f"  HP máximo: {lv_result['new_hp_max']}  |  skill_choice_pending: true")

    _print_alerts(cs, ac)
    print()

# ── 5.8 LIST SKILLS ──────────────────────────────────────────────────────────

def cmd_list_skills(args) -> None:
    cs    = load_json(_CS_PATH)
    nivel = cs["progression"]["level"]
    atribs = {abbr: cs["attributes"][k]["value"]
              for abbr, k in _me.ATTRIBUTE_MAP.items()
              if k in cs["attributes"]}
    adquiridas = cs.get("passive_skills", [])

    available  = _me.get_available_passive_skills(nivel, atribs, adquiridas)

    print(f"\n── Habilidades Passivas Adquiridas ──────────────────")
    if adquiridas:
        for sid in adquiridas:
            sk = _me.PASSIVE_SKILLS.get(sid, {})
            print(f"  ✓ [{sid}] {sk.get('nome',sid)} ({sk.get('categoria','?')})")
    else:
        print("  Nenhuma.")

    print(f"\n── Habilidades Disponíveis para Aquisição (Nível {nivel}) ─")
    if available:
        for sk in available:
            print(f"  [{sk['id']}] {sk['nome']} ({sk['categoria']})")
            print(f"         {sk['efeito']['descricao']}")
    else:
        print("  Nenhuma disponível agora.")

    print(f"\n── Todas as Habilidades (todas as categorias) ───────")
    categorias: dict[str, list] = {}
    for sid, sk in _me.PASSIVE_SKILLS.items():
        cat = sk.get("categoria", "?")
        categorias.setdefault(cat, []).append((sid, sk))
    for cat, sks in sorted(categorias.items()):
        print(f"\n  {cat}:")
        for sid, sk in sks:
            bloqueada = "✓" if sid in adquiridas else ("→" if sid in [s["id"] for s in available] else "✗")
            print(f"    {bloqueada} [{sid}] {sk['nome']}  (lv{sk['nivel_minimo']})")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 6. ALERTAS
# ─────────────────────────────────────────────────────────────────────────────

def _print_alerts(cs: dict, ac: dict) -> None:
    alerts = []
    vitals = cs.get("vitals", {})

    hp_c  = vitals.get("hp",             {}).get("current", 99)
    hp_m  = vitals.get("hp",             {}).get("max", 20)
    o2    = vitals.get("oxygen_level",   {}).get("current", 100)
    en    = vitals.get("energy_reserves",{}).get("current", 100)
    hull  = vitals.get("hull_integrity", {}).get("current", 100)
    fuel  = vitals.get("fuel_cells",     {}).get("current", 99)

    if hp_c <= 0:                     alerts.append("⛔ HP = 0 — DECEASED")
    elif (hp_c / hp_m) <= 0.25:      alerts.append(f"⚠ HP CRÍTICO: {hp_c}/{hp_m} ({100*hp_c//hp_m}%)")
    elif (hp_c / hp_m) <= 0.50:      alerts.append(f"⚠ HP baixo: {hp_c}/{hp_m}")
    if o2 < 15:                       alerts.append(f"⚠ O2 CRÍTICO: {o2}%")
    if en < 20:                       alerts.append(f"⚠ Energy baixo: {en}%")
    if hull < 20:                     alerts.append(f"⚠ Hull CRÍTICA: {hull}%")
    if fuel <= 0:                     alerts.append(f"⚠ Sem Fuel Cells")
    if cs.get("progression",{}).get("skill_choice_pending"):
        alerts.append("★ SKILL CHOICE PENDENTE — pipeline bloqueado até escolha")

    # Inimigo com moral baixa
    if ac.get("combate_ativo"):
        inn = ac.get("inimigo", {})
        hp_i = inn.get("hp_atual", 99)
        hp_im = inn.get("hp_maximo", 1)
        beh   = inn.get("ficha_racial", {}).get("comportamento","")
        if hp_im > 0 and (hp_i / hp_im) <= 0.30 and "Nunca" not in str(beh):
            alerts.append(f"⚠ {inn['nome']} em threshold de fuga ({100*hp_i//hp_im}% HP)")

    print(f"\n── Alertas ─────────────────────────────────────────")
    if alerts:
        for a in alerts:
            print(f"  {a}")
    else:
        print("  Nenhum.")

# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="architect.py",
        description="Chronos RPG Engine v4 — Guardião do Estado (Python Puro)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start_combat
    p_sc = sub.add_parser("start_combat", help="Inicia combate com inimigo do bestiário")
    p_sc.add_argument("--enemy",    required=True, help="Nome do inimigo (busca tolerante)")
    p_sc.add_argument("--position", default="MELEE",
                      choices=["MELEE","DISTANCIA","COBERTO","FLANQUEANDO"])
    p_sc.add_argument("--weapon",   help="Arma equipada (sobrescreve character_sheet)")

    # apply_loot
    sub.add_parser("apply_loot", help="Adiciona drops do inimigo morto ao inventário")

    # choose_skill
    p_cs = sub.add_parser("choose_skill", help="Aplica escolha de habilidade passiva")
    p_cs.add_argument("--skill", required=True, help="ID da habilidade (ex: pele_grossa)")

    # loot
    p_l = sub.add_parser("loot", help="Resolve loot de exploração via LOOT_TABLE")
    p_l.add_argument("--d20", required=True, help="Valor bruto do d20 (1–20)")
    p_l.add_argument("--qty", default="1",   help="Quantidade (default 1)")

    # add_item
    p_ai = sub.add_parser("add_item", help="Adiciona item ao inventário manualmente")
    p_ai.add_argument("--item", required=True)
    p_ai.add_argument("--qty",  default="1")

    # remove_item
    p_ri = sub.add_parser("remove_item", help="Remove item do inventário manualmente")
    p_ri.add_argument("--item", required=True)
    p_ri.add_argument("--qty",  default="1")

    # check
    sub.add_parser("check", help="Exibe alertas e estado atual detalhado")

    # list_skills
    sub.add_parser("list_skills", help="Lista habilidades passivas adquiridas e disponíveis")

    args = parser.parse_args()

    dispatch = {
        "start_combat": cmd_start_combat,
        "apply_loot":   cmd_apply_loot,
        "choose_skill": cmd_choose_skill,
        "loot":         cmd_loot,
        "add_item":     cmd_add_item,
        "remove_item":  cmd_remove_item,
        "check":        cmd_check,
        "list_skills":  cmd_list_skills,
    }
    dispatch[args.command](args)

if __name__ == "__main__":
    main()