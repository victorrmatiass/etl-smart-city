"""Servidor MCP stdio para consultar as tabelas EMLURB no Neon."""

from fastmcp import FastMCP

from assistente import AssistenteGPT
from banco import BancoComLimite
from src.config import (
    GPT_API_KEY,
    GPT_BASE_URL,
    MODELO,
    NEON_DATABASE_URL,
    TABELAS_MCP,
)

banco = BancoComLimite(NEON_DATABASE_URL, limite=10, tabelas_permitidas=TABELAS_MCP)
gpt = AssistenteGPT(GPT_API_KEY, modelo=MODELO, base_url=GPT_BASE_URL)
mcp = FastMCP("Smart City - Neon + GPT")


@mcp.tool
def listar_tabelas() -> list[str]:
    """Lista as tabelas do pipeline Smart City disponíveis no banco Neon."""
    return banco.listar_tabelas()


@mcp.tool
def descrever_tabela(tabela: str) -> list[dict]:
    """Mostra todas as colunas e os tipos de uma tabela disponível."""
    return banco.descrever_tabela(tabela)


@mcp.tool
def executar_select(sql: str) -> list[dict]:
    """Executa um único SELECT somente leitura e devolve no máximo 10 linhas."""
    return banco.consultar(sql)


@mcp.tool
def contar_linhas(tabela: str) -> int:
    """Conta quantas linhas uma tabela disponível possui."""
    return banco.contar_linhas(tabela)


@mcp.tool
def perguntar_ao_banco(pergunta: str) -> dict:
    """Gera um SELECT com IA, consulta o Neon e explica o resultado em português."""
    sql = gpt.gerar_sql(pergunta, banco.esquema_completo())
    dados = banco.consultar(sql)
    resposta = gpt.explicar_resultado(pergunta, dados)
    return {"sql": sql, "dados": dados, "resposta": resposta}


if __name__ == "__main__":
    mcp.run()
