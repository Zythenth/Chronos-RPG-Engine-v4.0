"""
mechanics_engine.py
Chronos RPG Engine v3.1

Motor de regras central. Usado pelo System_Engine (Passo 1) e pelo Architect (Passo 2).
Contém: custos de ação, DCs, cálculos de combate, progressão de XP e level,
resolução de crafting e avaliação de status.

REGRA DE OURO (Architect): NUNCA altere entradas existentes.
Novas entradas são adicionadas APENAS ao final de cada dicionário/lista.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 0. INTEGRAÇÃO COM OS DADOS — roll_d20() e roll_d4()
#
# Os scripts d20.py e d4.py ficam na mesma pasta (skills/).
# Usamos importlib para carregá-los pelo caminho absoluto — funciona em qualquer
# sistema operacional e independente do diretório de trabalho atual.
#
# REGRA do pipeline: SEMPRE use roll_d20() / roll_d4() daqui.
# NUNCA gere o número manualmente nem substitua por valor fixo.
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util
import os as _os
from typing import Optional, Any

def _load_dice(filename: str) -> Any:
    """Carrega um módulo de dado pelo caminho relativo a este arquivo."""
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    mod  = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    return mod

_d20 = _load_dice("d20.py")
_d4  = _load_dice("d4.py")

# Resultado das últimas rolagens do turno — lido pelo System_Engine ao montar o log
last_roll: dict = {
    "d20": None,   # int — resultado bruto do último d20 rodado
    "d4":  None,   # int — resultado bruto do último d4 rodado (None se não usado)
}

def roll_d20() -> int:
    """
    Chama rolar_d20() do script d20.py, salva em last_roll['d20'] e retorna o inteiro.
    Único ponto de entrada autorizado para testes de habilidade no pipeline.
    """
    value: int = _d20.rolar_d20()
    last_roll["d20"] = value
    return value

def roll_d4() -> int:
    """
    Chama rolar_d4() do script d4.py, salva em last_roll['d4'] e retorna o inteiro.
    Usado apenas quando há evento de dano confirmado (combate).
    """
    value: int = _d4.rolar_d4()
    last_roll["d4"] = value
    return value

def get_last_rolls() -> dict:
    """
    Retorna os resultados das últimas rolagens do turno.
    Chamado pelo System_Engine ao montar o LOG_MECANICO_V1.md.
    """
    return dict(last_roll)

def reset_rolls() -> None:
    """Zera os resultados antes de iniciar um novo turno."""
    last_roll["d20"] = None
    last_roll["d4"]  = None


# ─────────────────────────────────────────────────────────────────────────────
# 0B. TABELA DE MULTI-ROLL (fonte única de verdade — mecanicas-oficiais.md §2)
#     Formato: atributo_bruto → (qtd_rolagens, critério)
# ─────────────────────────────────────────────────────────────────────────────

ROLL_TABLE = {
     1: (5, "PIOR"),
     2: (4, "PIOR"),   3: (4, "PIOR"),
     4: (3, "PIOR"),   5: (3, "PIOR"),
     6: (2, "PIOR"),   7: (2, "PIOR"),
     8: (1, "ÚNICO"),  9: (1, "ÚNICO"),
    10: (2, "MELHOR"), 11: (2, "MELHOR"),
    12: (3, "MELHOR"), 13: (3, "MELHOR"),
    14: (4, "MELHOR"), 15: (4, "MELHOR"),
    16: (5, "MELHOR"), 17: (5, "MELHOR"),
    18: (6, "MELHOR"), 19: (6, "MELHOR"),
    20: (7, "MELHOR"),
}

def calc_modifier(attr_value: int) -> int:
    """Modificador de atributo = atributo − 10 (regra oficial, §1)."""
    return attr_value - 10

# ─────────────────────────────────────────────────────────────────────────────
# 1. ATRIBUTOS — mapeamento abbr → chave no character_sheet.json
# ─────────────────────────────────────────────────────────────────────────────

ATTRIBUTE_MAP = {
    "FOR": "forca",
    "DES": "destreza",
    "INT": "inteligencia",
    "SOB": "sobrevivencia",
    "PER": "percepcao",
    "CAR": "carisma",
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. SKILLS — qual atributo governa cada skill
# ─────────────────────────────────────────────────────────────────────────────

SKILL_ATTRIBUTE = {
    "combat":        "DES",
    "engineering":   "INT",
    "piloting":      "DES",
    "survival":      "SOB",
    "stealth":       "DES",
    "chip_interface":"INT",
    "social":        "CAR",
    "scan":          "INT",
    "medicine":      "INT",
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. DCs PADRÃO
# Fácil=10 | Médio=15 | Difícil=20 | Impossível=25
# ─────────────────────────────────────────────────────────────────────────────

DC = {
    "facil":       10,
    "medio":       15,
    "dificil":     20,
    "impossivel":  25,
}

DCS = DC

# ─────────────────────────────────────────────────────────────────────────────
# 4. CUSTO BASAL POR TURNO (deduzido ANTES de qualquer ação)
# Chaves: environment_profile → dict de deltas de recursos
# Valores negativos = consumo; positivos = ganho
# ─────────────────────────────────────────────────────────────────────────────

BASAL_COST = {
    "A_selva": {
        "energy_reserves": -2,
        "oxygen_level":     0,    # ar livre, sem custo
        "hp_passive":       0,    # -1 HP se sem abrigo à noite (condicional — System_Engine avalia)
    },
    "B_cidade": {
        "energy_reserves": -1,
        "oxygen_level":     0,    # ar disponível
        "hp_passive":       0,    # -2 HP em zonas de gás sem máscara (condicional)
    },
    "C_nave": {
        "energy_reserves": -1,
        "oxygen_level":    -1,
    },
    "D_eva": {
        "oxygen_level":    -5,
        "energy_reserves": -2,
    },
    "E_planeta": {
        "energy_reserves": -2,   # base; custo extra depende do planeta (PLANET_EXTRA_COST)
    },
}

# Custos extras por planeta (somados ao Perfil E)
PLANET_EXTRA_COST = {
    # caps 26-28
    "mundo_corrosivo":    {"suit_integrity": -2},          # sem blindagem ácida
    # caps 29-31
    "abismo_oceanico":    {"hull_integrity": -3},           # abaixo de 500m
    # caps 32-34
    "deserto_de_vidro":   {},                               # sem basal; risco situacional
    # caps 35-37
    "cemiterio_silicio":  {},                               # sem basal; risco situacional
    # caps 38-40
    "gigante_gasoso":     {"fuel_cells": -1},               # navegação nos furacões
    # caps 41-43
    "mundo_simbiotico":   {"hp_passive": -2},               # sem máscara de filtragem
    # caps 44-46
    "orbe_estilhacado":   {},                               # usa Perfil D durante EVA
    # caps 47-49
    "mundo_orfao":        {"hp_passive": -3},               # sem fonte de calor
    # caps 50-52
    "horizonte_eventos":  {"energy_reserves": -1},          # dilatação gravitacional extra
    # caps 53-55
    "paraiso_artificial": {"suit_integrity": -5, "hp_passive": -1},  # assimilação
}

def get_basal_cost(profile: str, planet: Optional[str] = None) -> dict:
    """
    Retorna os deltas de custo basal para o ambiente atual.
    profile: "A_selva" | "B_cidade" | "C_nave" | "D_eva" | "E_planeta"
    planet:  chave de PLANET_EXTRA_COST (só relevante se profile == "E_planeta")
    """
    cost = dict(BASAL_COST.get(profile, {}))
    if profile == "E_planeta" and planet:
        extra = PLANET_EXTRA_COST.get(planet, {})
        for key, val in extra.items():
            cost[key] = cost.get(key, 0) + val
    return cost


# ─────────────────────────────────────────────────────────────────────────────
# 5. CUSTOS DE AÇÃO (deduzidos ALÉM do custo basal)
# ─────────────────────────────────────────────────────────────────────────────

ACTION_COST = {
    # Ações universais
    "explorar_area":      {"energy_reserves": -3},
    "usar_chip":          {"energy_reserves": -5},
    "scan":               {"energy_reserves": -5},
    "primeiros_socorros": {},              # custo = item consumível (verificar inventário)
    "combate":            {},              # custo = HP recebido (calculado em resolve_combat)

    # Ações de nave
    "scan_setor":         {"energy_reserves": -5},
    "salto_decolagem":    {"fuel_cells": -1},
    "pouso_atmosferico":  {"fuel_cells": -2},
    "recarregar_sistemas":{"energy_reserves": -10},
    "ataque_canhao":      {"energy_reserves": -2},   # Ship-to-Ship
}

def calculate_turn_cost(action: str, profile: str, planet: Optional[str] = None) -> dict:
    """
    Combina custo basal + custo de ação em um único dicionário de deltas.
    Chamado pelo System_Engine ANTES de qualquer rolagem.

    action:  chave de ACTION_COST
    profile: chave de BASAL_COST
    planet:  chave de PLANET_EXTRA_COST (se profile == "E_planeta")

    Retorna dict com deltas acumulados (valores negativos = consumo).
    """
    basal = get_basal_cost(profile, planet)
    action_delta = dict(ACTION_COST.get(action, {}))

    combined = dict(basal)
    for key, val in action_delta.items():
        combined[key] = combined.get(key, 0) + val

    return combined


# ─────────────────────────────────────────────────────────────────────────────
# 6. RESOLUÇÃO DE TESTE (executa d20.py + modificador vs DC)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_check(modifier: int, dc: int) -> dict:
    """
    Executa roll_d20() internamente, aplica o modificador e classifica o resultado.
    Não recebe d20_result como parâmetro — o dado é sempre rolado aqui.

    Retorna dict com:
      d20_raw:  int — valor bruto saído de rolar_d20() (salvo em last_roll)
      total:    int — d20_raw + modifier
      dc:       int — DC usada
      result:   str — "SUCESSO_CRITICO" | "SUCESSO" | "FALHA" | "FALHA_CRITICA"
    """
    d20_raw = roll_d20()   # chama rolar_d20() e persiste em last_roll["d20"]
    total   = d20_raw + modifier

    if d20_raw == 20:
        outcome = "SUCESSO_CRITICO"
    elif d20_raw == 1:
        outcome = "FALHA_CRITICA"
    elif total >= dc:
        outcome = "SUCESSO"
    else:
        outcome = "FALHA"

    return {"d20_raw": d20_raw, "total": total, "dc": dc, "result": outcome}


# ─────────────────────────────────────────────────────────────────────────────
# 7. RESOLUÇÃO DE COMBATE PESSOAL
# ─────────────────────────────────────────────────────────────────────────────

ARMOR_DAMAGE_REDUCTION = 2   # redução fixa quando item "Armadura" está no inventário

def resolve_personal_combat(
    player_attr: int,
    enemy_dc: int,
    enemy_damage: int,
    armor_name: Optional[str] = None,
    weapon_name: Optional[str] = None,
    enemy_is_stunned: bool = False,
) -> dict:
    """
    Executa roll_d20() (teste de ataque) e roll_d4() (dano) internamente.

    Parâmetros:
      armor_name:       str|None — nome da armadura equipada (consulta ARMOR_REGISTRY)
      weapon_name:      str|None — nome da arma equipada (consulta WEAPON_REGISTRY + WEAPON_REGISTRY_FABRICADO)
      enemy_is_stunned: bool     — True quando inimigo tem efeito skip_ataque ativo

    Retorna dict com:
      d20_raw, total_attack, check_result, is_critical,
      d4_raw, weapon_bonus, damage_dealt,
      damage_reduction, damage_taken,
      effect_applied: str|None
    """
    check       = resolve_check(player_attr, enemy_dc)
    d20_raw     = check["d20_raw"]
    is_critical = (d20_raw == 20)

    # Lookup arma (base + fabricadas)
    weapon = WEAPON_REGISTRY.get(weapon_name or "") or WEAPON_REGISTRY_FABRICADO.get(weapon_name or "", {})
    weapon_bonus: int = weapon.get("damage_bonus", 0)

    d4_raw = roll_d4()

    if check["result"] in ("SUCESSO_CRITICO", "SUCESSO"):
        base      = d4_raw * 2 if is_critical else d4_raw
        damage_dealt = base + weapon_bonus
    else:
        damage_dealt = 0

    # Redução de armadura dinâmica
    reduction    = get_armor_reduction(armor_name)
    damage_taken = max(0, enemy_damage - reduction) if not enemy_is_stunned else 0

    # Efeito de status — rola chance somente se houve dano
    effect_applied: Optional[str] = None
    if damage_dealt > 0 and weapon.get("effect"):
        effect_id = weapon["effect"]
        effect_dc = weapon.get("effect_dc", 12)
        effect_roll = roll_d20()
        if effect_roll >= effect_dc or is_critical:
            effect_applied = effect_id

    return {
        "d20_raw":          d20_raw,
        "total_attack":     check["total"],
        "check_result":     check["result"],
        "is_critical":      is_critical,
        "d4_raw":           d4_raw,
        "weapon_bonus":     weapon_bonus,
        "damage_dealt":     damage_dealt,
        "damage_reduction": reduction,
        "damage_taken":     damage_taken,
        "effect_applied":   effect_applied,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. RESOLUÇÃO DE COMBATE NAVAL (Ship-to-Ship)
# ─────────────────────────────────────────────────────────────────────────────

SHIP_DAMAGE_ON_SHIELDS = 15
SHIP_DAMAGE_ON_HULL    = 10

def resolve_ship_combat(
    player_piloting: int,
    enemy_ac: int,
    enemy_shields: int,
) -> dict:
    """
    Executa roll_d20() internamente e processa um disparo de canhão (Ship-to-Ship).
    Não recebe d20_result como parâmetro.
    Custo de energia (-2) deve ser deduzido ANTES por calculate_turn_cost.

    Retorna dict com:
      d20_raw:        int
      total_attack:   int
      check_result:   str
      shield_damage:  int (0 se falha ou escudos = 0)
      hull_damage:    int (0 se escudos > 0 ou falha)
    """
    check = resolve_check(player_piloting, enemy_ac)

    if check["result"] in ("SUCESSO_CRITICO", "SUCESSO"):
        if enemy_shields > 0:
            shield_dmg, hull_dmg = SHIP_DAMAGE_ON_SHIELDS, 0
        else:
            shield_dmg, hull_dmg = 0, SHIP_DAMAGE_ON_HULL
    else:
        shield_dmg, hull_dmg = 0, 0

    return {
        "d20_raw":       check["d20_raw"],
        "total_attack":  check["total"],
        "check_result":  check["result"],
        "shield_damage": shield_dmg,
        "hull_damage":   hull_dmg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. XP — concessão e detecção de level up
# ─────────────────────────────────────────────────────────────────────────────

XP_TABLE = {
    # evento → XP concedido
    "inimigo_fraco":        10,   # HP original <= 10
    "inimigo_medio":        20,   # HP original 11–25
    "inimigo_forte":        35,   # HP original >= 26
    "inimigo_chefe":        60,
    "area_nova":            15,
    "objeto_analisado":     10,
    "crafting_sucesso":      5,
    "quest_completada":     50,
    "quest_falhada":        10,
    "sobrevivencia_critica":20,   # sobreviveu com HP ou O2 abaixo de 10%
}

LEVEL_TABLE = {
    # nivel → (xp_total_acumulado, attr_points, hp_max)
    1:  (0,    0, 20),
    2:  (100,  2, 24),
    3:  (250,  2, 28),
    4:  (450,  3, 33),
    5:  (700,  3, 38),
    6:  (1000, 3, 44),
    7:  (1400, 4, 50),
    8:  (1900, 4, 57),
    9:  (2500, 4, 64),
    10: (3200, 5, 72),
}

def calculate_xp_gain(events: list[str]) -> int:
    """
    Recebe lista de eventos ocorridos no turno e retorna XP total ganho.
    Exemplo: ["inimigo_medio", "area_nova"]
    """
    return sum(XP_TABLE.get(e, 0) for e in events)

def check_level_up(xp_current: int, current_level: int) -> dict:
    """
    Verifica se há level up pendente.

    Retorna dict com:
      level_up:        bool
      new_level:       int (igual ao atual se não há level up)
      attr_points:     int — pontos a distribuir (0 se sem level up)
      new_hp_max:      int — novo HP máximo (igual ao atual se sem level up)
      xp_to_next:      int — XP necessário para o próximo nível
    """
    next_level = current_level + 1
    if next_level not in LEVEL_TABLE:
        return {"level_up": False, "new_level": current_level, "attr_points": 0,
                "new_hp_max": LEVEL_TABLE[current_level][2], "xp_to_next": 0}

    xp_threshold = LEVEL_TABLE[next_level][0]
    if xp_current >= xp_threshold:
        _, attr_points, hp_max = LEVEL_TABLE[next_level]
        next_xp = LEVEL_TABLE.get(next_level + 1, (0,))[0]
        return {
            "level_up":   True,
            "new_level":  next_level,
            "attr_points": attr_points,
            "new_hp_max": hp_max,
            "xp_to_next": next_xp,
        }

    _, _, current_hp_max = LEVEL_TABLE[current_level]
    return {
        "level_up":   False,
        "new_level":  current_level,
        "attr_points": 0,
        "new_hp_max": current_hp_max,
        "xp_to_next": xp_threshold,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. CRAFTING — verificação de materiais e resolução
# ─────────────────────────────────────────────────────────────────────────────

CRAFTING_RECIPES: dict[str, Any] = {
    "reparo_casco": {
        "materiais":  {"Placa de Metal": 2, "Solda": 1},
        "atributo":   "INT",
        "dc":         10,
        "output_json": {"hull_integrity": 15},   # delta aplicado ao character_sheet
        "output_csv":  None,                      # sem item adicionado
    },
    "municao_energetica": {
        "materiais":  {"Bateria de Íon": 1, "Sucata Eletrônica": 1},
        "atributo":   None,    # automático, sem teste
        "dc":         None,
        "output_json": None,
        "output_csv":  {
            "name": "Cargas de Rifle", "type": "Consumível", "rarity": "Incomum",
            "quantity": 10, "weight_kg": 0.05,
            "effect": "Munição para Rifle Energético. 1 carga = 1 disparo.",
            "usable": False, "notes": "Fabricado via crafting.",
        },
    },
    "filtro_o2": {
        "materiais":  {"Biomassa": 2, "Plástico": 1},
        "atributo":   None,
        "dc":         None,
        "output_json": {"oxygen_level": 20},
        "output_csv":  None,
    },
    "drone_auxiliar": {
        "materiais":  {"Chip de IA Corrompido": 1, "Sucata Eletrônica": 3, "Bateria de Íon": 1},
        "atributo":   "INT",
        "dc":         18,
        "output_json": None,
        "output_csv":  {
            "name": "Drone Auxiliar", "type": "Equipamento Passivo", "rarity": "Raro",
            "quantity": 1, "weight_kg": 1.2,
            "effect": "+2 fixo em todos os testes de Engineering futuros.",
            "usable": False, "notes": "Aplicar bônus ao character_sheet.json → skills.engineering.bonus.",
        },
    },
}

def check_crafting_materials(recipe_key: str, inventory: dict) -> dict:
    """
    Verifica se o inventário tem os materiais necessários para a receita.
    inventory: dict nome_item → quantity (ex: {"Placa de Metal": 2, ...})

    Retorna dict com:
      ok:      bool
      missing: dict com itens faltando e quantidades
    """
    recipe = CRAFTING_RECIPES.get(recipe_key)
    if not recipe:
        return {"ok": False, "missing": {}, "error": "RECEITA_INVALIDA"}

    missing = {}
    for item, qty_needed in recipe["materiais"].items():
        available = inventory.get(item, 0)
        if available < qty_needed:
            missing[item] = qty_needed - available

    return {"ok": len(missing) == 0, "missing": missing}


# ─────────────────────────────────────────────────────────────────────────────
# 11. AVALIAÇÃO DE STATUS CRÍTICO
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_status(character: dict) -> str:
    """
    Avalia o estado atual do personagem e retorna o status global.
    character: character_sheet.json completo (como dict Python)

    Retorna: "STABLE" | "CRITICAL_FAILURE" | "DECEASED"
    """
    vitals = character.get("vitals", {})
    hp     = vitals.get("hp", {}).get("current", 1)
    o2     = vitals.get("oxygen_level", {}).get("current", 100)
    hull   = vitals.get("hull_integrity", {}).get("current", 100)

    if hp <= 0 or o2 <= 0 or hull <= 0:
        return "DECEASED"
    if hp <= 5 or o2 <= 10:
        return "CRITICAL_FAILURE"
    return "STABLE"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIO: clamp de recurso entre 0 e max
# ─────────────────────────────────────────────────────────────────────────────

def clamp(value: int | float, min_val: int | float = 0, max_val: int | float = 100):
    return max(min_val, min(max_val, value))

# ─────────────────────────────────────────────────────────────────────────────
# 12. EFEITOS DE STATUS — definições canônicas
# ─────────────────────────────────────────────────────────────────────────────

STATUS_EFFECTS: dict[str, Any] = {
    "sangramento": {
        "nome": "Sangramento", "descricao": "Ferida aberta drena vitalidade.",
        "tipo": "dano_turno", "dano_por_turno": 2, "duracao_max": None,
        "acumulavel": True, "reducao_dc": 0,
        "cura_por": ["Injetor Médico", "Erva Medicinal"],
    },
    "veneno": {
        "nome": "Veneno", "descricao": "Toxina sistêmica. Dano constante por duração fixa.",
        "tipo": "dano_turno", "dano_por_turno": 2, "duracao_max": 4,
        "acumulavel": False, "reducao_dc": 0, "cura_por": ["Injetor Médico"],
    },
    "queimadura": {
        "nome": "Queimadura", "descricao": "Tecido carbonizado. Dano alto mas dura pouco.",
        "tipo": "dano_turno", "dano_por_turno": 3, "duracao_max": 3,
        "acumulavel": False, "reducao_dc": 0, "cura_por": [],
    },
    "atordoamento": {
        "nome": "Atordoamento", "descricao": "Inimigo não contra-ataca por 1 turno.",
        "tipo": "skip_ataque", "dano_por_turno": 0, "duracao_max": 1,
        "acumulavel": False, "reducao_dc": 0, "cura_por": [],
    },
    "corrosao": {
        "nome": "Corrosão", "descricao": "DC de defesa do inimigo reduzida permanentemente.",
        "tipo": "reducao_dc", "dano_por_turno": 0, "duracao_max": None,
        "acumulavel": True, "reducao_dc": 2, "cura_por": [],
    },
    "choque_eletrico": {
        "nome": "Choque Elétrico", "descricao": "Sistema sobrecarregado. Dano e desorientação.",
        "tipo": "dano_turno", "dano_por_turno": 2, "duracao_max": 2,
        "acumulavel": False, "reducao_dc": 0, "cura_por": [],
    },
    "cegueira": {
        "nome": "Cegueira", "descricao": "Visão/sensores bloqueados. DC reduzida.",
        "tipo": "reducao_dc", "dano_por_turno": 0, "duracao_max": 2,
        "acumulavel": False, "reducao_dc": 4, "cura_por": [],
    },
    "paralisia": {
        "nome": "Paralisia", "descricao": "Inimigo imobilizado. Não contra-ataca por 2 turnos.",
        "tipo": "skip_ataque", "dano_por_turno": 0, "duracao_max": 2,
        "acumulavel": False, "reducao_dc": 0, "cura_por": [],
    },
    # REGRA DE OURO: NUNCA altere entradas existentes. Adicione ao final.
}


# ─────────────────────────────────────────────────────────────────────────────
# 13. REGISTRO DE ARMAS BASE
# ─────────────────────────────────────────────────────────────────────────────

WEAPON_REGISTRY: dict[str, Any] = {
    "Lança Primitiva":       {"damage_bonus": 1, "effect": "sangramento",    "effect_dc": 13},
    "Faca Improvisada":      {"damage_bonus": 0, "effect": "sangramento",    "effect_dc": 16},
    "Rifle Energético":      {"damage_bonus": 2, "effect": "queimadura",     "effect_dc": 14},
    "Pistola de Choque":     {"damage_bonus": 1, "effect": "atordoamento",   "effect_dc": 12},
    "Lançador Ácido":        {"damage_bonus": 1, "effect": "corrosao",       "effect_dc": 11},
    "Canhão de Pulso":       {"damage_bonus": 3, "effect": "paralisia",      "effect_dc": 15},
    "Injetor Neurotóxico":   {"damage_bonus": 0, "effect": "veneno",         "effect_dc": 10},
    "Lança-Chamas Compacto": {"damage_bonus": 1, "effect": "queimadura",     "effect_dc": 10},
    # REGRA DE OURO: NUNCA altere entradas existentes. Adicione ao final.
}


# ─────────────────────────────────────────────────────────────────────────────
# 14. UTILITÁRIOS DE EFEITO (inimigo e jogador)
# ─────────────────────────────────────────────────────────────────────────────

def process_status_effects(status_effects: list) -> dict:
    """Processa efeitos de status no INIMIGO (active_combat.json)."""
    dano_parts: list[int] = []
    dc_parts:   list[int] = []
    is_stunned: bool      = False
    expirados:  list[str] = []
    atualizados: list[dict] = []
    for entry in status_effects:
        defn = STATUS_EFFECTS.get(entry.get("id", ""))
        if not defn:
            continue
        stacks:   int            = int(entry.get("stacks", 1))
        restante: Optional[int]  = entry.get("turno_restante")
        if defn["tipo"] == "dano_turno":
            dano_parts.append(int(defn["dano_por_turno"]) * stacks)
        elif defn["tipo"] == "skip_ataque":
            is_stunned = True
        elif defn["tipo"] == "reducao_dc":
            dc_parts.append(int(defn["reducao_dc"]) * stacks)
        if restante is None:
            atualizados.append(entry)
        elif restante <= 1:
            expirados.append(str(entry["id"]))
        else:
            novo = dict(entry)
            novo["turno_restante"] = restante - 1
            atualizados.append(novo)
    return {"dano_total": sum(dano_parts), "enemy_is_stunned": is_stunned,
            "dc_penalty": sum(dc_parts), "efeitos_expirados": expirados,
            "efeitos_atualizados": atualizados}


def apply_new_effect(status_effects: list, effect_id: str) -> list:
    """Adiciona ou incrementa efeito na lista (inimigo ou jogador)."""
    defn = STATUS_EFFECTS.get(effect_id)
    if not defn:
        return status_effects
    for entry in status_effects:
        if entry["id"] == effect_id:
            if defn["acumulavel"]:
                entry["stacks"] += 1
            return status_effects
    status_effects.append({"id": effect_id, "stacks": 1,
                            "turno_restante": defn["duracao_max"]})
    return status_effects


# ─────────────────────────────────────────────────────────────────────────────
# 15. EFEITOS DE STATUS NO JOGADOR
#
# Espelha process_status_effects() mas opera sobre character_sheet.json.
# Chamado pelo System_Engine NO INÍCIO de cada turno, antes de qualquer ação.
#
# Entrada: lista de active_status_effects do character_sheet.json
# Retorna dict com:
#   dano_total:          int  — HP a deduzir do jogador
#   efeitos_expirados:   list[str]
#   efeitos_atualizados: list[dict] — para salvar de volta no JSON
# ─────────────────────────────────────────────────────────────────────────────

def process_player_status_effects(status_effects: list) -> dict:
    """
    Processa todos os efeitos de status ativos no jogador.
    Deve ser chamado pelo System_Engine ANTES do cálculo de custo basal,
    no início de cada turno.
    """
    dano_parts: list[int]  = []
    expirados:  list[str]  = []
    atualizados: list[dict] = []

    for entry in status_effects:
        effect_id: str          = str(entry.get("id", ""))
        stacks:    int          = int(entry.get("stacks", 1))
        restante:  Optional[int] = entry.get("turno_restante")

        definition = STATUS_EFFECTS.get(effect_id)
        if not definition:
            continue

        tipo = definition["tipo"]
        if tipo == "dano_turno":
            dano_parts.append(int(definition["dano_por_turno"]) * stacks)
        # skip_ataque e reducao_dc não se aplicam ao jogador — ignorar

        if restante is None:
            atualizados.append(entry)
        elif restante <= 1:
            expirados.append(effect_id)
        else:
            novo = dict(entry)
            novo["turno_restante"] = restante - 1
            atualizados.append(novo)

    return {
        "dano_total":          sum(dano_parts),
        "efeitos_expirados":   expirados,
        "efeitos_atualizados": atualizados,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 16. SCHEMA DE ARMAS FABRICADAS
#
# Define o que uma arma gerada dinamicamente pelo Architect deve conter.
# O Architect preenche este template e o adiciona a WEAPON_REGISTRY.
#
# REGRA DE OURO: NUNCA altere entradas existentes. Adicione apenas ao final.
# ─────────────────────────────────────────────────────────────────────────────

WEAPON_SCHEMA: dict[str, Any] = {
    # Template obrigatório — todos os campos devem ser preenchidos pelo Architect
    "_template": {
        "name":         "str  — nome exato que aparece no inventory.csv",
        "damage_bonus": "int  — somado ao d4 em todo acerto (0 se arma não tem bônus)",
        "effect":       "str|None — id de STATUS_EFFECTS ou null",
        "effect_dc":    "int  — DC do d20 bruto para aplicar o efeito (ignorado se effect=null)",
        "arco":         "int  — 1, 2 ou 3 (arco narrativo de origem)",
        "rarity":       "str  — Comum | Incomum | Raro | Lendário",
        "weight_kg":    "float — peso em kg para o inventory.csv",
        "notes":        "str  — descrição física Hard Sci-Fi, máx. 1 frase",
    }
}

# Registro de armas fabricadas dinamicamente (preenchido pelo Architect)
# Estrutura idêntica a WEAPON_REGISTRY — o System_Engine consulta os dois juntos
WEAPON_REGISTRY_FABRICADO: dict[str, Any] = {
    # REGRA DE OURO: NUNCA altere entradas existentes. Adicione ao final.
}


# ─────────────────────────────────────────────────────────────────────────────
# 17. SCHEMA DE ARMADURAS FABRICADAS
#
# Armaduras não são itens usáveis — são equipadas em character_sheet.json
# → equipment.armor. A redução de dano substitui o valor fixo ARMOR_DAMAGE_REDUCTION.
#
# REGRA DE OURO: NUNCA altere entradas existentes. Adicione apenas ao final.
# ─────────────────────────────────────────────────────────────────────────────

ARMOR_SCHEMA: dict[str, Any] = {
    "_template": {
        "name":            "str   — nome exato no inventory.csv",
        "damage_reduction":"int   — substitui ARMOR_DAMAGE_REDUCTION enquanto equipada",
        "suit_integrity_bonus": "int — bônus passivo em suit_integrity.max (0 se não aplicável)",
        "arco":            "int   — arco de origem",
        "rarity":          "str   — Comum | Incomum | Raro | Lendário",
        "weight_kg":       "float",
        "notes":           "str   — descrição física, máx. 1 frase",
    }
}

# Registro de armaduras (base + fabricadas)
ARMOR_REGISTRY: dict[str, Any] = {
    # ── Armas base ────────────────────────────────────────────────────────────
    "Armadura de Couro": {
        "damage_reduction": 2,
        "suit_integrity_bonus": 0,
        "arco": 1, "rarity": "Comum", "weight_kg": 3.0,
        "notes": "Tiras de couro animal reforçado. Proteção básica contra impacto físico.",
    },
    # REGRA DE OURO: Novas entradas adicionadas ao final pelo Architect.
}


# ─────────────────────────────────────────────────────────────────────────────
# 18. SCHEMA DE ITENS DINÂMICOS (fabricação livre)
#
# Para itens que não são armas nem armaduras — utilitários, ferramentas,
# consumíveis avançados, equipamentos passivos criados pelo Architect.
#
# O Architect preenche este template, adiciona ao ITEM_SCHEMA do loot_manager.py
# e à tabela de crafting em crafting_recipes.md.
# ─────────────────────────────────────────────────────────────────────────────

DYNAMIC_ITEM_SCHEMA: dict[str, Any] = {
    "_template": {
        "name":      "str   — nome único, Case-Sensitive, sem abreviação",
        "type":      "str   — Material|Consumível|Equipamento Passivo|Recurso|Quest|Arma|Armadura",
        "rarity":    "str   — Comum|Incomum|Raro|Lendário",
        "quantity":  "int   — sempre 1 ao ser criado",
        "weight_kg": "float — peso unitário",
        "effect":    "str   — efeito mecânico exato (ex: +15 HP, +2 FOR permanente, equipa como Armadura)",
        "usable":    "bool  — true se o jogador pode usar como ação",
        "notes":     "str   — instruções especiais ou flags de quest",
        # Campos extras obrigatórios dependendo do tipo:
        # Se type == "Arma":    adicionar entrada em WEAPON_REGISTRY_FABRICADO
        # Se type == "Armadura": adicionar entrada em ARMOR_REGISTRY
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# 19. RESOLUÇÃO DE ARMADURA ATIVA
#
# Lê o nome da armadura equipada e retorna a redução de dano correta.
# Consultado por resolve_personal_combat().
# ─────────────────────────────────────────────────────────────────────────────

def get_armor_reduction(armor_name: Optional[str]) -> int:
    """
    Retorna a redução de dano da armadura equipada.
    - None → 0 (sem armadura)
    - Nome encontrado no registry → valor do registro
    - Nome não encontrado → ARMOR_DAMAGE_REDUCTION (fallback seguro)
    """
    if not armor_name:
        return 0
    entry = ARMOR_REGISTRY.get(armor_name)
    if entry is None:
        return ARMOR_DAMAGE_REDUCTION  # fallback para armaduras futuras não registradas
    return entry.get("damage_reduction", ARMOR_DAMAGE_REDUCTION)


# ─────────────────────────────────────────────────────────────────────────────
# 34. HABILIDADES PASSIVAS POR NÍVEL
#
# Ao subir de nível, além dos pontos de atributo, o jogador escolhe UMA
# habilidade passiva da lista abaixo. Habilidades desbloqueadas são
# permanentes e persistem em character_sheet.json → passive_skills (lista).
#
# Regras de elegibilidade:
#   - Cada habilidade pode ser adquirida APENAS UMA VEZ.
#   - Algumas têm pré-requisito de atributo (ex: INT ≥ 12) ou de nível (ex: nível ≥ 3).
#   - O jogador vê apenas as habilidades que pode adquirir (requisitos cumpridos).
#   - Habilidades já adquiridas não aparecem na lista de escolha.
#
# Integração com outros sistemas:
#   - get_skill_total()       → skill_bonuses               (Seção 22)
#   - get_armor_reduction()   → dano_reducao_fisica          (Seção 19)
#   - resolve_enemy_damage()  → critico_limiar               (Seção 23)
#   - check_trap_detection()  → armadilha_bonus              (Seção 33)
#   - calculate_encumbrance() → capacidade e stealth         (Seção 30)
#   - apply_survival_decay()  → survival_decay_reducao       (Seção 28)
# ─────────────────────────────────────────────────────────────────────────────

PASSIVE_SKILLS: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: SOBREVIVÊNCIA
    # Árvore focada em SOB. Resistência ao ambiente, regeneração, limiar da morte.
    # ══════════════════════════════════════════════════════════════════════════

    "pele_grossa": {
        "nome":        "Pele Grossa",
        "descricao":   "Anos de sucata e trabalho pesado endureceram o corpo. Reduz todo dano físico recebido.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {
            "tipo":      "dano_reducao",
            "valor":     1,
            "condicao":  "tipo_dano == 'Físico'",
            "descricao": "+1 redução permanente em dano Físico recebido.",
        },
    },

    "sangue_frio": {
        "nome":        "Sangue Frio",
        "descricao":   "Metabolismo que aprendeu a se conservar. Survival needs decaem mais devagar.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 2,
        "requisito":   {"SOB": 11},
        "efeito": {
            "tipo":      "survival_decay_reducao",
            "valor":     1,
            "descricao": "Fome/Sede/Exaustão decaem 1 a menos por turno (mínimo 0).",
        },
    },

    "resistencia_termica": {
        "nome":        "Resistência Térmica",
        "descricao":   "Tolerância construída turno a turno em ambientes hostis. Frio, calor e ácido machucam menos.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 3,
        "requisito":   {"SOB": 12},
        "efeito": {
            "tipo":      "hp_exposure_reducao",
            "valor":     1,
            "descricao": "-1 HP de exposição ambiental (frio, fogo, ácido) por turno.",
        },
    },

    "metabolismo_de_ferro": {
        "nome":        "Metabolismo de Ferro",
        "descricao":   "O corpo aprende a extrair mais de menos. Comida e água rendem mais.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 4,
        "requisito":   {"SOB": 13},
        "efeito": {
            "tipo":      "survival_item_bonus",
            "valor":     15,   # +15 em todos os itens de recuperação de fome/sede
            "descricao": "Itens de fome/sede recuperam +15 pontos a mais ao serem consumidos.",
        },
    },

    "ultimo_suspiro": {
        "nome":        "Último Suspiro",
        "descricao":   "Uma vez por capítulo, quando HP chegaria a 0, ficar em 1 HP.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 5,
        "requisito":   {"SOB": 14},
        "efeito": {
            "tipo":                "hp_zero_prevencao",
            "usos_por_capitulo":   1,
            "descricao":           "1×/capítulo: HP que chegaria a 0 fica em 1. Registrar uso no JSON.",
        },
    },

    "recuperacao_acelerada": {
        "nome":        "Recuperação Acelerada",
        "descricao":   "O corpo cicatriza além do normal. Cura por repouso rende o dobro.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 6,
        "requisito":   {"SOB": 15},
        "efeito": {
            "tipo":      "cura_repouso_bonus",
            "mult":      2,
            "descricao": "HP recuperado por repouso ou item médico é multiplicado por 2.",
        },
    },

    "carapaça": {
        "nome":        "Carapaça",
        "descricao":   "A pele endurecida vai além. Reduz também dano químico e elétrico.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 7,
        "requisito":   {"SOB": 16, "pele_grossa": True},   # requer pele_grossa adquirida
        "efeito": {
            "tipo":      "dano_reducao_multi",
            "valor":     1,
            "tipos":     ["Físico", "Químico", "Elétrico"],
            "descricao": "+1 redução em dano Físico, Químico e Elétrico recebido.",
        },
    },

    "vontade_de_aco": {
        "nome":        "Vontade de Aço",
        "descricao":   "Quando a maioria desistiria, Ferro funciona. Penalidades de survival needs reduzidas à metade.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 8,
        "requisito":   {"SOB": 17},
        "efeito": {
            "tipo":      "survival_penalty_reducao",
            "divisor":   2,
            "descricao": "DC penalty de fome/sede/exaustão é dividida por 2 (arredondado para baixo).",
        },
    },

    "corpo_de_maquina": {
        "nome":        "Corpo de Máquina",
        "descricao":   "O chip CHRONOS-7 e o corpo trabalham em simbiose. Exaustão não reduz mais atributos.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 9,
        "requisito":   {"SOB": 18},
        "efeito": {
            "tipo":      "exaustao_sem_penalidade_atributo",
            "descricao": "Exaustão aplica apenas DC penalty normal — nunca reduz atributos diretamente.",
        },
    },

    "imortal_de_sucata": {
        "nome":        "Imortal de Sucata",
        "descricao":   "Ferro já deveria ter morrido dezenas de vezes. O universo deixou de tentar.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 10,
        "requisito":   {"SOB": 20},
        "efeito": {
            "tipo":      "hp_zero_prevencao",
            "usos_por_capitulo": 3,
            "descricao": "3×/capítulo: HP que chegaria a 0 fica em 1. Acumula com Último Suspiro (total 4×).",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: COMBATE
    # Árvore focada em DES e FOR. Dano, defesa, críticos, situações extremas.
    # ══════════════════════════════════════════════════════════════════════════

    "postura_defensiva": {
        "nome":        "Postura Defensiva",
        "descricao":   "Usar o ambiente como escudo. +1 DC de defesa quando em COBERTO.",
        "categoria":   "Combate",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {
            "tipo":      "dc_defesa_bonus_posicao",
            "valor":     1,
            "condicao":  "COBERTO",
            "descricao": "+1 DC de defesa efetiva quando posicionamento é COBERTO.",
        },
    },

    "reflexos_rapidos": {
        "nome":        "Reflexos Rápidos",
        "descricao":   "Instinto afiado que reduz a janela de crítico do inimigo.",
        "categoria":   "Combate",
        "nivel_minimo": 2,
        "requisito":   {"DES": 11},
        "efeito": {
            "tipo":      "critico_limiar_reducao",
            "valor":     1,
            "descricao": "Crítico do inimigo ativado apenas se d20 do jogador ≤ 2 (padrão: ≤ 3).",
        },
    },

    "golpe_preciso": {
        "nome":        "Golpe Preciso",
        "descricao":   "Conhecimento de pontos fracos — biológicos ou mecânicos. +1 dano em todo ataque.",
        "categoria":   "Combate",
        "nivel_minimo": 3,
        "requisito":   {"DES": 12},
        "efeito": {
            "tipo":      "dano_bonus_fixo",
            "valor":     1,
            "descricao": "+1 dano fixo em todo ataque bem-sucedido (somado após o d4).",
        },
    },

    "furia_terminal": {
        "nome":        "Fúria Terminal",
        "descricao":   "Quando o corpo está quebrando, os golpes ficam mais desesperados — e mais letais.",
        "categoria":   "Combate",
        "nivel_minimo": 4,
        "requisito":   {"FOR": 12},
        "efeito": {
            "tipo":      "ataque_bonus_hp_baixo",
            "valor":     2,
            "condicao":  "hp_pct <= 0.30",
            "descricao": "+2 no total do teste de ataque quando HP ≤ 30% do máximo.",
        },
    },

    "esquiva_instintiva": {
        "nome":        "Esquiva Instintiva",
        "descricao":   "O corpo reage antes da mente processar. Reduz o dano do primeiro contra-ataque por combate.",
        "categoria":   "Combate",
        "nivel_minimo": 4,
        "requisito":   {"DES": 13},
        "efeito": {
            "tipo":      "primeiro_contra_ataque_reducao",
            "valor":     2,
            "descricao": "Primeiro contra-ataque de cada combate causa -2 dano (mínimo 0).",
        },
    },

    "golpe_brutal": {
        "nome":        "Golpe Brutal",
        "descricao":   "Força bruta transmutada em técnica. Crítico do jogador aplica efeito de status adicional.",
        "categoria":   "Combate",
        "nivel_minimo": 5,
        "requisito":   {"FOR": 14},
        "efeito": {
            "tipo":      "critico_status_bonus",
            "status":    "atordoamento",
            "duracao":   1,
            "descricao": "Acerto crítico do jogador aplica Atordoado no inimigo por 1 turno.",
        },
    },

    "fortitude_de_combate": {
        "nome":        "Fortitude de Combate",
        "descricao":   "Treinamento que converte resistência em armadura. FOR alta reduz dano recebido.",
        "categoria":   "Combate",
        "nivel_minimo": 6,
        "requisito":   {"FOR": 15},
        "efeito": {
            "tipo":      "dano_reducao_for_bonus",
            "formula":   "max(0, (FOR-14)//2)",
            "descricao": "Redução de dano adicional = max(0, (FOR−14)//2). Com FOR 16: +1. FOR 18: +2. FOR 20: +3.",
        },
    },

    "implacavel": {
        "nome":        "Implacável",
        "descricao":   "Ferimentos permanentes não penalizam testes de combate — a dor virou rotina.",
        "categoria":   "Combate",
        "nivel_minimo": 7,
        "requisito":   {"FOR": 15, "SOB": 14},
        "efeito": {
            "tipo":      "ferimento_combat_imune",
            "descricao": "Penalidades de ferimentos permanentes não se aplicam a testes de combat e dano.",
        },
    },

    "reflexo_de_predador": {
        "nome":        "Reflexo de Predador",
        "descricao":   "Crítico do inimigo se torna praticamente impossível. Limiar cai para d20 = 1.",
        "categoria":   "Combate",
        "nivel_minimo": 8,
        "requisito":   {"DES": 17, "reflexos_rapidos": True},
        "efeito": {
            "tipo":      "critico_limiar_fixo",
            "valor":     1,
            "descricao": "Crítico do inimigo ativado apenas se d20 do jogador = 1 (padrão: ≤ 3).",
        },
    },

    "maquina_de_matar": {
        "nome":        "Máquina de Matar",
        "descricao":   "Todo ataque bem-sucedido carrega mais peso. +2 dano fixo em todo ataque.",
        "categoria":   "Combate",
        "nivel_minimo": 9,
        "requisito":   {"DES": 18, "golpe_preciso": True},
        "efeito": {
            "tipo":      "dano_bonus_fixo",
            "valor":     2,
            "descricao": "+2 dano fixo em todo ataque (acumula com Golpe Preciso: total +3).",
        },
    },

    "forma_perfeita": {
        "nome":        "Forma Perfeita",
        "descricao":   "O corpo em seu limite absoluto. Toda a DES se traduz em precisão letal.",
        "categoria":   "Combate",
        "nivel_minimo": 10,
        "requisito":   {"DES": 20},
        "efeito": {
            "tipo":      "ataque_bonus_des_escala",
            "formula":   "(DES - 10) // 3",
            "descricao": "Bônus de ataque = (DES−10)//3. Com DES 20: +3 permanente em todos os testes de combat.",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: EXPLORAÇÃO
    # Árvore focada em PER e INT. Mapa, armadilhas, fauna, detalhes ocultos.
    # ══════════════════════════════════════════════════════════════════════════

    "rastreador": {
        "nome":        "Rastreador",
        "descricao":   "Leitura de pegadas, galhos quebrados e perturbações deixadas por fauna.",
        "categoria":   "Exploração",
        "nivel_minimo": 1,
        "requisito":   {"PER": 10},
        "efeito": {
            "tipo":      "skill_bonus",
            "skill":     "survival",
            "valor":     2,
            "bonus_encontro_previo": True,
            "descricao": "+2 em survival. Ao explorar área, GM avisa se inimigo passou recentemente.",
        },
    },

    "olho_clinico": {
        "nome":        "Olho Clínico",
        "descricao":   "Treinamento em leitura de ambiente. +2 scan e +3 em detecção de armadilhas.",
        "categoria":   "Exploração",
        "nivel_minimo": 2,
        "requisito":   {"PER": 11},
        "efeito": {
            "tipo":             "skill_bonus",
            "skill":            "scan",
            "valor":            2,
            "bonus_armadilha":  3,
            "descricao":        "+2 em testes de scan. +3 extra em detecção de armadilhas.",
        },
    },

    "memoria_fotografica": {
        "nome":        "Memória Fotográfica",
        "descricao":   "Cada área é mapeada em detalhes pelo chip CHRONOS-7. Recursos ocultos revelados.",
        "categoria":   "Exploração",
        "nivel_minimo": 3,
        "requisito":   {"INT": 12},
        "efeito": {
            "tipo":      "mapa_detalhe_bonus",
            "descricao": "Áreas exploradas ganham campo 'recursos_ocultos' no mapa procedural.",
        },
    },

    "sentido_de_perigo": {
        "nome":        "Sentido de Perigo",
        "descricao":   "Presença de ameaça percebida antes do contato visual. +4 contra emboscadas.",
        "categoria":   "Exploração",
        "nivel_minimo": 4,
        "requisito":   {"PER": 13},
        "efeito": {
            "tipo":      "emboscada_bonus",
            "valor":     4,
            "descricao": "+4 em testes de PER ao detectar inimigos em emboscada ou furtivos.",
        },
    },

    "leitura_de_ambiente": {
        "nome":        "Leitura de Ambiente",
        "descricao":   "O clima e a fauna se tornam sinais legíveis. Penalidades de noite e neblina reduzidas.",
        "categoria":   "Exploração",
        "nivel_minimo": 5,
        "requisito":   {"PER": 14},
        "efeito": {
            "tipo":      "visibilidade_penalty_reducao",
            "valor":     2,
            "descricao": "Penalidades de DC por NOITE e NEBLINA reduzidas em 2 (ex: NOITE +4 vira +2).",
        },
    },

    "cartografo_instintivo": {
        "nome":        "Cartógrafo Instintivo",
        "descricao":   "Toda transição entre áreas revela conexões adicionais no mapa.",
        "categoria":   "Exploração",
        "nivel_minimo": 6,
        "requisito":   {"INT": 14, "PER": 13},
        "efeito": {
            "tipo":      "mapa_conexoes_bonus",
            "descricao": "Ao descobrir área nova, o Architect revela automaticamente 1 conexão adjacente extra.",
        },
    },

    "predador_de_informacao": {
        "nome":        "Predador de Informação",
        "descricao":   "Scan se torna cirúrgico. Resultado de Scan revela fraqueza do inimigo automaticamente.",
        "categoria":   "Exploração",
        "nivel_minimo": 7,
        "requisito":   {"INT": 15, "PER": 14},
        "efeito": {
            "tipo":      "scan_fraqueza_auto",
            "descricao": "Scan bem-sucedido em inimigo revela fraqueza e resistência (sem DC extra).",
        },
    },

    "sentidos_amplificados": {
        "nome":        "Sentidos Amplificados",
        "descricao":   "O chip CHRONOS-7 sincroniza com os sentidos. +4 em todos os testes de PER.",
        "categoria":   "Exploração",
        "nivel_minimo": 8,
        "requisito":   {"PER": 16, "INT": 14},
        "efeito": {
            "tipo":      "skill_bonus",
            "skill":     "scan",
            "valor":     4,
            "descricao": "+4 em todos os testes de scan e percepção.",
        },
    },

    "campo_ampliado": {
        "nome":        "Campo Ampliado",
        "descricao":   "Visão periférica e mapeamento passivo. Armadilhas inimigas são detectadas automaticamente.",
        "categoria":   "Exploração",
        "nivel_minimo": 9,
        "requisito":   {"PER": 18, "olho_clinico": True},
        "efeito": {
            "tipo":      "armadilha_deteccao_auto",
            "descricao": "Armadilhas inimigas são detectadas automaticamente ao entrar na área (sem rolagem).",
        },
    },

    "onisciencia_tatica": {
        "nome":        "Onisciência Tática",
        "descricao":   "PER no limite humano. O ambiente inteiro se torna um texto legível.",
        "categoria":   "Exploração",
        "nivel_minimo": 10,
        "requisito":   {"PER": 20},
        "efeito": {
            "tipo":      "per_escala_total",
            "descricao": "Penalidades de visibilidade (NOITE, NEBLINA, TEMPESTADE) são anuladas completamente.",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: TÉCNICA
    # Árvore focada em INT. Crafting, reparo, hacking, CHRONOS-7.
    # ══════════════════════════════════════════════════════════════════════════

    "sucateiro_nato": {
        "nome":        "Sucateiro Nato",
        "descricao":   "Instinto de Ferro para aproveitar tudo. Falha em crafting consome 1 material a menos.",
        "categoria":   "Técnica",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {
            "tipo":      "crafting_falha_salvamento",
            "valor":     1,
            "descricao": "Falha em crafting: salva 1 material que seria consumido (sorteio aleatório).",
        },
    },

    "maos_habilidosas": {
        "nome":        "Mãos Habilidosas",
        "descricao":   "Destreza fina para trabalho de precisão. -2 na DC de todas as receitas.",
        "categoria":   "Técnica",
        "nivel_minimo": 2,
        "requisito":   {"INT": 11},
        "efeito": {
            "tipo":      "crafting_dc_reducao",
            "valor":     2,
            "descricao": "-2 na DC de todo crafting e reparo.",
        },
    },

    "tecnico_de_campo": {
        "nome":        "Técnico de Campo",
        "descricao":   "Reparo improvisado sem infraestrutura. Pode reparar itens com materiais do inventário.",
        "categoria":   "Técnica",
        "nivel_minimo": 3,
        "requisito":   {"INT": 13},
        "efeito": {
            "tipo":      "reparo_sem_estacao",
            "descricao": "Pode reparar itens com materiais do inventário (DC padrão de reparo +3).",
        },
    },

    "engenharia_reversa": {
        "nome":        "Engenharia Reversa",
        "descricao":   "Desmontar revela o funcionamento. Itens desmontados rendem +1 material extra.",
        "categoria":   "Técnica",
        "nivel_minimo": 4,
        "requisito":   {"INT": 13},
        "efeito": {
            "tipo":      "desmontagem_bonus",
            "valor":     1,
            "descricao": "Ao desmontar item: +1 material aleatório além do resultado normal.",
        },
    },

    "interface_profunda": {
        "nome":        "Interface Profunda",
        "descricao":   "Conexão mais eficiente com o chip. Uso do CHRONOS-7 consome menos energia.",
        "categoria":   "Técnica",
        "nivel_minimo": 5,
        "requisito":   {"INT": 14},
        "efeito": {
            "tipo":      "chip_custo_reducao",
            "valor":     3,
            "descricao": "Ações de chip_interface custam -3% energy_reserves a menos.",
        },
    },

    "prototipagem_rapida": {
        "nome":        "Prototipagem Rápida",
        "descricao":   "Construção instintiva. Crafting não consome ação — pode ser feito junto a outra ação.",
        "categoria":   "Técnica",
        "nivel_minimo": 6,
        "requisito":   {"INT": 15},
        "efeito": {
            "tipo":      "crafting_sem_acao",
            "condicao":  "receita com DC ≤ 12",
            "descricao": "Receitas com DC ≤ 12 não consomem ação do turno (1×/turno).",
        },
    },

    "sobrecarga_controlada": {
        "nome":        "Sobrecarga Controlada",
        "descricao":   "Explorar os limites do chip sem queimá-lo. +3 em chip_interface em troca de -5% energy.",
        "categoria":   "Técnica",
        "nivel_minimo": 7,
        "requisito":   {"INT": 16},
        "efeito": {
            "tipo":      "chip_overload_opcao",
            "bonus":     3,
            "custo_energy": 5,
            "descricao": "Pode declarar Sobrecarga antes do teste: +3 chip_interface, mas -5% energy extra.",
        },
    },

    "arquiteto_de_armadilhas": {
        "nome":        "Arquiteto de Armadilhas",
        "descricao":   "Domínio total sobre armadilhas. Todas as receitas têm DC reduzida e dano aumentado.",
        "categoria":   "Técnica",
        "nivel_minimo": 8,
        "requisito":   {"INT": 16},
        "efeito": {
            "tipo":      "armadilha_dc_e_dano",
            "dc_reducao": 3,
            "dano_bonus": 2,
            "descricao": "Armadilhas criadas têm DC −3 e causam +2 dano ao acionar.",
        },
    },

    "genius_improvisado": {
        "nome":        "Gênio Improvisado",
        "descricao":   "INT tão alta que falha crítica em crafting (d20=1) vira falha simples — materiais salvos.",
        "categoria":   "Técnica",
        "nivel_minimo": 9,
        "requisito":   {"INT": 18},
        "efeito": {
            "tipo":      "crafting_critico_imune",
            "descricao": "Falha crítica em crafting (d20=1) trata-se como falha normal — materiais preservados.",
        },
    },

    "mente_de_maquina": {
        "nome":        "Mente de Máquina",
        "descricao":   "INT no limite. O chip e o cérebro são indistinguíveis. Todo teste de INT ignora penalidades.",
        "categoria":   "Técnica",
        "nivel_minimo": 10,
        "requisito":   {"INT": 20},
        "efeito": {
            "tipo":      "int_imune_penalidades",
            "descricao": "Todos os testes baseados em INT ignoram penalidades de ferimentos, exaustão e status.",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: FURTIVIDADE
    # Árvore focada em DES. Stealth, posicionamento, engano.
    # ══════════════════════════════════════════════════════════════════════════

    "sombra": {
        "nome":        "Sombra",
        "descricao":   "Movimento silencioso e instintivo construído em anos de sobrevivência urbana.",
        "categoria":   "Furtividade",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {
            "tipo":      "skill_bonus",
            "skill":     "stealth",
            "valor":     2,
            "descricao": "+2 em todos os testes de stealth.",
        },
    },

    "pisada_fantasma": {
        "nome":        "Pisada Fantasma",
        "descricao":   "O chão não registra Ferro. Terrenos difíceis (lama, folhas secas) não penalizam stealth.",
        "categoria":   "Furtividade",
        "nivel_minimo": 2,
        "requisito":   {"DES": 11},
        "efeito": {
            "tipo":      "stealth_terreno_imune",
            "descricao": "Terreno difícil não aplica penalidade extra em testes de stealth.",
        },
    },

    "ataque_surpresa": {
        "nome":        "Ataque Surpresa",
        "descricao":   "Atacar de furtividade. Se inimigo não detectou Ferro, primeiro ataque tem +3.",
        "categoria":   "Furtividade",
        "nivel_minimo": 3,
        "requisito":   {"DES": 12},
        "efeito": {
            "tipo":      "ataque_surpresa_bonus",
            "valor":     3,
            "descricao": "+3 no primeiro ataque do combate se iniciado de posição furtiva não detectada.",
        },
    },

    "passo_fantasma": {
        "nome":        "Passo Fantasma",
        "descricao":   "Peso não é obstáculo. PESADO não penaliza stealth.",
        "categoria":   "Furtividade",
        "nivel_minimo": 4,
        "requisito":   {"DES": 13},
        "efeito": {
            "tipo":      "encumbrance_stealth_excecao",
            "tier_ignorado": "PESADO",
            "descricao": "Tier PESADO não aplica penalidade de stealth. SOBRECARREGADO ainda penaliza.",
        },
    },

    "dissolver_nas_sombras": {
        "nome":        "Dissolver nas Sombras",
        "descricao":   "Durante NOITE ou NEBLINA, Ferro pode reentrar furtividade mesmo após ser detectado.",
        "categoria":   "Furtividade",
        "nivel_minimo": 5,
        "requisito":   {"DES": 14},
        "efeito": {
            "tipo":      "stealth_reentrada",
            "condicao":  "periodo == 'NOITE' or clima == 'NEBLINA'",
            "descricao": "NOITE/NEBLINA: pode tentar stealth novamente mesmo já detectado (DC +5).",
        },
    },

    "silhueta_vazia": {
        "nome":        "Silhueta Vazia",
        "descricao":   "Em COBERTO ou FLANQUEANDO, inimigos têm -2 em testes de percepção para localizar Ferro.",
        "categoria":   "Furtividade",
        "nivel_minimo": 6,
        "requisito":   {"DES": 15},
        "efeito": {
            "tipo":      "inimigo_percepcao_penalty_posicao",
            "valor":     -2,
            "condicao":  "posicao in ['COBERTO', 'FLANQUEANDO']",
            "descricao": "Em COBERTO ou FLANQUEANDO: inimigos têm -2 em PER para detectar Ferro.",
        },
    },

    "predador_silencioso": {
        "nome":        "Predador Silencioso",
        "descricao":   "Ataque surpresa letal. Dano dobrado no primeiro ataque de furtividade por combate.",
        "categoria":   "Furtividade",
        "nivel_minimo": 7,
        "requisito":   {"DES": 16, "ataque_surpresa": True},
        "efeito": {
            "tipo":      "ataque_surpresa_critico",
            "descricao": "Primeiro ataque de furtividade trata resultado do d4 como crítico (×2) automaticamente.",
        },
    },

    "fantasma_de_carne": {
        "nome":        "Fantasma de Carne",
        "descricao":   "Encumbrance não afeta mais stealth — nem SOBRECARREGADO.",
        "categoria":   "Furtividade",
        "nivel_minimo": 8,
        "requisito":   {"DES": 17, "passo_fantasma": True},
        "efeito": {
            "tipo":      "encumbrance_stealth_imune_total",
            "descricao": "Nenhum tier de encumbrance penaliza stealth.",
        },
    },

    "invisibilidade_tatica": {
        "nome":        "Invisibilidade Tática",
        "descricao":   "Stealth tão apurado que inimigos têm dificuldade de reagir mesmo após detectar.",
        "categoria":   "Furtividade",
        "nivel_minimo": 9,
        "requisito":   {"DES": 18},
        "efeito": {
            "tipo":      "stealth_deteccao_dc_bonus",
            "valor":     3,
            "descricao": "+3 na DC de detecção de Ferro por inimigos (permanente, em todos os contextos).",
        },
    },

    "nao_existe": {
        "nome":        "Não Existe",
        "descricao":   "DES no absoluto. Ferro se move como se o mundo não pudesse registrá-lo.",
        "categoria":   "Furtividade",
        "nivel_minimo": 10,
        "requisito":   {"DES": 20},
        "efeito": {
            "tipo":      "stealth_escala_des",
            "formula":   "(DES - 10) // 2",
            "descricao": "+stealth permanente = (DES−10)//2. Com DES 20: +5 em todos os testes de stealth.",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORIA: FÍSICO
    # Árvore focada em FOR. Carga, força bruta, resistência estrutural.
    # ══════════════════════════════════════════════════════════════════════════

    "carga_extra": {
        "nome":        "Carga Extra",
        "descricao":   "Musculatura adaptada ao peso constante. Capacidade de carga aumenta.",
        "categoria":   "Físico",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {
            "tipo":      "encumbrance_capacidade_bonus",
            "mult_bonus": 0.5,
            "descricao": "Capacidade de carga de cada tier aumenta em +FOR×0.5 kg.",
        },
    },

    "braco_de_ferro": {
        "nome":        "Braço de Ferro",
        "descricao":   "Musculatura que transforma força em poder de ataque. +1 dano em ataques melee.",
        "categoria":   "Físico",
        "nivel_minimo": 2,
        "requisito":   {"FOR": 11},
        "efeito": {
            "tipo":      "dano_bonus_melee",
            "valor":     1,
            "descricao": "+1 dano em ataques melee (MELEE ou FLANQUEANDO).",
        },
    },

    "arrombador": {
        "nome":        "Arrombador",
        "descricao":   "FOR aplicada para vencer obstáculos físicos. Portas, grades e estruturas cedem mais fácil.",
        "categoria":   "Físico",
        "nivel_minimo": 2,
        "requisito":   {"FOR": 12},
        "efeito": {
            "tipo":      "skill_bonus",
            "skill":     "engineering",
            "valor":     2,
            "condicao":  "acao_forcada",
            "descricao": "+2 em testes de engineering quando ação envolve força bruta (arrombar, escalar, empurrar).",
        },
    },

    "portador": {
        "nome":        "Portador",
        "descricao":   "Capacidade de carga além do normal. Tier PESADO não penaliza DES.",
        "categoria":   "Físico",
        "nivel_minimo": 3,
        "requisito":   {"FOR": 13},
        "efeito": {
            "tipo":      "encumbrance_des_excecao",
            "tier_ignorado": "PESADO",
            "descricao": "Tier PESADO não aplica penalidade de DES. SOBRECARREGADO ainda penaliza.",
        },
    },

    "golpe_de_impacto": {
        "nome":        "Golpe de Impacto",
        "descricao":   "Força aplicada em ponto específico. Inimigos atingidos com sucesso crítico são derrubados.",
        "categoria":   "Físico",
        "nivel_minimo": 4,
        "requisito":   {"FOR": 14},
        "efeito": {
            "tipo":      "critico_derruba",
            "descricao": "Acerto crítico do jogador aplica status Derrubado no inimigo (perde próxima ação).",
        },
    },

    "muro_de_carne": {
        "nome":        "Muro de Carne",
        "descricao":   "FOR tão alta que o corpo absorve golpes que deveriam incapacitar.",
        "categoria":   "Físico",
        "nivel_minimo": 5,
        "requisito":   {"FOR": 15},
        "efeito": {
            "tipo":      "dano_maximo_por_hit",
            "teto":      8,
            "descricao": "Nenhum único ataque pode causar mais de 8 dano (exceto críticos do inimigo).",
        },
    },

    "carregador_de_guerra": {
        "nome":        "Carregador de Guerra",
        "descricao":   "Tier SOBRECARREGADO não bloqueia mais posições de combate.",
        "categoria":   "Físico",
        "nivel_minimo": 6,
        "requisito":   {"FOR": 16},
        "efeito": {
            "tipo":      "encumbrance_posicao_imune",
            "descricao": "SOBRECARREGADO não bloqueia posições DISTANCIA e FLANQUEANDO.",
        },
    },

    "golpe_devastador": {
        "nome":        "Golpe Devastador",
        "descricao":   "Toda a FOR concentrada num único ponto. Dano melee escala com a força.",
        "categoria":   "Físico",
        "nivel_minimo": 7,
        "requisito":   {"FOR": 17},
        "efeito": {
            "tipo":      "dano_bonus_for_escala",
            "formula":   "max(0, (FOR-14)//2)",
            "descricao": "+dano melee = max(0,(FOR−14)//2). FOR 16: +1. FOR 18: +2. FOR 20: +3.",
        },
    },

    "colosso": {
        "nome":        "Colosso",
        "descricao":   "A presença física de Ferro intimida. Inimigos com threshold de fuga o atingem mais cedo.",
        "categoria":   "Físico",
        "nivel_minimo": 8,
        "requisito":   {"FOR": 18},
        "efeito": {
            "tipo":      "moral_threshold_bonus",
            "valor":     0.10,
            "descricao": "Threshold de fuga de inimigos biológicos e humanos aumenta em +10% (fogem mais cedo).",
        },
    },

    "maquinario_humano": {
        "nome":        "Maquinário Humano",
        "descricao":   "O encumbrance não existe para Ferro. Nenhum tier reduz DES ou stealth.",
        "categoria":   "Físico",
        "nivel_minimo": 9,
        "requisito":   {"FOR": 19, "portador": True},
        "efeito": {
            "tipo":      "encumbrance_imune_total",
            "descricao": "Encumbrance não aplica penalidade de DES nem de stealth em nenhum tier.",
        },
    },

    "forca_absoluta": {
        "nome":        "Força Absoluta",
        "descricao":   "FOR no limite humano. O corpo de Ferro move o que outros não conseguem imaginar carregar.",
        "categoria":   "Físico",
        "nivel_minimo": 10,
        "requisito":   {"FOR": 20},
        "efeito": {
            "tipo":      "for_escala_total",
            "descricao": "Capacidade de carga = FOR × 3 kg (sem tiers). Dano melee +4 fixo permanente.",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # NOVAS HABILIDADES — Sessão 10
    # ══════════════════════════════════════════════════════════════════════════

    # ── COMBATE ──

    "contra_ataque": {
        "nome":        "Contra-Ataque",
        "descricao":   "O instinto das ruas: cada golpe recebido alimenta o próximo.",
        "categoria":   "Combate",
        "nivel_minimo": 3,
        "requisito":   {"DES": 13},
        "efeito": {"tipo": "ataque_bonus_pos_dano", "valor": 2,
                   "descricao": "+2 no próximo ataque após receber dano no turno anterior."},
    },
    "veterano_de_rua": {
        "nome":        "Veterano de Rua",
        "descricao":   "Passou por tudo. Status negativos não duram tanto.",
        "categoria":   "Combate",
        "nivel_minimo": 2,
        "requisito":   {"FOR": 11},
        "efeito": {"tipo": "status_duracao_reducao", "valor": 1,
                   "descricao": "-1 turno em todos os status negativos (mínimo 1)."},
    },

    # ── SOBREVIVÊNCIA ──

    "resistencia_toxica": {
        "nome":        "Resistência Tóxica",
        "descricao":   "O corpo processou tanta toxina nos esgotos que veneno leve é irrelevante.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 3,
        "requisito":   {"SOB": 13},
        "efeito": {"tipo": "imunidade_veneno_nivel1",
                   "descricao": "Imune a veneno nível 1. Veneno nível 2+ tem duração -1 turno."},
    },
    "intestino_de_aco": {
        "nome":        "Intestino de Aço",
        "descricao":   "Comeu o que tinha a vida toda. Itens deteriorados não causam penalidade.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 3,
        "requisito":   {"SOB": 12},
        "efeito": {"tipo": "consumo_deteriorado_imune",
                   "descricao": "Pode consumir itens deteriorados sem penalidade de envenenamento."},
    },
    "sono_de_ferro": {
        "nome":        "Sono de Ferro",
        "descricao":   "Dorme em qualquer lugar. O descanso sempre rende.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 1,
        "requisito":   {},
        "efeito": {"tipo": "hp_descanso_bonus", "valor": 3,
                   "descricao": "+3 HP ao descansar, mesmo sem abrigo."},
    },
    "cicatrizacao_acelerada": {
        "nome":        "Cicatrização Acelerada",
        "descricao":   "O organismo aprendeu a fechar feridas mais rápido.",
        "categoria":   "Sobrevivência",
        "nivel_minimo": 4,
        "requisito":   {"SOB": 13},
        "efeito": {"tipo": "hemorragia_duracao_reducao", "valor": 1,
                   "descricao": "Hemorragia dura -1 turno (mínimo 1)."},
    },

    # ── EXPLORAÇÃO ──

    "farejador": {
        "nome":        "Farejador",
        "descricao":   "Sentidos treinados revelam armadilhas antes de acioná-las.",
        "categoria":   "Exploração",
        "nivel_minimo": 3,
        "requisito":   {"PER": 12},
        "efeito": {"tipo": "armadilha_deteccao_automatica",
                   "descricao": "Detecta armadilhas automaticamente ao entrar em área."},
    },
    "escalador": {
        "nome":        "Escalador",
        "descricao":   "Anos escalando estruturas deterioradas. Terreno vertical não é obstáculo.",
        "categoria":   "Exploração",
        "nivel_minimo": 2,
        "requisito":   {"DES": 11},
        "efeito": {"tipo": "skill_bonus", "skill": "escalada", "valor": 2,
                   "descricao": "+2 em testes de escalada e terreno vertical."},
    },

    # ── CHIP / TECNOLOGIA ──

    "cache_energetico": {
        "nome":        "Cache Energético",
        "descricao":   "O chip recalibrou os buffers. Mais energia disponível por ciclo.",
        "categoria":   "Chip",
        "nivel_minimo": 3,
        "requisito":   {},
        "efeito": {"tipo": "energy_max_bonus", "valor": 10,
                   "descricao": "Energy máxima permanentemente +10."},
    },
    "processamento_duplo": {
        "nome":        "Processamento Duplo",
        "descricao":   "O chip processa análise e motor em paralelo.",
        "categoria":   "Chip",
        "nivel_minimo": 5,
        "requisito":   {"INT": 12},
        "efeito": {"tipo": "acao_dupla_scan",
                   "descricao": "Pode realizar scan + ação física no mesmo turno sem penalidade."},
    },
    "diagnostico_continuo": {
        "nome":        "Diagnóstico Contínuo",
        "descricao":   "O chip monitora o organismo e aplica microcorreções fora de combate.",
        "categoria":   "Chip",
        "nivel_minimo": 5,
        "requisito":   {"INT": 13},
        "efeito": {"tipo": "regen_hp_fora_combate", "valor": 1, "condicao": "energy >= 50",
                   "descricao": "+1 HP/turno fora de combate enquanto Energy >= 50%."},
    },
    "infiltracao_digital": {
        "nome":        "Infiltração Digital",
        "descricao":   "A interface do chip alcança sistemas sem contato físico.",
        "categoria":   "Chip",
        "nivel_minimo": 6,
        "requisito":   {"INT": 14},
        "efeito": {"tipo": "interface_sem_contato", "valor": 2,
                   "descricao": "Interface eletrônica sem toque, alcance de 2 metros."},
    },
    "compressao_de_dados": {
        "nome":        "Compressão de Dados",
        "descricao":   "O chip otimiza os processos de leitura. Scans custam menos.",
        "categoria":   "Chip",
        "nivel_minimo": 2,
        "requisito":   {},
        "efeito": {"tipo": "scan_energy_reducao", "valor": 5,
                   "descricao": "Scan e análise custam -5% Energy (mínimo 1%)."},
    },
    "firewall_biologico": {
        "nome":        "Firewall Biológico",
        "descricao":   "O chip desenvolveu camadas de proteção contra intrusão.",
        "categoria":   "Chip",
        "nivel_minimo": 4,
        "requisito":   {"INT": 12},
        "efeito": {"tipo": "resistencia_hacking",
                   "descricao": "+4 em testes de resistência a hacking e controle mental."},
    },
    "escudo_eletromagnetico": {
        "nome":        "Escudo Eletromagnético",
        "descricao":   "O chip redistribui a carga. Ataques elétricos causam menos dano.",
        "categoria":   "Chip",
        "nivel_minimo": 4,
        "requisito":   {"INT": 13},
        "efeito": {"tipo": "dano_reducao_multi", "tipos": ["Elétrico"], "valor": 2,
                   "descricao": "-2 de dano elétrico recebido por ataque."},
    },

}

def get_available_passive_skills(
    nivel: int,
    atributos: dict[str, int],
    skills_adquiridas: list[str],
) -> list[dict]:
    """
    Retorna a lista de habilidades passivas elegíveis para o jogador escolher.

    Parâmetros:
      nivel:             int           — nível atual do personagem
      atributos:         dict[str,int] — ex: {"FOR":10,"DES":10,...}
      skills_adquiridas: list[str]     — ids já obtidos

    Retorna lista de dicts com: id, nome, descricao, categoria, efeito, requisito
    """
    elegiveis: list[dict] = []
    for skill_id, data in PASSIVE_SKILLS.items():
        if skill_id in skills_adquiridas:
            continue
        if nivel < data["nivel_minimo"]:
            continue
        req = data.get("requisito", {})
        # Split attribute requirements from prerequisite skill requirements
        attr_req   = {k: v for k, v in req.items() if isinstance(v, int)}
        skill_req  = [k for k, v in req.items() if v is True]
        if not all(atributos.get(a, 0) >= v for a, v in attr_req.items()):
            continue
        if not all(s in skills_adquiridas for s in skill_req):
            continue
        elegiveis.append({"id": skill_id, **data})
    return elegiveis


def apply_passive_skill_effects(
    passive_skills_ids: list[str],
    context: dict,
) -> dict:
    """
    Calcula os efeitos das habilidades passivas adquiridas dado um contexto.

    Parâmetros:
      passive_skills_ids: list[str] — ids das habilidades adquiridas
      context: dict — campos relevantes:
        hp_atual, hp_maximo, posicao, tipo_dano, is_crafting, is_stealth,
        encumbrance_tier, is_trap_check, is_survival_decay

    Retorna dict com modificadores agregados.
    """
    out: dict = {
        "dano_reducao_fisica":          0,
        "dano_reducao_multi":           {},   # tipo → valor
        "dano_bonus_fixo":              0,
        "dano_bonus_melee":             0,
        "critico_limiar":               3,    # padrão — crítico se d20 ≤ 3
        "dc_bonus_defesa":              0,
        "ataque_bonus":                 0,
        "skill_bonuses":                {},
        "armadilha_bonus":              0,
        "crafting_dc_reducao":          0,
        "crafting_falha_salvamento":    0,
        "survival_decay_reducao":       0,
        "hp_exposure_reducao":          0,
        "survival_penalty_divisor":     1,
        "encumbrance_stealth_excecao":  False,
        "encumbrance_stealth_imune":    False,
        "encumbrance_des_excecao":      False,
        "encumbrance_imune_total":      False,
        "encumbrance_capacidade_mult":  0.0,
        "ultimo_suspiro_disponivel":    False,
        "reparo_sem_estacao":           False,
        "breakdown":                    ["HABILIDADES PASSIVAS:"],
    }

    hp_pct: float = (context.get("hp_atual", 1) / context.get("hp_maximo", 1)
                     if context.get("hp_maximo", 1) > 0 else 1.0)
    posicao   = context.get("posicao", "MELEE")
    tipo_dano = context.get("tipo_dano", "")

    for sid in passive_skills_ids:
        data = PASSIVE_SKILLS.get(sid)
        if data is None:
            continue
        ef   = data["efeito"]
        nome = data["nome"]
        tipo = ef["tipo"]

        if tipo == "dano_reducao" and tipo_dano == "Físico":
            out["dano_reducao_fisica"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] dano Físico −{ef['valor']}")

        elif tipo == "dano_reducao_multi":
            for t in ef.get("tipos", []):
                out["dano_reducao_multi"][t] = out["dano_reducao_multi"].get(t, 0) + ef["valor"]
            out["breakdown"].append(f"  [{nome}] dano −{ef['valor']} ({'/'.join(ef.get('tipos',[]))})")

        elif tipo == "critico_limiar_reducao":
            out["critico_limiar"] = max(1, out["critico_limiar"] - ef["valor"])
            out["breakdown"].append(f"  [{nome}] crítico inimigo: d20 ≤ {out['critico_limiar']}")

        elif tipo == "critico_limiar_fixo":
            out["critico_limiar"] = ef["valor"]
            out["breakdown"].append(f"  [{nome}] crítico inimigo: d20 = {ef['valor']} apenas")

        elif tipo == "dano_bonus_fixo":
            out["dano_bonus_fixo"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] +{ef['valor']} dano fixo por ataque")

        elif tipo == "dano_bonus_melee":
            if posicao in ("MELEE", "FLANQUEANDO"):
                out["dano_bonus_melee"] += ef["valor"]
                out["breakdown"].append(f"  [{nome}] +{ef['valor']} dano melee")

        elif tipo == "dc_defesa_bonus_posicao":
            if posicao == "COBERTO":
                out["dc_bonus_defesa"] += ef["valor"]
                out["breakdown"].append(f"  [{nome}] +{ef['valor']} DC defesa (COBERTO)")

        elif tipo == "ataque_bonus_hp_baixo":
            if hp_pct <= 0.30:
                out["ataque_bonus"] += ef["valor"]
                out["breakdown"].append(f"  [{nome}] +{ef['valor']} ataque (HP ≤ 30%)")

        elif tipo == "ataque_surpresa_bonus":
            if context.get("is_surpresa"):
                out["ataque_bonus"] += ef["valor"]
                out["breakdown"].append(f"  [{nome}] +{ef['valor']} ataque surpresa")

        elif tipo == "skill_bonus":
            skill = ef["skill"]
            val   = ef["valor"]
            out["skill_bonuses"][skill] = out["skill_bonuses"].get(skill, 0) + val
            out["breakdown"].append(f"  [{nome}] +{val} {skill}")
            if ef.get("bonus_armadilha") and context.get("is_trap_check"):
                out["armadilha_bonus"] += ef["bonus_armadilha"]
                out["breakdown"].append(f"  [{nome}] +{ef['bonus_armadilha']} detecção armadilha")

        elif tipo == "crafting_dc_reducao":
            out["crafting_dc_reducao"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] DC crafting −{ef['valor']}")

        elif tipo == "crafting_falha_salvamento":
            out["crafting_falha_salvamento"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] falha crafting salva {ef['valor']} material")

        elif tipo == "survival_decay_reducao":
            out["survival_decay_reducao"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] decay survival −{ef['valor']}/turno")

        elif tipo == "survival_penalty_reducao":
            out["survival_penalty_divisor"] = ef["divisor"]
            out["breakdown"].append(f"  [{nome}] DC penalty survival ÷{ef['divisor']}")

        elif tipo == "hp_exposure_reducao":
            out["hp_exposure_reducao"] += ef["valor"]
            out["breakdown"].append(f"  [{nome}] exposição −{ef['valor']} HP/turno")

        elif tipo == "encumbrance_stealth_excecao":
            out["encumbrance_stealth_excecao"] = True
            out["breakdown"].append(f"  [{nome}] PESADO não penaliza stealth")

        elif tipo == "encumbrance_stealth_imune_total":
            out["encumbrance_stealth_imune"] = True
            out["breakdown"].append(f"  [{nome}] encumbrance não penaliza stealth")

        elif tipo == "encumbrance_des_excecao":
            out["encumbrance_des_excecao"] = True
            out["breakdown"].append(f"  [{nome}] PESADO não penaliza DES")

        elif tipo == "encumbrance_imune_total":
            out["encumbrance_imune_total"] = True
            out["breakdown"].append(f"  [{nome}] encumbrance sem penalidade alguma")

        elif tipo == "encumbrance_capacidade_bonus":
            out["encumbrance_capacidade_mult"] += ef["mult_bonus"]
            out["breakdown"].append(f"  [{nome}] capacidade +FOR×{ef['mult_bonus']}kg")

        elif tipo == "hp_zero_prevencao":
            out["ultimo_suspiro_disponivel"] = True
            out["breakdown"].append(f"  [{nome}] HP→0 fica em 1 ({ef['usos_por_capitulo']}×/cap)")

        elif tipo == "reparo_sem_estacao":
            out["reparo_sem_estacao"] = True
            out["breakdown"].append(f"  [{nome}] reparo sem estação (DC+3)")

        else:
            out["breakdown"].append(f"  [{nome}] {ef.get('descricao','')}")

    if len(out["breakdown"]) == 1:
        out["breakdown"].append("  Nenhuma habilidade passiva adquirida.")

    return out

# ─────────────────────────────────────────────────────────────────────────────
# 35. MAPA PROCEDURAL
#
# O mapa é um grafo de áreas exploradas. Cada área é um nó com conexões
# para áreas adjacentes. Persiste em world_map.json.
#
# Schema de um nó:
#   id:               str  — identificador único (ex: "selva_01")
#   nome:             str  — nome narrativo (ex: "Clarão junto ao rio")
#   arco:             int  — 1 | 2 | 3
#   ambiente:         str  — "Selva" | "Urbano" | "Nave" | "Planeta X"
#   capitulo:         int  — capítulo em que foi descoberta
#   turno_descoberta: int  — turno global em que foi descoberta
#   status:           str  — "DESCOBERTA" | "PARCIALMENTE_EXPLORADA" | "TOTALMENTE_EXPLORADA"
#   conexoes:         list[str] — ids de áreas adjacentes (grafo não-dirigido)
#   pontos_de_interesse: list[dict] — itens encontráveis, inimigos, eventos
#   recursos_ocultos: list[dict]   — só visível com habilidade memoria_fotografica
#   notas:            str  — observações do System_Engine (ex: "armadilha ativa aqui")
#   clima_no_momento: str  — clima registrado no turno de descoberta
#   periodo_no_momento: str — período (DIA/NOITE) no turno de descoberta
#
# Fluxo de atualização (System_Engine, todo turno de exploração):
#   1. Identifique a área atual via chapter_tracker.json → capitulo_atual.
#   2. Se a área não existe em world_map.json: chame create_map_node() e adicione.
#   3. Se existe mas status != TOTALMENTE_EXPLORADA: chame update_map_node() com
#      novas informações do turno.
#   4. Ao transitar para área adjacente: adicionar conexão nos dois nós.
# ─────────────────────────────────────────────────────────────────────────────

# Template de tipo de ponto de interesse
MAP_POI_SCHEMA: dict = {
    "tipo":      "str — INIMIGO | ITEM | EVENTO | SAIDA | PERIGO | NPC",
    "nome":      "str — nome narrativo",
    "status":    "str — ATIVO | COLETADO | DERROTADO | RESOLVIDO",
    "descricao": "str — 1 frase",
}

# Status de exploração — ordem de progressão
MAP_STATUS_SEQUENCE: list[str] = [
    "DESCOBERTA",
    "PARCIALMENTE_EXPLORADA",
    "TOTALMENTE_EXPLORADA",
]

# Conexão entre ambiente e prefixo de ID de área
MAP_ID_PREFIXES: dict[str, str] = {
    "Selva":        "selva",
    "Urbano":       "urb",
    "Nave":         "nave",
    "EVA":          "eva",
    "Planeta":      "pla",
}


def create_map_node(
    area_id: str,
    nome: str,
    arco: int,
    ambiente: str,
    capitulo: int,
    turno: int,
    clima: str = "LIMPO",
    periodo: str = "DIA",
    conexoes: list[str] | None = None,
    notas: str = "",
) -> dict:
    """
    Cria um novo nó de área para o mapa procedural.

    Parâmetros:
      area_id:   str — identificador único gerado pelo Architect
      nome:      str — nome narrativo da área
      arco, capitulo, turno: int
      clima, periodo: str — estado do mundo no momento de descoberta
      conexoes:  list[str] — ids de áreas adjacentes (pode ser vazio)
      notas:     str — observações mecânicas

    Retorna: dict pronto para inserir em world_map.json → areas
    """
    return {
        "id":               area_id,
        "nome":             nome,
        "arco":             arco,
        "ambiente":         ambiente,
        "capitulo":         capitulo,
        "turno_descoberta": turno,
        "status":           "DESCOBERTA",
        "conexoes":         conexoes if conexoes is not None else [],
        "pontos_de_interesse": [],
        "recursos_ocultos":    [],   # populado se jogador tem memoria_fotografica
        "notas":            notas,
        "clima_no_momento": clima,
        "periodo_no_momento": periodo,
    }


def update_map_node(node: dict, updates: dict) -> dict:
    """
    Atualiza campos de um nó existente.

    Parâmetros:
      node:    dict — nó atual de world_map.json → areas
      updates: dict — campos a sobrescrever. Chaves válidas:
        status, notas, conexoes (append), pontos_de_interesse (append),
        recursos_ocultos (append)

    Retorna o nó atualizado.
    """
    if "status" in updates:
        curr_idx = MAP_STATUS_SEQUENCE.index(node.get("status", "DESCOBERTA"))
        new_idx  = MAP_STATUS_SEQUENCE.index(updates["status"])
        if new_idx > curr_idx:     # status só avança, nunca retrocede
            node["status"] = updates["status"]

    if "notas" in updates and updates["notas"]:
        existing = node.get("notas", "")
        node["notas"] = (existing + " | " + updates["notas"]).strip(" | ")

    if "conexoes" in updates:
        for conn in updates["conexoes"]:
            if conn not in node["conexoes"]:
                node["conexoes"].append(conn)

    if "pontos_de_interesse" in updates:
        existing_nomes = {p["nome"] for p in node.get("pontos_de_interesse", [])}
        for poi in updates["pontos_de_interesse"]:
            if poi["nome"] not in existing_nomes:
                node["pontos_de_interesse"].append(poi)
                existing_nomes.add(poi["nome"])

    if "recursos_ocultos" in updates:
        existing_nomes = {r["nome"] for r in node.get("recursos_ocultos", [])}
        for rec in updates["recursos_ocultos"]:
            if rec["nome"] not in existing_nomes:
                node["recursos_ocultos"].append(rec)

    return node


def get_map_summary(areas: list[dict]) -> dict:
    """
    Gera um resumo do mapa para exibir no HUD.

    Retorna dict com:
      total_areas:     int
      por_status:      dict[str, int]
      por_arco:        dict[int, int]
      conexoes_totais: int
      breakdown:       list[str]
    """
    por_status: dict[str, int] = {}
    por_arco:   dict[int, int] = {}
    conexoes:   int = 0
    for area in areas:
        s = area.get("status", "DESCOBERTA")
        por_status[s] = por_status.get(s, 0) + 1
        a = area.get("arco", 1)
        por_arco[a]   = por_arco.get(a, 0) + 1
        conexoes     += len(area.get("conexoes", []))

    breakdown: list[str] = [
        f"MAPA: {len(areas)} área(s) descoberta(s)",
        f"  Descoberta:          {por_status.get('DESCOBERTA', 0)}",
        f"  Parcialm. explorada: {por_status.get('PARCIALMENTE_EXPLORADA', 0)}",
        f"  Totalm. explorada:   {por_status.get('TOTALMENTE_EXPLORADA', 0)}",
        f"  Conexões:            {conexoes // 2}",  # cada conexão é bidirecional
    ]
    return {
        "total_areas":     len(areas),
        "por_status":      por_status,
        "por_arco":        por_arco,
        "conexoes_totais": conexoes // 2,
        "breakdown":       breakdown,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 36. TABELAS DE TIERS DE EXPANSÃO (GUARDRAILS) (I-12)
#
# Usado pelo Expansion Manager para validar e equilibrar conteúdo gerado.
# ─────────────────────────────────────────────────────────────────────────────

CREATURE_TIERS = {
    "fraco": {"hp": 8, "dano": 2, "dc": 10, "bonus_racial": 0, "moral": "40%"},
    "medio": {"hp": 15, "dano": 4, "dc": 12, "bonus_racial": 2, "moral": "30%"},
    "forte": {"hp": 35, "dano": 8, "dc": 15, "bonus_racial": 4, "moral": "20%"},
    "lendario": {"hp": 80, "dano": 15, "dc": 18, "bonus_racial": 6, "moral": "Nunca"}
}

ITEM_TIERS = {
    "fraco": {"durabilidade": 10, "quantidade_drop": 1, "peso_kg": 0.1},
    "medio": {"durabilidade": 25, "quantidade_drop": 2, "peso_kg": 0.5},
    "forte": {"durabilidade": 50, "quantidade_drop": 3, "peso_kg": 1.0},
    "lendario": {"durabilidade": 100, "quantidade_drop": 1, "peso_kg": 2.0}
}