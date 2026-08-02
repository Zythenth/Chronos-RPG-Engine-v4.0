"""
multi_roll.py — Sistema de Rolagem Multi-Dados (Chronos RPG Engine)

USO:
    python multi_roll.py <dado> <valor_atributo>

EXEMPLOS:
    python multi_roll.py d20 10     →  DES 10(+1): [14, 7] → USADO: 14 (MELHOR)
    python multi_roll.py d4  10     →  FOR 10(+1): [3, 1] → USADO: 3 (MELHOR)
    python multi_roll.py d20 6      →  d20 6(−1): [5, 18] → USADO: 5 (PIOR)
    python multi_roll.py d20 8      →  d20 8: [11] → USADO: 11 (ÚNICO)
    python multi_roll.py d4  1      →  ENEMY_D4: [3] + RACIAL — (inimigo sempre 1x)
"""

import sys
import io
import importlib.util as _ilu
import os

try:
    from chronos.domain import dice as _dice
except ModuleNotFoundError as exc:
    if exc.name != "chronos":
        raise
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from chronos.domain import dice as _dice

_HERE = os.path.dirname(os.path.abspath(__file__))

_d20_spec = _ilu.spec_from_file_location("d20", os.path.join(_HERE, "d20.py"))
_d20 = _ilu.module_from_spec(_d20_spec)
_d20_spec.loader.exec_module(_d20)

_d4_spec = _ilu.spec_from_file_location("d4", os.path.join(_HERE, "d4.py"))
_d4 = _ilu.module_from_spec(_d4_spec)
_d4_spec.loader.exec_module(_d4)

# Força UTF-8 no stdout — necessário no Windows (cp1252 não suporta →)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

# Tabela: valor_atributo → (n_rolagens, criterio)
# criterio: 'melhor' | 'pior' | 'unico'
ROLL_TABLE = {
    attribute: rule
    for attribute, rule in enumerate(_dice.MULTI_ROLL_TABLE, start=1)
}

# Modificador = atributo − 10 (regra oficial, mecanicas-oficiais.md §1)
def _calc_mod(attr_val: int) -> int:
    return _dice.calc_modifier(attr_val)

def _fmt_mod(mod: int) -> str:
    return _dice.modifier_suffix(mod)

def rolar(faces, n):
    if faces == 20:
        return [_d20.rolar_d20() for _ in range(n)]
    elif faces == 4:
        return [_d4.rolar_d4() for _ in range(n)]
    return []


def do_multi_roll(faces: int, attr_val: int) -> tuple:
    """
    API pública de multi-roll — pode ser importada por system_engine.py.

    Consulta a ROLL_TABLE pelo valor bruto do atributo, rola N dados de
    `faces` faces via secrets.choice e seleciona o melhor ou pior resultado.

    Retorna (resultados, usado, criterio, sufixo_mod):
      - resultados : list[int]  — todos os valores rolados
      - usado      : int        — valor selecionado (melhor, pior ou único)
      - criterio   : str        — 'MELHOR' | 'PIOR' | 'ÚNICO'
      - sufixo_mod : str        — string de modificador, ex: '(+4)' ou ''
    """
    return _dice.multi_roll(faces, attr_val, roller=rolar)


def main():
    if len(sys.argv) < 3:
        print("USO: python multi_roll.py <d20|d4> <valor_atributo> [bonus]")
        print("     python multi_roll.py d4 enemy  (inimigo — sempre 1×)")
        sys.exit(1)

    dado_arg = sys.argv[1].lower()
    attr_arg  = sys.argv[2].lower()

    # Modo inimigo: sempre 1× d4, sem multi-roll
    if attr_arg == 'enemy':
        resultado = _d4.rolar_d4()
        print(f"D4_ENEMY: [{resultado}]  ← some +damage_bonus_racial manualmente")
        sys.exit(0)

    # Valida dado
    if dado_arg == 'd20':
        faces = 20
    elif dado_arg == 'd4':
        faces = 4
    else:
        print(f"ERRO: dado inválido '{dado_arg}'. Use d20 ou d4.")
        sys.exit(1)

    # Valida atributo
    try:
        attr_val = int(attr_arg)
        if attr_val < 1 or attr_val > 20:
            raise ValueError
    except ValueError:
        print(f"ERRO: valor_atributo deve ser inteiro entre 1 e 20. Recebido: '{attr_arg}'")
        sys.exit(1)

    # Valida bônus opcional
    bonus = 0
    if len(sys.argv) >= 4:
        try:
            bonus = int(sys.argv[3])
        except ValueError:
            print(f"ERRO: bônus deve ser um inteiro. Recebido: '{sys.argv[3]}'")
            sys.exit(1)

    # Rola e seleciona pela regra central
    resultados, usado, label, sufixo = do_multi_roll(faces, attr_val)
    modificador = _calc_mod(attr_val)

    # Calcula total final = resultado_selecionado + modificador + bônus (U-12)
    total = usado + modificador + bonus

    # Saída formatada — pronta para colar no log/HUD
    sufixo_str = f" {sufixo}" if sufixo else ""
    mod_str = f" + mod({modificador:+})" if modificador != 0 else ""
    bonus_str = f" + bonus({bonus:+})" if bonus != 0 else ""
    print(f"{dado_arg.upper()} {attr_val}{sufixo_str}: {resultados} → USADO: {usado} ({label}){mod_str}{bonus_str} = TOTAL: {total}")

if __name__ == "__main__":
    main()