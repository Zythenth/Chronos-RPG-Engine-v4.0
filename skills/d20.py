import secrets

def rolar_d20():
    resultado = secrets.choice(range(1, 21))
    return resultado

if __name__ == "__main__":
    print("Rolando os dados...")
    valor_tirado = rolar_d20()
    print(f"O resultado do seu D20 foi: {valor_tirado}")