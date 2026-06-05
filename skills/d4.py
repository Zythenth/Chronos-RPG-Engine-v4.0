import secrets

def rolar_d4():
    resultado = secrets.choice(range(1, 5))
    return resultado

if __name__ == "__main__":
    print("Rolando os dados...")
    valor_tirado = rolar_d4()
    print(f"O resultado do seu D4 foi: {valor_tirado}")