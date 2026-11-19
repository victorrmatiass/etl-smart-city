"""Validação em memória das ferramentas MCP contra o Neon configurado."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client

from servidor import mcp


async def main() -> None:
    async with Client(mcp) as cliente:
        ferramentas = await cliente.list_tools()
        nomes = {ferramenta.name for ferramenta in ferramentas}
        esperadas = {
            "listar_tabelas",
            "descrever_tabela",
            "executar_select",
            "contar_linhas",
            "perguntar_ao_banco",
        }
        if nomes != esperadas:
            raise AssertionError(f"Ferramentas inesperadas: {sorted(nomes)}")

        resposta_tabelas = await cliente.call_tool("listar_tabelas", {})
        tabelas = resposta_tabelas.data
        if not tabelas:
            raise AssertionError("Nenhuma tabela do projeto foi encontrada no Neon.")

        contagens = {}
        for tabela in tabelas:
            resposta = await cliente.call_tool("contar_linhas", {"tabela": tabela})
            contagens[tabela] = resposta.data

        amostra = await cliente.call_tool(
            "executar_select",
            {"sql": "SELECT * FROM emlurb_156_demandas ORDER BY id_demanda"},
        )
        if len(amostra.data) > 10:
            raise AssertionError("BancoComLimite devolveu mais de 10 linhas.")

        print("Ferramentas:", ", ".join(sorted(nomes)))
        print("Contagens:", contagens)
        print("Linhas na amostra limitada:", len(amostra.data))
        print("Servidor MCP validado com sucesso.")


if __name__ == "__main__":
    asyncio.run(main())
