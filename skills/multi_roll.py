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

import secrets
import sys
import io

# Força UTF-8 no stdout — necessário no Windows (cp1252 não suporta →)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

# Tabela: valor_atributo → (n_rolagens, criterio)
# criterio: 'melhor' | 'pior' | 'unico'
ROLL_TABLE = {
    1:  (5, 'pior'),
    2:  (4, 'pior'),
    3:  (4, 'pior'),
    4:  (3, 'pior'),
    5:  (3, 'pior'),
    6:  (2, 'pior'),
    7:  (2, 'pior'),
    8:  (1, 'unico'),
    9:  (1, 'unico'),
    10: (2, 'melhor'),
    11: (2, 'melhor'),
    12: (3, 'melhor'),
    13: (3, 'melhor'),
    14: (4, 'melhor'),
    15: (4, 'melhor'),
    16: (5, 'melhor'),
    17: (5, 'melhor'),
    18: (6, 'melhor'),
    19: (6, 'melhor'),
    20: (7, 'melhor'),
}

# Modificador = atributo − 10 (regra oficial, mecanicas-oficiais.md §1)
def _calc_mod(attr_val: int) -> int:
    return attr_val - 10

def _fmt_mod(mod: int) -> str:
    if mod == 0: return ''
    return f'({mod:+})'

def rolar(faces, n):
    return [secrets.choice(range(1, faces + 1)) for _ in range(n)]

def main():
    if len(sys.argv) < 3:
        print("USO: python multi_roll.py <d20|d4> <valor_atributo> [bonus]")
        print("     python multi_roll.py d4 enemy  (inimigo — sempre 1×)")
        sys.exit(1)

    dado_arg = sys.argv[1].lower()
    attr_arg  = sys.argv[2].lower()

    # Modo inimigo: sempre 1× d4, sem multi-roll
    if attr_arg == 'enemy':
        resultado = secrets.choice(range(1, 5))
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

    # Consulta tabela
    n_rolls, criterio = ROLL_TABLE.get(attr_val, (1, 'unico'))
    modificador = _calc_mod(attr_val)
    sufixo = _fmt_mod(modificador)

    # Rola
    resultados = rolar(faces, n_rolls)

    # Seleciona
    if criterio == 'melhor':
        usado = max(resultados)
        label = 'MELHOR'
    elif criterio == 'pior':
        usado = min(resultados)
        label = 'PIOR'
    else:
        usado = resultados[0]
        label = 'ÚNICO'

    # Calcula total final = resultado_selecionado + modificador + bônus (U-12)
    total = usado + modificador + bonus

    # Saída formatada — pronta para colar no log/HUD
    sufixo_str = f" {sufixo}" if sufixo else ""
    mod_str = f" + mod({modificador:+})" if modificador != 0 else ""
    bonus_str = f" + bonus({bonus:+})" if bonus != 0 else ""
    print(f"{dado_arg.upper()} {attr_val}{sufixo_str}: {resultados} → USADO: {usado} ({label}){mod_str}{bonus_str} = TOTAL: {total}")

if __name__ == "__main__":
    main()