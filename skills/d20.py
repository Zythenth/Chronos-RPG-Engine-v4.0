import os
import secrets
import sys

try:
    from chronos.domain import dice as _dice
except ModuleNotFoundError as exc:
    if exc.name != "chronos":
        raise
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from chronos.domain import dice as _dice

def rolar_d20():
    return _dice.roll_d20(choice=secrets.choice)

if __name__ == "__main__":
    print("Rolando os dados...")
    valor_tirado = rolar_d20()
    print(f"O resultado do seu D20 foi: {valor_tirado}")