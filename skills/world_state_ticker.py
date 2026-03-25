#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
world_state_ticker.py — Ciclo de Mundo (Clima, Período, Patrulhas)
Chronos RPG Engine v4.0

Executa a cada turno (antes do Architect) para:
  1. Avançar o período do dia (DIA → TARDE → NOITE → MADRUGADA → DIA)
  2. Atualizar o clima aleatoriamente (20% chance de mudança por turno)
  3. Atualizar patrulhas e eventos no chapter_tracker.json

Exporta para importação pelo game_master.py:
  WEATHER_EFFECTS — dict clima → efeito narrativo
  PERIOD_EFFECTS  — dict período → efeito narrativo

USO:
  python world_state_ticker.py           # execução normal
  python world_state_ticker.py --quiet   # sem output (modo pipeline)
  python world_state_ticker.py --status  # exibe estado atual sem modificar
"""

import os, sys, json, secrets, argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_CT_PATH   = os.path.join(_STATE_DIR, "chapter_tracker.json")

# ─────────────────────────────────────────────────────────────────────────────
# Tabelas de Efeitos (importadas pelo game_master.py)
# ─────────────────────────────────────────────────────────────────────────────

WEATHER_EFFECTS = {
    "LIMPO":         "",
    "NEBLINA":       "Visibilidade reduzida. Testes de Percepção com desvantagem.",
    "CHUVA":         "Solo escorregadio. Testes de DES com penalidade. Trilhas apagadas.",
    "TEMPESTADE":    "Vento forte. Barulho encobre movimentos. Combate à distância prejudicado.",
    "RADIAÇÃO":      "Zona contaminada. -1 HP por turno sem proteção. Chip alerta.",
    "CALOR EXTREMO": "Desidratação acelerada. SEDE decai 2x mais rápido.",
    "FRIO INTENSO":  "Hipotermia ameaça. EXAUSTÃO decai 2x mais rápido sem abrigo.",
    "VENTOS ÁCIDOS": "Equipamentos sofrem desgaste. Durabilidade -1 por exposição.",
}

PERIOD_EFFECTS = {
    "DIA":        "",
    "TARDE":      "Calor do sol no ápice. Vigilância humana no pico.",
    "NOITE":      "Visibilidade reduzida. Criaturas noturnas ativas. Patrulhas intensificadas.",
    "MADRUGADA":  "Menor vigilância. Temperatura mínima. Névoa provável.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Sequência de períodos e pool de climas ponderados
# ─────────────────────────────────────────────────────────────────────────────

_PERIOD_CYCLE = ["DIA", "TARDE", "NOITE", "MADRUGADA"]
_PERIOD_DURATION = 6   # turnos por período antes de avançar
_WEATHER_CHANGE_CHANCE = 20  # % de chance de mudança de clima por turno

_WEATHER_POOL = [
    ("LIMPO",        50),
    ("NEBLINA",      15),
    ("CHUVA",        15),
    ("TEMPESTADE",    8),
    ("RADIAÇÃO",      5),
    ("CALOR EXTREMO", 4),
    ("FRIO INTENSO",  2),
    ("VENTOS ÁCIDOS", 1),
]


def _weighted_choice(pool, exclude=""):
    """Escolhe clima ponderado, evitando o clima atual quando possível."""
    filtered = [(n, w) for n, w in pool if n != exclude]
    if not filtered:
        filtered = pool
    total = sum(w for _, w in filtered)
    r = secrets.randbelow(total)
    acc = 0
    for name, w in filtered:
        acc += w
        if r < acc:
            return name
    return filtered[-1][0]


# ─────────────────────────────────────────────────────────────────────────────
# I/O do chapter_tracker
# ─────────────────────────────────────────────────────────────────────────────

def _load_ct():
    if not os.path.exists(_CT_PATH):
        return {}
    try:
        return json.load(open(_CT_PATH, encoding="utf-8"))
    except Exception:
        return {}


def _save_ct(ct):
    os.makedirs(_STATE_DIR, exist_ok=True)
    with open(_CT_PATH, "w", encoding="utf-8") as f:
        json.dump(ct, f, ensure_ascii=False, indent=2)


def _ensure_world_state(ct):
    """Garante que world_state existe no chapter_tracker com defaults."""
    if "world_state" not in ct:
        ct["world_state"] = {}
    ws = ct["world_state"]
    if "clima" not in ws or not isinstance(ws.get("clima"), dict):
        ws["clima"] = {"estado_atual": "LIMPO", "turno_mudanca": 0}
    if "periodo" not in ws or not isinstance(ws.get("periodo"), dict):
        ws["periodo"] = {"estado_atual": "DIA", "turnos_no_periodo": 0}
    if "patrulhas" not in ws or not isinstance(ws.get("patrulhas"), dict):
        ws["patrulhas"] = {"ativas": True, "nivel": "BAIXO", "ultimo_avistamento": 0}
    return ct


# ─────────────────────────────────────────────────────────────────────────────
# Lógica de Tick
# ─────────────────────────────────────────────────────────────────────────────

def _tick_periodo(ws):
    """Avança período após _PERIOD_DURATION turnos. Retorna (periodo, mudou)."""
    pd = ws["periodo"]
    atual = pd.get("estado_atual", "DIA")
    turnos = int(pd.get("turnos_no_periodo", 0)) + 1

    if turnos >= _PERIOD_DURATION:
        try:
            idx = _PERIOD_CYCLE.index(atual)
        except ValueError:
            idx = 0
        novo = _PERIOD_CYCLE[(idx + 1) % len(_PERIOD_CYCLE)]
        pd["estado_atual"] = novo
        pd["turnos_no_periodo"] = 0
        return novo, True
    else:
        pd["turnos_no_periodo"] = turnos
        return atual, False


def _tick_clima(ws):
    """Muda clima com _WEATHER_CHANGE_CHANCE%. Retorna (clima, mudou)."""
    cd = ws["clima"]
    atual = cd.get("estado_atual", "LIMPO")

    if secrets.randbelow(100) < _WEATHER_CHANGE_CHANCE:
        novo = _weighted_choice(_WEATHER_POOL, exclude=atual)
        cd["estado_atual"] = novo
        return novo, True
    return atual, False


def _tick_patrulhas(ws, periodo):
    """Atualiza nível de patrulhas por período do dia."""
    pat = ws["patrulhas"]
    nivel_map = {
        "DIA":       "BAIXO",
        "TARDE":     "MEDIO",
        "NOITE":     "ALTO",
        "MADRUGADA": "MEDIO",
    }
    pat["ativas"] = True
    pat["nivel"] = nivel_map.get(periodo, "BAIXO")


# ─────────────────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────────────────

def tick(quiet=False):
    """Executa tick completo. Retorna dict com estado atualizado."""
    ct = _load_ct()
    ct = _ensure_world_state(ct)
    ws = ct["world_state"]

    novo_periodo, periodo_mudou = _tick_periodo(ws)
    novo_clima,   clima_mudou   = _tick_clima(ws)
    _tick_patrulhas(ws, novo_periodo)

    _save_ct(ct)

    if not quiet:
        p_tag = " (MUDOU)" if periodo_mudou else ""
        c_tag = " (MUDOU)" if clima_mudou else ""
        nivel = ws["patrulhas"].get("nivel", "?")
        print(f"  [Ticker] Período: {novo_periodo}{p_tag}")
        print(f"  [Ticker] Clima:   {novo_clima}{c_tag}")
        print(f"  [Ticker] Patrulhas: {nivel}")

    return {
        "periodo":       novo_periodo,
        "clima":         novo_clima,
        "periodo_mudou": periodo_mudou,
        "clima_mudou":   clima_mudou,
        "patrulhas":     ws["patrulhas"],
    }


def status():
    """Exibe estado atual sem modificar nada."""
    ct = _load_ct()
    ws = ct.get("world_state", {})
    clima   = ws.get("clima",   {}).get("estado_atual", "?")
    periodo = ws.get("periodo", {}).get("estado_atual", "?")
    turnos_p = ws.get("periodo", {}).get("turnos_no_periodo", 0)
    pat = ws.get("patrulhas", {})

    print(f"\n{'─'*40}")
    print(f"  ESTADO DO MUNDO")
    print(f"{'─'*40}")
    print(f"  Período:    {periodo}  ({turnos_p}/{_PERIOD_DURATION} turnos)")
    efeito_p = PERIOD_EFFECTS.get(periodo, "")
    if efeito_p:
        print(f"  ↳ {efeito_p}")
    print(f"  Clima:      {clima}")
    efeito_c = WEATHER_EFFECTS.get(clima, "")
    if efeito_c:
        print(f"  ↳ {efeito_c}")
    print(f"  Patrulhas:  {pat.get('nivel','?')} (ativas={pat.get('ativas',False)})")
    print(f"{'─'*40}")


def main():
    parser = argparse.ArgumentParser(
        prog="world_state_ticker.py",
        description="Chronos RPG — Tick do ciclo de mundo"
    )
    parser.add_argument("--quiet",  action="store_true", help="Sem output")
    parser.add_argument("--status", action="store_true", help="Exibe estado atual")
    args = parser.parse_args()

    if args.status:
        status()
        return

    tick(quiet=args.quiet)


if __name__ == "__main__":
    main()