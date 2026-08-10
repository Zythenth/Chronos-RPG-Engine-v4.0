"""Pure survival-cost rules shared by the Chronos engine."""

from typing import Optional


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
