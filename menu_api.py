import json
from typing import Any, Optional

from src.extract import Extract


def _ler_opcional(mensagem: str) -> Optional[str]:
    valor = input(mensagem).strip()
    return valor or None


def _ler_pagina() -> int:
    while True:
        try:
            pagina = int(input("Página [1]: ").strip() or "1")
            if pagina < 1:
                raise ValueError
            return pagina
        except ValueError:
            print("Informe um número de página válido (maior ou igual a 1).")


def _mostrar_resultado(resultado: Any) -> None:
    if resultado is None:
        print("Nenhum resultado foi retornado.")
        return
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


def menu_interativo(cliente_api: Extract) -> None:
    while True:
        print("""
========== Portal de Dados Abertos ==========
1. Listar conjuntos de dados
2. Detalhar conjunto de dados
3. Listar tags de um conjunto
4. Listar observância legal
5. Listar ODS
6. Listar formatos
7. Consultar solicitações
8. Listar reúsos
9. Detalhar reúso
10. Consultar temas
11. Consultar tags
12. Listar organizações
13. Detalhar organização
0. Sair
==============================================
""")
        opcao = input("Escolha uma opção: ").strip()

        try:
            if opcao == "1":
                resultado = cliente_api.listar_conjuntos_de_dados(
                    pagina=_ler_pagina(),
                    nome_conjunto_dados=_ler_opcional("Nome (opcional): "),
                    dados_abertos=_ler_opcional("Apenas dados abertos? (s/n, opcional): "),
                    id_organizacao=_ler_opcional("ID da organização (opcional): "),
                )
            elif opcao == "2":
                resultado = cliente_api.detalhar_conjunto_de_dados(input("ID do conjunto: ").strip())
            elif opcao == "3":
                resultado = cliente_api.listar_tags_conjunto_de_dados(input("ID do conjunto: ").strip())
            elif opcao == "4":
                resultado = cliente_api.listar_observancia_legal()
            elif opcao == "5":
                resultado = cliente_api.listar_objetivos_desenvolvimento_sustentavel()
            elif opcao == "6":
                resultado = cliente_api.listar_formatos()
            elif opcao == "7":
                resultado = cliente_api.consultar_solicitacoes(
                    data_abertura=_ler_opcional("Data de abertura (YYYY-MM-DD, opcional): "),
                    tipo_solicitacao=_ler_opcional("Tipo (opcional): "),
                    status_solicitacao=_ler_opcional("Status (opcional): "),
                )
            elif opcao == "8":
                resultado = cliente_api.listar_reusos(
                    nome_reuso=_ler_opcional("Nome do reúso (opcional): "),
                    nome_autor=_ler_opcional("Nome do autor (opcional): "),
                    id_organizacao=_ler_opcional("ID da organização (opcional): "),
                )
            elif opcao == "9":
                resultado = cliente_api.detalhar_reuso(int(input("ID do reúso: ").strip()))
            elif opcao == "10":
                resultado = cliente_api.consultar_temas()
            elif opcao == "11":
                resultado = cliente_api.consultar_tags(input("Nome da tag: ").strip())
            elif opcao == "12":
                resultado = cliente_api.listar_organizacoes(
                    pagina=_ler_pagina(),
                    nome=_ler_opcional("Nome da organização (opcional): "),
                )
            elif opcao == "13":
                resultado = cliente_api.detalhar_organizacao(input("ID da organização: ").strip())
            elif opcao == "0":
                print("Encerrando...")
                return
            else:
                print("Opção inválida.")
                continue

            _mostrar_resultado(resultado)
        except ValueError:
            print("Entrada inválida. Verifique os valores informados e tente novamente.")
        except KeyboardInterrupt:
            print("\nEncerrando...")
            return


if __name__ == "__main__":
    try:
        cliente_api = Extract()
    except ValueError as erro:
        print(erro)
    else:
        menu_interativo(cliente_api)
