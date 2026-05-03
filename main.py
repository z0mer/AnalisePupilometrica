from codigos_tcc import anomalias, anomalias_individuais, individual, media_pilotos, sincronizacao


def exibir_menu():
    print("\n" + "=" * 60)
    print("MENU PRINCIPAL")
    print("=" * 60)
    print("1. Rodar individual.py")
    print("2. Rodar media_pilotos.py")
    print("3. Rodar anomalias.py")
    print("4. Rodar anomalias_individuais.py")
    print("5. Rodar sincronizacao.py  ← execute antes dos demais")
    print("0. Sair")


def main():
    opcoes = {
        "1": ("individual.py",            individual.executar),
        "2": ("media_pilotos.py",         media_pilotos.executar),
        "3": ("anomalias.py",             anomalias.executar),
        "4": ("anomalias_individuais.py", anomalias_individuais.executar),
        "5": ("sincronizacao.py",         sincronizacao.executar),
    }

    while True:
        exibir_menu()
        escolha = input("Escolha uma opcao: ").strip()

        if escolha == "0":
            print("Encerrando.")
            break

        if escolha not in opcoes:
            print("Opcao invalida. Tente novamente.")
            continue

        nome_script, funcao = opcoes[escolha]
        print(f"\nExecutando {nome_script}...\n")
        try:
            funcao()
        except Exception as erro:
            print(f"\nErro ao executar {nome_script}: {erro}")


if __name__ == "__main__":
    main()
