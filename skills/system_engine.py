#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_engine.py — Motor Lógico Autônomo
Chronos RPG Engine v4.0

Substitui o agente System_Engine (IA) por Python puro.
Lê os arquivos de estado, processa a ação, atualiza os JSONs
e imprime o Relatório Técnico — sem nenhuma chamada de IA.

COMANDOS:
  python system_engine.py combat   [--weapon NOME] [--position MELEE|DISTANCIA|COBERTO|FLANQUEANDO]
  python system_engine.py explore  [--dc facil|medio|dificil|impossivel] [--profile A_selva|B_cidade|C_nave]
  python system_engine.py scan     [--dc facil|medio|dificil|impossivel]
  python system_engine.py craft    --recipe CHAVE
  python system_engine.py rest
  python system_engine.py use      --item NOME_EXATO
  python system_engine.py flee
  python system_engine.py status
"""

import sys
import io
import os
import json
import csv
import secrets
import argparse
from typing import Optional

# ── Encoding Windows ──────────────────────────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Caminhos ──────────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_STATE_DIR   = os.path.join(_HERE, "..", "current_state")
_CS_PATH     = os.path.join(_STATE_DIR, "character_sheet.json")
_AC_PATH     = os.path.join(_STATE_DIR, "active_combat.json")
_INV_PATH    = os.path.join(_STATE_DIR, "inventory.csv")
_CT_PATH     = os.path.join(_STATE_DIR, "chapter_tracker.json")

# ── Importa mechanics_engine do mesmo diretório ───────────────────────────────
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("mechanics_engine", os.path.join(_HERE, "mechanics_engine.py"))
_me   = _ilu.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_me)          # type: ignore

# ── Importa multi_roll para delegar multi-roll (U-41) ─────────────────────────
_mr_spec = _ilu.spec_from_file_location("multi_roll", os.path.join(_HERE, "multi_roll.py"))
_mr      = _ilu.module_from_spec(_mr_spec)  # type: ignore
_mr_spec.loader.exec_module(_mr)             # type: ignore

# ── Importa d20 e d4 para rolagens oficiais ───────────────────────────────────
_d20_spec = _ilu.spec_from_file_location("d20", os.path.join(_HERE, "d20.py"))
_d20      = _ilu.module_from_spec(_d20_spec)  # type: ignore
_d20_spec.loader.exec_module(_d20)             # type: ignore

_d4_spec = _ilu.spec_from_file_location("d4", os.path.join(_HERE, "d4.py"))
_d4      = _ilu.module_from_spec(_d4_spec)    # type: ignore
_d4_spec.loader.exec_module(_d4)               # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# 1. SISTEMA MULTI-DADOS — delega a mechanics_engine.ROLL_TABLE
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE COMBATE AVANÇADO
# ─────────────────────────────────────────────────────────────────────────────

# Moral do inimigo: foge quando HP% <= este limiar
MORAL_FLEE_THRESHOLD = 0.30

# Flanqueio: bônus de dano extra além do dano_bonus_melee das passivas
FLANQUEAR_DAMAGE_BONUS = 2

# Multi-ataque: disponível a partir deste nível
MULTI_ATTACK_MIN_LEVEL = 3
# Penalidade de ataque no segundo ataque
MULTI_ATTACK_PENALTY = -4

# ─────────────────────────────────────────────────────────────────────────────
# SISTEMA DE SOBREVIVÊNCIA — Fome / Sede / Exaustão
# ─────────────────────────────────────────────────────────────────────────────

# Decay por turno (pontos perdidos)
_SURVIVAL_DECAY: dict[str, int] = {
    "fome":    3,   # -3/turno  → ~33 turnos até esgotar
    "sede":    5,   # -5/turno  → ~20 turnos até esgotar (mais urgente)
    "exaustao": 2,  # -2/turno  → ~50 turnos até esgotar
}

# Dano de HP quando vital esgotado (aplicado por turno)
_SURVIVAL_DAMAGE: dict[str, int] = {
    "fome":    1,   # fome=0 → -1 HP/turno
    "sede":    2,   # sede=0 → -2 HP/turno (desidratação mata rápido)
    "exaustao": 0,  # exaustao=0 → não causa HP diretamente, mas impõe penalidade
}

# Limiar de perigo (abaixo disso = crítico)
_SURVIVAL_CRIT = 20

# Recuperação no descanso
_REST_RECOVERY: dict[str, int] = {
    "fome":    5,
    "sede":    5,
    "exaustao": 20,
}


def _ensure_survival_vitals(cs: dict) -> None:
    """
    Garante que fome, sede e exaustao existam em cs['vitals'].
    Inicializa com valor máximo se ausentes (retrocompatível).
    """
    v = cs.setdefault("vitals", {})
    for key in ("fome", "sede", "exaustao"):
        if key not in v:
            v[key] = {"current": 100, "max": 100}
        elif not isinstance(v[key], dict):
            v[key] = {"current": int(v[key]), "max": 100}
        # Garante que 'max' existe
        v[key].setdefault("max", 100)
        v[key].setdefault("current", 100)


def _tick_survival(cs: dict, report: list, action: str = "") -> None:
    """
    Aplica decay de fome/sede/exaustão por turno.
    Aplica dano de HP quando algum vital chega a 0.
    Descanso não consome — é tratado em action_rest().
    """
    _ensure_survival_vitals(cs)

    # status e rest não consomem survival (rest recupera)
    if action in ("status",):
        return

    # Exaustão: rest recupera, outros ações custam
    decays = dict(_SURVIVAL_DECAY)
    if action == "rest":
        # Não aplica decay durante descanso — recovery é feito em action_rest
        return

    lines: list[str] = []
    damage_list: list[int] = []

    for key, decay in decays.items():
        v = cs["vitals"][key]
        old = v["current"]
        novo = max(0, old - decay)
        v["current"] = novo

        if old != novo:
            lines.append(f"   {key.upper()}: {old} → {novo} (-{decay})")

        # Dano por esgotamento
        if novo == 0 and _SURVIVAL_DAMAGE.get(key, 0) > 0:
            dmg: int = _SURVIVAL_DAMAGE[key]
            damage_list.append(dmg)
            lines.append(f"   ⚠ {key.upper()} ESGOTADA — -{dmg} HP por turno!")

        # Penalidade de exaustão (aviso narrativo, sem dano direto)
        if key == "exaustao" and novo <= _SURVIVAL_CRIT and novo > 0:
            lines.append(f"   ⚠ EXAUSTÃO CRÍTICA ({novo}%) — penalidade em rolagens!")

    total_dmg = sum(damage_list)
    if total_dmg > 0:
        current_hp = get_vital(cs, "hp")
        set_vital(cs, "hp", current_hp - total_dmg)
        hp_a = get_vital(cs, "hp")
        lines.append(f"   HP: {current_hp} → {hp_a} (-{total_dmg} por esgotamento)")

    if lines:
        report.append("\n0. SOBREVIVÊNCIA (decay por turno)")
        report.extend(lines)


def _roll(faces: int, attr_val: int) -> tuple:
    """Delega multi-rolagem a multi_roll.do_multi_roll (U-41).
    Retorna (lista_brutos, usado, criterio, sufixo_mod)."""
    return _mr.do_multi_roll(faces, attr_val)

def _roll_enemy_d4() -> int:
    """Inimigo sempre 1× d4 — usa _d4.rolar_d4() para rastreamento oficial."""
    return _d4.rolar_d4()

# ─────────────────────────────────────────────────────────────────────────────
# 2. I/O DE ESTADO
# ─────────────────────────────────────────────────────────────────────────────

def load_character_sheet() -> dict:
    with open(_CS_PATH, encoding="utf-8") as f:
        return json.load(f)

def load_active_combat() -> dict:
    with open(_AC_PATH, encoding="utf-8") as f:
        return json.load(f)

def load_inventory() -> list[dict]:
    with open(_INV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def save_character_sheet(cs: dict) -> None:
    with open(_CS_PATH, "w", encoding="utf-8") as f:
        json.dump(cs, f, ensure_ascii=False, indent=2)

def save_active_combat(ac: dict) -> None:
    with open(_AC_PATH, "w", encoding="utf-8") as f:
        json.dump(ac, f, ensure_ascii=False, indent=2)

# Colunas canônicas do inventário — ordem garantida independente do dict
_INV_FIELDNAMES = [
    "id", "name", "type", "rarity", "quantity",
    "weight_kg", "effect", "usable", "durability", "durability_max", "notes",
]

def save_inventory(rows: list[dict]) -> None:
    # Nunca retorna cedo: se o inventário ficou vazio, limpa o CSV corretamente.
    # Usa _INV_FIELDNAMES como fallback para garantir ordem de colunas estável.
    fieldnames = list(rows[0].keys()) if rows else _INV_FIELDNAMES
    with open(_INV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def load_chapter_tracker() -> dict:
    try:
        with open(_CT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_chapter_tracker(ct: dict) -> None:
    with open(_CT_PATH, "w", encoding="utf-8") as f:
        json.dump(ct, f, ensure_ascii=False, indent=4)


# ─────────────────────────────────────────────────────────────────────────────
# 3. HELPERS DE LEITURA DE ESTADO
# ─────────────────────────────────────────────────────────────────────────────

def get_attr(cs: dict, abbr: str) -> int:
    """Retorna valor inteiro do atributo por abreviação (FOR, DES, INT, ...)."""
    key = _me.ATTRIBUTE_MAP.get(abbr)
    if key:
        return cs["attributes"][key]["value"]
    raise ValueError(f"Atributo desconhecido: {abbr}")

def _mod(attr_val: int) -> int:
    """Modificador = Atributo − 10 (regra oficial)."""
    return attr_val - 10

def get_skill_total(cs: dict, skill: str, passive_fx: dict) -> int:
    """Retorna atributo base + bônus de skill + bônus passivo."""
    s    = cs["skills"].get(skill, {})
    attr = get_attr(cs, _me.SKILL_ATTRIBUTE.get(skill, "INT"))
    bonus = s.get("bonus", 0) + passive_fx.get("skill_bonuses", {}).get(skill, 0)
    return attr + bonus

def get_vital(cs: dict, key: str) -> int:
    return cs["vitals"][key]["current"]

def set_vital(cs: dict, key: str, value: int) -> None:
    v = cs["vitals"][key]
    v["current"] = max(0, min(value, v["max"]))

def clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))

def _get_turn(cs: dict) -> int:
    raw = cs["meta"].get("last_updated", "TURNO_0")
    try:
        return int(raw.split("_")[1]) + 1
    except Exception:
        return 1

# ─────────────────────────────────────────────────────────────────────────────
# 4. PROCESSAMENTO DE EFEITOS DE STATUS DO JOGADOR
# ─────────────────────────────────────────────────────────────────────────────

def _apply_player_status(cs: dict, report: list) -> int:
    """Processa status effects do jogador, retorna dano total."""
    efx = cs.get("active_status_effects", [])
    if not efx:
        return 0
    result = _me.process_player_status_effects(efx)
    cs["active_status_effects"] = result["efeitos_atualizados"]
    if result["efeitos_expirados"]:
        report.append(f"  Status expirados: {result['efeitos_expirados']}")
    return result["dano_total"]

# ─────────────────────────────────────────────────────────────────────────────
# 5. AÇÃO: COMBAT
# ─────────────────────────────────────────────────────────────────────────────

def action_combat(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    """
    Combate melhorado com:
      - Iniciativa: quem ataca primeiro determinado por DES vs velocidade do inimigo
      - Moral do inimigo: foge se HP <= 30% do máximo
      - Flanqueio real: +FLANQUEAR_DAMAGE_BONUS de dano direto
      - Multi-ataque: nivel >= MULTI_ATTACK_MIN_LEVEL permite segundo ataque com penalidade
    """
    if not ac.get("combate_ativo"):
        report.append("ERRO: Nenhum combate ativo (active_combat.json → combate_ativo: false).")
        return

    inimigo   = ac["inimigo"]
    posicao   = ac["posicionamento"]["estado_atual"]
    if args.position:
        posicao = args.position.upper()
        ac["posicionamento"]["estado_atual"] = posicao

    weapon_name = args.weapon or ac["jogador"].get("arma_equipada")
    weapon = _me.WEAPON_REGISTRY.get(weapon_name or "") or \
             _me.WEAPON_REGISTRY_FABRICADO.get(weapon_name or "", {})
    weapon_bonus: int = weapon.get("damage_bonus", 0)

    des_val = get_attr(cs, "DES")
    for_val = get_attr(cs, "FOR")
    level   = cs.get("progression", {}).get("level", 1)

    # ── 0. CUSTO DE ENERGIA (SOMENTE COMBATE NAVAL — seção 6) ──
    # Combate pessoal NÃO deduz energia. O custo de −2% é exclusivo do
    # disparo naval (Ship-to-Ship), tratado em action_naval_fire().
    report.append(f"\n1. CUSTO DE ENERGIA")
    report.append(f"   N/A — combate pessoal não consome energia")

    # ── 1. INICIATIVA (multi-roll para jogador, velocidade fixa para inimigo) ──
    ini_rolls, ini_used, ini_crit, _ = _roll(20, des_val)
    ini_player  = ini_used + _mod(des_val)
    ini_enemy   = _d20.rolar_d20() + inimigo.get("velocidade", 0)
    player_first = ini_player >= ini_enemy
    report.append(f"\n2. SCRIPTS")
    report.append(f"   INICIATIVA: Ferro [{ini_player}] vs {inimigo.get('nome','?')} [{ini_enemy}] → {'FERRO ataca PRIMEIRO' if player_first else 'INIMIGO ataca PRIMEIRO'}")

    # ── 2. STATUS EFFECTS DO INIMIGO ──────────────────────────────────────────
    status_result  = _me.process_status_effects(inimigo.get("status_effects", []))
    inimigo["status_effects"] = status_result["efeitos_atualizados"]
    dc_penalty     = status_result["dc_penalty"]
    enemy_stunned  = status_result["enemy_is_stunned"]
    status_dano    = status_result["dano_total"]

    dc_base    = inimigo["dc_defesa"]
    dc_efetiva = max(1, dc_base - dc_penalty)

    attack_bonus = passive_fx.get("ataque_bonus", 0)

    # ── Função interna: executa um único ataque ────────────────────────────────
    def _single_attack(atk_penalty: int = 0) -> tuple[str, int, list, int, str, str]:
        """
        Retorna (outcome, damage_dealt, d20_rolls, d20_used, d20_crit, d20_suf).
        atk_penalty: penalidade de ataque (multi-ataque).
        """
        d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, des_val)
        is_crit   = (d20_used == 20)
        is_fumble = (d20_used == 1)

        total_attack = d20_used + _mod(des_val) + attack_bonus + atk_penalty

        if is_crit:
            out = "SUCESSO CRÍTICO"
        elif is_fumble:
            out = "FALHA CRÍTICA"
        elif total_attack >= dc_efetiva:
            out = "SUCESSO"
        else:
            out = "FALHA"

        dmg = 0
        if out in ("SUCESSO CRÍTICO", "SUCESSO"):
            # d4 de dano: rolagem simples (multi-roll é apenas para d20)
            d4p_used = _d4.rolar_d4()
            base_dmg   = d4p_used * 2 if is_crit else d4p_used
            dano_fixo  = passive_fx.get("dano_bonus_fixo", 0)
            dano_melee = passive_fx.get("dano_bonus_melee", 0) if posicao in ("MELEE","FLANQUEANDO") else 0
            # Flanqueio real: bônus direto de posicionamento
            dano_flank = FLANQUEAR_DAMAGE_BONUS if posicao == "FLANQUEANDO" else 0
            dmg = base_dmg + weapon_bonus + dano_fixo + dano_melee + dano_flank

            if dano_flank:
                report.append(f"   ★ FLANQUEANDO: +{dano_flank} dano de flanqueio")

            # Efeito de arma
            if weapon.get("effect"):
                ef_dc   = weapon.get("effect_dc", 12)
                ef_roll = _d20.rolar_d20()
                if ef_roll >= ef_dc or is_crit:
                    _me.apply_new_effect(inimigo["status_effects"], weapon["effect"])
                    report.append(f"   Efeito aplicado: {weapon['effect']} (roll={ef_roll} vs DC{ef_dc})")

        pen_str = f" (pen {atk_penalty:+})" if atk_penalty else ""
        report.append(f"   D20 {des_val}(mod {_mod(des_val):+}){pen_str}: {d20_rolls} → USADO: {d20_used} ({d20_crit})")
        atk_bonus_str = f"+{attack_bonus}" if attack_bonus > 0 else (f"{attack_bonus}" if attack_bonus else "")
        report.append(f"   Total ataque: {d20_used}+{_mod(des_val)}(DES mod){atk_bonus_str}{pen_str} = {total_attack} vs DC {dc_efetiva} → {out}")
        if dmg:
            report.append(f"   Dano causado: {dmg}")

        return out, dmg, d20_rolls, d20_used, d20_crit, d20_suf

    # ── 3. ATAQUE(S) DO JOGADOR ───────────────────────────────────────────────
    # Jogador SEMPRE ataca. Iniciativa afeta o dano do contra-ataque inimigo:
    # se inimigo venceu, dano dele é multiplicado por 1.5 (atacou em vantagem).
    total_damage_dealt = 0
    first_outcome, first_d20_rolls, first_d20_used, first_d20_crit, first_d20_suf = "", [], 0, "", ""

    out1, dmg1, r1, u1, c1, s1 = _single_attack(0)
    first_outcome    = out1
    first_d20_rolls  = r1
    first_d20_used   = u1
    first_d20_crit   = c1
    first_d20_suf    = s1
    total_damage_dealt += dmg1

    # Multi-ataque (nível >= MULTI_ATTACK_MIN_LEVEL)
    if level >= MULTI_ATTACK_MIN_LEVEL and out1 != "FALHA CRÍTICA":
        report.append(f"   ★ MULTI-ATAQUE (Nível {level}): segundo ataque com {MULTI_ATTACK_PENALTY:+}")
        out2, dmg2, _, _, _, _ = _single_attack(MULTI_ATTACK_PENALTY)
        total_damage_dealt += dmg2

    # Aplica dano ao inimigo (inclui DoT)
    hp_inimigo_antes  = inimigo["hp_atual"]
    inimigo["hp_atual"] = max(0, hp_inimigo_antes - total_damage_dealt - status_dano)
    hp_inimigo_depois = inimigo["hp_atual"]

    report.append(f"\n3. RESULTADO: {first_outcome}")

    # ── 4. MORAL DO INIMIGO ───────────────────────────────────────────────────
    inimigo_fugiu = False
    inimigo_morto = hp_inimigo_depois <= 0

    if not inimigo_morto:
        hp_pct = hp_inimigo_depois / max(1, inimigo["hp_maximo"])
        tem_moral = inimigo.get("ficha_racial", {}).get("pode_fugir", True)
        if hp_pct <= MORAL_FLEE_THRESHOLD and tem_moral:
            roll_moral = _d20.rolar_d20()
            dc_moral   = inimigo.get("ficha_racial", {}).get("dc_moral", 10)
            if roll_moral < dc_moral:
                inimigo_fugiu = True
                report.append(f"   ⚠ MORAL QUEBRADA: {inimigo.get('nome','?')} HP={hp_pct*100:.0f}% ≤ {MORAL_FLEE_THRESHOLD*100:.0f}%")
                report.append(f"   Roll moral: {roll_moral} vs DC {dc_moral} → FUGA DO INIMIGO")
                ac["combate_ativo"] = False
                # XP parcial por fuga — usa tier real do inimigo (igual à morte)
                hp_orig_fuga = inimigo["hp_maximo"]
                xp_ev_fuga = "inimigo_fraco" if hp_orig_fuga <= 10 else ("inimigo_forte" if hp_orig_fuga >= 26 else "inimigo_medio")
                xp_fuga = int(_me.XP_TABLE.get(xp_ev_fuga, 10) * 0.5)
                cs["progression"]["xp_current"] += xp_fuga
                report.append(f"   XP parcial (fuga): +{xp_fuga} [{xp_ev_fuga}]")
            else:
                report.append(f"   Teste moral: {roll_moral} vs DC {dc_moral} → INIMIGO SEGURA (raiva +1)")

    # ── 5. CONTRA-ATAQUE (se inimigo não fugiu, não morreu, não atordoado) ────
    enemy_damage_total = 0
    d4e_raw = 0
    racial  = inimigo.get("damage_bonus_racial", 0)

    if not inimigo_morto and not inimigo_fugiu and not enemy_stunned:
        d4e_raw = _roll_enemy_d4()
        enemy_damage_raw = d4e_raw + racial

        # Redução de armadura e passivas aplicada primeiro
        armor_red   = _me.get_armor_reduction(ac["jogador"].get("armadura_equipada"))
        passive_red = passive_fx.get("dano_reducao_fisica", 0) if inimigo.get("tipo_dano","") == "Físico" else 0
        enemy_damage_total = max(0, enemy_damage_raw - armor_red - passive_red)

        # Se inimigo atacou primeiro (iniciativa), dano FINAL é multiplicado por 1.5
        if not player_first:
            report.append(f"   ⚠ INIMIGO ATACOU PRIMEIRO (iniciativa) — dano ×1.5")
            enemy_damage_total = int(enemy_damage_total * 1.5)

        report.append(f"   D4_ENEMY: [{d4e_raw}] + RACIAL[{racial}] = {enemy_damage_raw}" +
                      (f" −{armor_red+passive_red}(red)" if (armor_red+passive_red) else "") +
                      (f" ×1.5(init)" if not player_first else "") +
                      f" → −{enemy_damage_total} HP jogador")
    else:
        report.append(f"   D4_ENEMY: N/A ({'atordoado' if enemy_stunned else 'morto/fugiu'})")

    # ── 6. APLICA DANO AO JOGADOR ─────────────────────────────────────────────
    hp_before = get_vital(cs, "hp")
    set_vital(cs, "hp", hp_before - enemy_damage_total)
    hp_after  = get_vital(cs, "hp")

    if hp_after <= 0 and passive_fx.get("ultimo_suspiro_disponivel"):
        set_vital(cs, "hp", 1)
        hp_after = 1
        report.append("   ★ ÚLTIMO SUSPIRO ATIVADO — HP ficou em 1")

    report.append(f"\n4. DELTAS — JOGADOR")
    report.append(f"   HP: {hp_before} → {hp_after} ({hp_after-hp_before:+})")

    report.append(f"\n5. DELTAS — INIMIGO ({inimigo['nome']})")
    report.append(f"   HP: {hp_inimigo_antes} → {hp_inimigo_depois} (-{total_damage_dealt + status_dano})")

    if inimigo_morto:
        report.append(f"   Status: MORTO")
        report.append(f"   DROP: {inimigo['ficha_racial'].get('drop', 'nenhum')}")
        ac["combate_ativo"] = False
        hp_orig = inimigo["hp_maximo"]
        xp_ev   = "inimigo_fraco" if hp_orig <= 10 else ("inimigo_forte" if hp_orig >= 26 else "inimigo_medio")
        xp_gain = _me.XP_TABLE.get(xp_ev, 0)
        cs["progression"]["xp_current"] += xp_gain
        lv_result = _me.check_level_up(cs["progression"]["xp_current"], cs["progression"]["level"])
        report.append(f"   XP ganho: +{xp_gain} → total {cs['progression']['xp_current']}")
        if lv_result["level_up"]:
            cs["progression"]["level"]     = lv_result["new_level"]
            cs["vitals"]["hp"]["max"]       = lv_result["new_hp_max"]
            cs["vitals"]["hp"]["current"]   = min(cs["vitals"]["hp"]["current"] + 4, lv_result["new_hp_max"])
            cs["progression"]["skill_choice_pending"] = True
            cs["progression"]["attribute_points_available"] = (
                cs["progression"].get("attribute_points_available", 0) + lv_result["attr_points"]
            )
            cs["progression"]["xp_to_next_level"] = lv_result["xp_to_next"]
            report.append(f"   ★ LEVEL UP → Nível {lv_result['new_level']}! attr_points={lv_result['attr_points']} skill_choice_pending = true")
            available = _me.get_available_passive_skills(
                lv_result["new_level"],
                {abbr: cs["attributes"][k]["value"] for abbr, k in _me.ATTRIBUTE_MAP.items()
                 if k in cs["attributes"]},
                cs.get("passive_skills", []),
            )
            if available:
                report.append("   Habilidades disponíveis para escolha:")
                for sk in available:
                    report.append(f"     [{sk['id']}] {sk['nome']} — {sk['descricao']}")
    elif inimigo_fugiu:
        report.append(f"   Status: FUGIU")
    else:
        report.append(f"   Status: VIVO")

    ac["turno_combate"] = ac.get("turno_combate", 0) + 1

    _print_hud(cs, ac, first_d20_rolls, first_d20_used, first_d20_crit, first_d20_suf, des_val, "DES",
               [], None, None,
               d4e_raw, racial, enemy_damage_total,
               first_d20_used + _mod(des_val) + attack_bonus if first_d20_used else 0,
               dc_efetiva, first_outcome, report)



# ─────────────────────────────────────────────────────────────────────────────
# 6. AÇÃO: EXPLORE
# ─────────────────────────────────────────────────────────────────────────────

def action_explore(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    sob_val = get_attr(cs, "SOB")
    dc      = _me.DC.get(args.dc or "medio", 15)
    profile = args.profile or "A_selva"

    d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, sob_val)
    total = d20_used + _mod(sob_val) + passive_fx.get("skill_bonuses",{}).get("survival", 0)

    if d20_used == 20:    outcome = "SUCESSO CRÍTICO"
    elif d20_used == 1:   outcome = "FALHA CRÍTICA"
    elif total >= dc:     outcome = "SUCESSO"
    else:                 outcome = "FALHA"

    costs = _me.calculate_turn_cost("explorar_area", profile)
    for key, delta in costs.items():
        if key in cs["vitals"] and delta != 0:
            old = get_vital(cs, key)
            set_vital(cs, key, old + delta)

    suf_lbl = f"({d20_suf})" if d20_suf else ""
    report.append(f"\n2. SCRIPTS")
    report.append(f"   D20 {sob_val}{suf_lbl}: {d20_rolls} → USADO: {d20_used} ({d20_crit})")
    report.append(f"   Total: {d20_used} + {_mod(sob_val)}(SOB mod) = {total} vs DC {dc} → {outcome}")
    report.append(f"\n3. RESULTADO: {outcome}")
    report.append(f"\n4. DELTAS — JOGADOR")
    for key, delta in costs.items():
        if key in cs["vitals"] and delta != 0:
            report.append(f"   {key}: {delta:+}")

    _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf, sob_val, "SOB",
               [], None, None, 0, 0, 0, total, dc, outcome, report)

# ─────────────────────────────────────────────────────────────────────────────
# 7. AÇÃO: SCAN
# ─────────────────────────────────────────────────────────────────────────────

def action_scan(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    int_val = get_attr(cs, "INT")
    dc      = _me.DC.get(args.dc or "medio", 15)
    scan_bonus = passive_fx.get("skill_bonuses", {}).get("scan", 0)

    d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, int_val)
    total = d20_used + _mod(int_val) + scan_bonus

    if d20_used == 20:   outcome = "SUCESSO CRÍTICO"
    elif d20_used == 1:  outcome = "FALHA CRÍTICA"
    elif total >= dc:    outcome = "SUCESSO"
    else:                outcome = "FALHA"

    en_before = get_vital(cs, "energy_reserves")
    set_vital(cs, "energy_reserves", en_before - 5)
    en_after  = get_vital(cs, "energy_reserves")

    suf_lbl = f"({d20_suf})" if d20_suf else ""
    report.append(f"\n2. SCRIPTS")
    report.append(f"   D20 {int_val}{suf_lbl}: {d20_rolls} → USADO: {d20_used} ({d20_crit})")
    report.append(f"   Total: {d20_used} + {_mod(int_val)}(INT mod) = {total} vs DC {dc} → {outcome}")
    report.append(f"\n3. RESULTADO: {outcome}")
    report.append(f"\n4. DELTAS — JOGADOR")
    report.append(f"   Energy: {en_before} → {en_after} (-5)")

    _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf, int_val, "INT",
               [], None, None, 0, 0, 0, total, dc, outcome, report)

# ─────────────────────────────────────────────────────────────────────────────
# 8. AÇÃO: CRAFT
# ─────────────────────────────────────────────────────────────────────────────

def action_craft(cs: dict, ac: dict, args, passive_fx: dict,
                 report: list, inv: list) -> list:
    if not args.recipe:
        report.append("ERRO: especifique --recipe CHAVE")
        return inv

    recipe_key = args.recipe
    recipe     = _me.CRAFTING_RECIPES.get(recipe_key)
    if not recipe:
        report.append(f"ERRO: receita '{recipe_key}' não encontrada em mechanics_engine.py")
        report.append(f"  Receitas disponíveis: {list(_me.CRAFTING_RECIPES.keys())}")
        return inv

    inv_dict = {row["name"]: int(row.get("quantity", 0)) for row in inv}
    mat_check = _me.check_crafting_materials(recipe_key, inv_dict)
    if not mat_check["ok"]:
        report.append(f"ERRO: materiais insuficientes. Faltando: {mat_check['missing']}")
        return inv

    outcome = "SUCESSO"  # default para receitas sem teste
    total, dc = 0, 0
    d20_rolls, d20_used, d20_crit, d20_suf = [], 0, "N/A", ""

    if recipe.get("atributo") and recipe.get("dc"):
        int_val = get_attr(cs, "INT")
        dc      = recipe["dc"] - passive_fx.get("crafting_dc_reducao", 0)
        d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, int_val)
        total   = d20_used + _mod(int_val)
        if d20_used == 20:   outcome = "SUCESSO CRÍTICO"
        elif d20_used == 1:
            outcome = "FALHA CRÍTICA"
            salvos  = passive_fx.get("crafting_falha_salvamento", 0)
            if salvos > 0:
                outcome += f" (SALVOU {salvos} MATERIAL)"
        elif total >= dc:    outcome = "SUCESSO"
        else:                outcome = "FALHA"

    report.append(f"\n2. SCRIPTS")
    if d20_rolls:
        suf_lbl = f"({d20_suf})" if d20_suf else ""
        int_val = get_attr(cs, "INT")
        report.append(f"   D20 {int_val}{suf_lbl}: {d20_rolls} → USADO: {d20_used} ({d20_crit})")
        report.append(f"   Total: {d20_used} + {_mod(int_val)}(INT mod) = {total} vs DC {dc} → {outcome}")
    else:
        report.append(f"   Sem teste (receita automática)")
    report.append(f"\n3. RESULTADO: {outcome}")

    if "FALHA" in outcome and "SALVOU" not in outcome:
        # Falha sem salvamento: materiais consumidos, nenhum output
        report.append(f"\n4. DELTAS — Materiais consumidos (falha).")
        for mat, qty in recipe["materiais"].items():
            for row in inv:
                if row["name"] == mat:
                    row["quantity"] = str(max(0, int(row["quantity"]) - qty))
    else:
        # Sucesso ou Falha Crítica com SALVOU (passiva preserva materiais)
        if "SALVOU" in outcome:
            report.append(f"\n4. DELTAS — Materiais preservados (passiva SALVOU ativa).")
        else:
            # Aplica output apenas em sucesso
            if recipe.get("output_json"):
                for key, delta in recipe["output_json"].items():
                    if key in cs["vitals"]:
                        old = get_vital(cs, key)
                        set_vital(cs, key, old + delta)
                        report.append(f"   {key}: +{delta}")
            if recipe.get("output_csv"):
                item = recipe["output_csv"]
                inv.append({
                    "id":            str(len(inv) + 1),
                    "name":          item["name"],
                    "type":          item["type"],
                    "rarity":        item["rarity"],
                    "quantity":      str(item["quantity"]),
                    "weight_kg":     str(item["weight_kg"]),
                    "effect":        item["effect"],
                    "usable":        str(item["usable"]).lower(),
                    # durability/durability_max OBRIGATÓRIOS: se omitidos e este item
                    # for rows[0], save_inventory usará rows[0].keys() como fieldnames
                    # e apagará essas colunas do CSV inteiro (todos os itens perdem durabilidade).
                    "durability":     str(item["durability"]) if item.get("durability") not in (None, "") else "",
                    "durability_max": str(item["durability_max"]) if item.get("durability_max") not in (None, "") else "",
                    "notes":         item.get("notes",""),
                })
                report.append(f"   Item adicionado ao inventário: {item['name']}")
            # Consome materiais apenas em sucesso
            for mat, qty in recipe["materiais"].items():
                for row in inv:
                    if row["name"] == mat:
                        row["quantity"] = str(max(0, int(row["quantity"]) - qty))

    _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf,
               get_attr(cs,"INT"), "INT", [], None, None,
               0, 0, 0, total, dc, outcome, report)
    return inv

# ─────────────────────────────────────────────────────────────────────────────
# 9. AÇÃO: REST
# ─────────────────────────────────────────────────────────────────────────────

def action_rest(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    _ensure_survival_vitals(cs)
    mult  = passive_fx.get("cura_repouso_mult", 1)  # recuperacao_acelerada
    cura  = 2 * mult
    hp_b  = get_vital(cs, "hp")
    set_vital(cs, "hp", hp_b + int(cura))
    hp_a  = get_vital(cs, "hp")

    report.append(f"\n2. SCRIPTS: sem rolagem (descanso)")
    report.append(f"\n3. RESULTADO: DESCANSO")
    report.append(f"\n4. DELTAS — JOGADOR")
    report.append(f"   HP: {hp_b} → {hp_a} (+{int(cura)})")

    # Recuperação de sobrevivência durante descanso
    surv_lines = []
    for key, rec in _REST_RECOVERY.items():
        v = cs["vitals"][key]
        old = v["current"]
        novo = min(v["max"], old + rec)
        v["current"] = novo
        if old != novo:
            surv_lines.append(f"   {key.upper()}: {old} → {novo} (+{rec})")
    if surv_lines:
        report.append("   --- Recuperação de sobrevivência ---")
        report.extend(surv_lines)

    _print_hud(cs, ac, [], 0, "N/A", "", 0, "", [], None, None,
               0, 0, 0, 0, 0, "DESCANSO", report)

# ─────────────────────────────────────────────────────────────────────────────
# 10. AÇÃO: USE ITEM
# ─────────────────────────────────────────────────────────────────────────────

def action_use(cs: dict, ac: dict, args, passive_fx: dict,
               report: list, inv: list) -> list:
    if not args.item:
        report.append("ERRO: especifique --item NOME_EXATO")
        return inv

    target = args.item
    found_idx = -1
    for i, row in enumerate(inv):
        name_val = row.get("name")
        if isinstance(name_val, str) and name_val.lower() == target.lower() and str(row.get("usable","false")).lower() == "true":
            if int(row.get("quantity",0)) > 0:
                found_idx = i
                break

    if found_idx == -1:
        report.append(f"ERRO: item '{target}' não encontrado, não usável ou quantidade = 0.")
        return inv

    found_item = inv[found_idx]
    effect     = str(found_item.get("effect", ""))
    item_type  = str(found_item.get("type", "")).strip()
    item_name  = found_item.get("name", target)

    report.append(f"\n2. SCRIPTS: sem rolagem (uso de item)")
    report.append(f"\n3. RESULTADO: Item usado — {item_name} (tipo: {item_type or 'desconhecido'})")
    report.append(f"\n4. DELTAS — JOGADOR")

    # Parse de efeito simples "+X HP", "+X Energy", "+X O2", "+X Fome", "+X Sede", "+X Exaustao"
    _ensure_survival_vitals(cs)
    import re
    for pat, key_map in [
        (r"\+(\d+)\s*HP",       "hp"),
        (r"\+(\d+)\s*Energy",   "energy_reserves"),
        (r"\+(\d+)\s*O2",       "oxygen_level"),
        (r"\+(\d+)\s*Fome",     "fome"),
        (r"\+(\d+)\s*Sede",     "sede"),
        (r"\+(\d+)\s*Exaustao", "exaustao"),
    ]:
        m = re.search(pat, effect, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            old = get_vital(cs, key_map)
            set_vital(cs, key_map, old + val)
            new = get_vital(cs, key_map)
            report.append(f"   {key_map}: {old} → {new} (+{val})")

    # ── LÓGICA DE CONSUMO POR TIPO ─────────────────────────────────────────
    # Consumível / Recurso → diminui quantity (desaparece ao chegar em 0)
    # Arma / Armadura / Equipamento Passivo → diminui durability, NÃO quantity
    # Material / Quest → não consome (apenas aplica efeito)
    _CONSUMIVEIS = {"consumível", "consumivel", "recurso"}
    _COM_DURABILIDADE = {"arma", "armadura", "equipamento passivo"}
    _type_lower = item_type.lower()

    if _type_lower in _CONSUMIVEIS:
        found_item["quantity"] = str(max(0, int(found_item.get("quantity", 1)) - 1))
        report.append(f"   quantity: {int(found_item['quantity'])+1} → {found_item['quantity']} (consumido)")

    elif _type_lower in _COM_DURABILIDADE:
        dur_raw = found_item.get("durability", "")
        dur_str = str(dur_raw) if dur_raw not in ("", "null", "None", None) else ""
        if dur_str:
            try:
                dur_old = int(dur_str)
                dur_new = max(0, dur_old - 1)
                found_item["durability"] = str(dur_new)
                report.append(f"   durability: {dur_old} → {dur_new}")
                if dur_new == 0:
                    report.append(f"   ⚠ AVISO: {item_name} com durabilidade 0 — precisa de reparo!")
            except ValueError:
                report.append(f"   durability inalterada (valor não numérico: '{dur_str}')")
        else:
            report.append(f"   quantity inalterada (arma/armadura sem campo durability)")

    else:
        # Material, Quest, tipo desconhecido — só aplica efeito, não consome
        report.append(f"   quantity inalterada (tipo '{item_type}' não é consumível)")

    _print_hud(cs, ac, [], 0, "N/A", "", 0, "", [], None, None,
               0, 0, 0, 0, 0, "ITEM_USADO", report)
    return inv

# ─────────────────────────────────────────────────────────────────────────────
# 11. AÇÃO: FLEE
# ─────────────────────────────────────────────────────────────────────────────

def action_flee(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    if not ac.get("combate_ativo"):
        report.append("ERRO: Nenhum combate ativo.")
        return

    des_val = get_attr(cs, "DES")
    dc      = 15  # fuga padrão DC Médio
    d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, des_val)
    total   = d20_used + _mod(des_val) + passive_fx.get("skill_bonuses",{}).get("stealth",0)

    if d20_used == 20:   outcome = "SUCESSO CRÍTICO"
    elif d20_used == 1:  outcome = "FALHA CRÍTICA"
    elif total >= dc:    outcome = "SUCESSO"
    else:                outcome = "FALHA"

    suf_lbl = f"({d20_suf})" if d20_suf else ""
    report.append(f"\n2. SCRIPTS")
    report.append(f"   D20 {des_val}{suf_lbl}: {d20_rolls} → USADO: {d20_used} ({d20_crit})")
    report.append(f"   Total: {d20_used} + {_mod(des_val)}(DES mod) = {total} vs DC {dc} → {outcome}")
    report.append(f"\n3. RESULTADO: {outcome}")

    if "SUCESSO" in outcome:
        ac["combate_ativo"] = False
        report.append("   Fuga bem-sucedida. combate_ativo → false")
        report.append("   NOTA: Nenhum drop. Inimigo permanece vivo.")
    else:
        # Inimigo acerta durante fuga
        inimigo = ac["inimigo"]
        d4e = _roll_enemy_d4()
        racial = inimigo.get("damage_bonus_racial", 0)
        dano   = max(0, d4e + racial - _me.get_armor_reduction(ac["jogador"].get("armadura_equipada")))
        hp_b   = get_vital(cs, "hp")
        set_vital(cs, "hp", hp_b - dano)
        hp_a   = get_vital(cs, "hp")
        report.append(f"   Fuga falhou. Inimigo golpeia: D4[{d4e}]+{racial}={d4e+racial} → -{dano} HP")
        report.append(f"\n4. DELTAS — JOGADOR")
        report.append(f"   HP: {hp_b} → {hp_a} (-{dano})")

    _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf, des_val, "DES",
               [], None, None, 0, 0, 0, total, dc, outcome, report)

# ─────────────────────────────────────────────────────────────────────────────
# 12. AÇÃO: STATUS (somente leitura)
# ─────────────────────────────────────────────────────────────────────────────

def action_status(cs: dict, ac: dict, report: list) -> None:
    report.append("")
    report.append("=== ESTADO ATUAL ===")
    _print_hud(cs, ac, [], None, "", "", None, "", [], None, None,
               0, 0, 0, None, None, "—", report)

# ─────────────────────────────────────────────────────────────────────────────
# 13. HUD
# ─────────────────────────────────────────────────────────────────────────────

def _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf, attr_val, attr_nm,
               d4p_rolls, d4p_used, d4p_crit,
               d4e_raw, racial, enemy_dmg,
               total_attack, dc, outcome, report):

    hp  = get_vital(cs, "hp"); hp_max = cs["vitals"]["hp"]["max"]
    o2  = get_vital(cs, "oxygen_level")
    en  = get_vital(cs, "energy_reserves")
    _ensure_survival_vitals(cs)
    fome    = cs["vitals"]["fome"]["current"]
    sede    = cs["vitals"]["sede"]["current"]
    exaustao = cs["vitals"]["exaustao"]["current"]
    xp  = cs["progression"]["xp_current"]
    xp2 = cs["progression"]["xp_to_next_level"]
    lv  = cs["progression"]["level"]
    status = _me.evaluate_status(cs)

    inimigo = ac.get("inimigo", {}) if ac.get("combate_ativo") else {}
    i_nome  = inimigo.get("nome", "—") if inimigo else "—"
    i_hp    = f"{inimigo.get('hp_atual','?')} / {inimigo.get('hp_maximo','?')}" if inimigo else "—"

    suf_lbl = f"({d20_suf})" if d20_suf else ""
    d20_str = f"{d20_rolls} → USADO: {d20_used} ({d20_crit})" if d20_rolls else "—"
    d4p_str = f"{d4p_rolls} → USADO: {d4p_used} ({d4p_crit})" if d4p_rolls else "N/A"
    d4e_str = f"[{d4e_raw}] + RACIAL[{racial}] → -{enemy_dmg} HP" if d4e_raw else "N/A"
    dado_d20_str = (f"{d20_used} + {_mod(attr_val)}({attr_nm} mod{suf_lbl}) = {total_attack} vs DC {dc} → {outcome}"
                    if d20_used and attr_val is not None else "—")

    cs["identity"]["status"] = status
    cs["meta"]["last_updated"] = f"TURNO_{_get_turn(cs)}"

    report.append(f"""
6. HUD
┌─────────────────────────────────────────────────────┐
│ HP {hp:>3}/{hp_max:<3}  O2 {o2:>3}%  EN {en:>3}%  Nv {lv}
│ XP {xp}/{xp2}
│ FOME {fome:>3}%  SEDE {sede:>3}%  EXAUSTÃO {exaustao:>3}%
│ INIMIGO: {i_nome:<20} HP {i_hp}
├─────────────────────────────────────────────────────┤
│ D20_ROLLS : {d20_str}
│ DADO_D20  : {dado_d20_str}
│ D4_PLAYER : {d4p_str}
│ D4_ENEMY  : {d4e_str}
└─────────────────────────────────────────────────────┘
7. STATUS FINAL: {status}""")

# ─────────────────────────────────────────────────────────────────────────────
# 13B. AÇÃO: NAVAL
# ─────────────────────────────────────────────────────────────────────────────

def action_naval_fire(cs: dict, ac: dict, args, passive_fx: dict, report: list) -> None:
    if not ac.get("combate_ativo"):
        report.append("ERRO: Nenhum combate ativo (active_combat.json → combate_ativo: false).")
        return

    inimigo = ac["inimigo"]

    # 1. Custo de Energy: -2%
    en_before = get_vital(cs, "energy_reserves")
    if en_before < 2:
        report.append("ERRO: Sem energia suficiente para disparo naval (Energy < 2%).")
        return
    set_vital(cs, "energy_reserves", en_before - 2)
    report.append(f"\n1. NAVAL FIRE: Energy -2% (Atual: {en_before-2}%)")

    # 2. Rolar DES contra AC
    des_val = get_attr(cs, "DES")
    dc = inimigo.get("ac", 15)  # AC da nave inimiga

    d20_rolls, d20_used, d20_crit, d20_suf = _roll(20, des_val)
    total = d20_used + _mod(des_val) + passive_fx.get("ataque_naval_bonus", 0)

    sucesso = (total >= dc) or (d20_used == 20)
    falha_critica = (d20_used == 1)

    suf_lbl = f"({d20_suf})" if d20_suf else ""
    report.append(f"   D20 DES{suf_lbl}: {d20_rolls} → USADO: {d20_used}")
    report.append(f"   Ataque: {d20_used} + {_mod(des_val)}(DES mod) = {total} vs AC {dc}")

    if falha_critica or not sucesso:
        outcome = "FALHA"
        report.append("   Resultado: FALHA (sem dano)")
    else:
        outcome = "SUCESSO"
        escudos = inimigo.get("escudos_atuais", 0)
        hp = inimigo.get("hp_atual", 10)
        if escudos > 0:
            dano = 15
            novo_escudo = max(0, escudos - dano)
            inimigo["escudos_atuais"] = novo_escudo
            report.append(f"   Resultado: SUCESSO (15 dano nos escudos → {escudos} para {novo_escudo})")
        else:
            dano = 10
            novo_hp = max(0, hp - dano)
            inimigo["hp_atual"] = novo_hp
            report.append(f"   Resultado: SUCESSO (10 dano no casco → {hp} para {novo_hp})")

            if novo_hp <= 0:
                report.append("   Inimigo DESTRUÍDO!")
                ac["combate_ativo"] = False

    ac["turno_combate"] = ac.get("turno_combate", 0) + 1

    _print_hud(cs, ac, d20_rolls, d20_used, d20_crit, d20_suf, des_val, "DES", [], None, None, 0, 0, 0, total, dc, outcome, report)

# ─────────────────────────────────────────────────────────────────────────────
# 14. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="system_engine.py",
        description="Chronos RPG Engine v4 — Motor Lógico Python Puro",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    # combat
    p_c = sub.add_parser("combat", help="Atacar inimigo ativo")
    p_c.add_argument("--weapon",   help="Nome exato da arma (ex: 'Faca Improvisada')")
    p_c.add_argument("--position", choices=["MELEE","DISTANCIA","COBERTO","FLANQUEANDO"],
                     help="Sobrescreve posicionamento atual")

    # naval
    sub.add_parser("naval", help="Combate ship-to-ship (disparo naval)")

    # explore
    p_e = sub.add_parser("explore", help="Explorar área")
    p_e.add_argument("--dc",      default="medio",   choices=["facil","medio","dificil","impossivel"])
    p_e.add_argument("--profile", default="A_selva", help="Perfil de ambiente")

    # scan
    p_s = sub.add_parser("scan", help="Scan / Análise")
    p_s.add_argument("--dc", default="medio", choices=["facil","medio","dificil","impossivel"])

    # craft
    p_f = sub.add_parser("craft", help="Fabricar item")
    p_f.add_argument("--recipe", required=True, help="Chave da receita em mechanics_engine.py")

    # rest
    sub.add_parser("rest", help="Descansar (+2 HP, sem custo)")

    # use
    p_u = sub.add_parser("use", help="Usar item do inventário")
    p_u.add_argument("--item", required=True, help="Nome exato do item")

    # flee
    sub.add_parser("flee", help="Tentar fugir do combate")

    # status
    sub.add_parser("status", help="Exibir estado atual sem processar turno")

    args = parser.parse_args()

    # ── Carrega estado ────────────────────────────────────────────────────────
    cs  = load_character_sheet()
    ac  = load_active_combat()
    inv = load_inventory()

    # ── Passive skills ────────────────────────────────────────────────────────
    passive_ids = cs.get("passive_skills", [])
    hp_pct      = (get_vital(cs,"hp") / cs["vitals"]["hp"]["max"]) if cs["vitals"]["hp"]["max"] > 0 else 1.0
    context     = {
        "hp_atual":   get_vital(cs, "hp"),
        "hp_maximo":  cs["vitals"]["hp"]["max"],
        "posicao":    ac["posicionamento"]["estado_atual"] if ac.get("combate_ativo") else "MELEE",
        "tipo_dano":  ac["inimigo"].get("tipo_dano","Físico") if ac.get("combate_ativo") else "Físico",
    }
    passive_fx = _me.apply_passive_skill_effects(passive_ids, context)

    # ── Relatório ─────────────────────────────────────────────────────────────
    report = []
    turno  = _get_turn(cs)
    report.append(f"{'='*55}")
    report.append(f"  RELATÓRIO TÉCNICO — Turno {turno}")
    report.append(f"{'='*55}")

    # ── Status effects do jogador (antes de qualquer ação) ────────────────────
    status_dano = _apply_player_status(cs, report)
    if status_dano > 0:
        hp_b = get_vital(cs, "hp")
        set_vital(cs, "hp", hp_b - status_dano)
        report.append(f"  EFEITOS_JOGADOR: -{status_dano} HP por status effects")

    # ── Decay de sobrevivência (fome/sede/exaustão) ───────────────────────────
    if args.action != "status":
        _tick_survival(cs, report, args.action)

    # ── Parsing ───────────────────────────────────────────────────────────────
    action_map = {
        "combat":  "Combate",
        "naval":   "Combate Naval",
        "explore": "Exploração",
        "scan":    "Scan/Análise",
        "craft":   "Crafting",
        "rest":    "Descanso",
        "use":     "Uso de Item",
        "flee":    "Fuga",
        "status":  "Status",
    }
    report.append(f"\n1. AÇÃO: {action_map.get(args.action,'?')}")
    if passive_ids:
        report.append(f"   Passivas ativas: {passive_ids}")

    # ── Despacha ação ─────────────────────────────────────────────────────────
    if   args.action == "combat":  action_combat(cs, ac, args, passive_fx, report)
    elif args.action == "naval":   action_naval_fire(cs, ac, args, passive_fx, report)
    elif args.action == "explore": action_explore(cs, ac, args, passive_fx, report)
    elif args.action == "scan":    action_scan(cs, ac, args, passive_fx, report)
    elif args.action == "craft":   inv = action_craft(cs, ac, args, passive_fx, report, inv)
    elif args.action == "rest":    action_rest(cs, ac, args, passive_fx, report)
    elif args.action == "use":     inv = action_use(cs, ac, args, passive_fx, report, inv)
    elif args.action == "flee":    action_flee(cs, ac, args, passive_fx, report)
    elif args.action == "status":  action_status(cs, ac, report)

    # ── Salva estado (exceto status que é read-only) ──────────────────────────
    if args.action != "status":
        save_character_sheet(cs)
        save_active_combat(ac)
        if args.action in ("craft","use"):
            save_inventory(inv)
        # Incrementa contador de interações no capítulo
        ct = load_chapter_tracker()
        if ct:
            contagem = ct.setdefault("contagem", {})
            contagem["interacoes_no_capitulo"] = contagem.get("interacoes_no_capitulo", 0) + 1
            inter = contagem["interacoes_no_capitulo"]
            maximo = contagem.get("maximo_obrigatorio", 25)
            if inter >= 15:
                ct["contagem"]["alerta_final_ativado"] = True
            ct["meta"]["last_updated"] = f"TURNO_{inter}"
            save_chapter_tracker(ct)
            report.append(f"5. CAPITULO: interacoes = {inter}/{maximo}{chr(32) + chr(91) + chr(65) + chr(76) + chr(69) + chr(82) + chr(84) + chr(65) + chr(93) if inter >= 15 else chr(32) + chr(111) + chr(107)}")

    # ── Salva e imprime relatório ──────────────────────────────────────────────
    report_text = "\n".join(report)
    try:
        _draft_dir = os.path.join(_HERE, "..", "drafts")
        os.makedirs(_draft_dir, exist_ok=True)
        with open(os.path.join(_draft_dir, "technical_report.txt"), "w", encoding="utf-8") as _rf:
            _rf.write(report_text)
    except Exception:
        pass
    print(report_text)
    print()

if __name__ == "__main__":
    main()