"""Acesso somente leitura ao banco Neon usado pelo servidor MCP."""

from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg import sql as psycopg_sql


class BancoNeon:
    """Consulta tabelas PostgreSQL do Neon sem permitir escrita."""

    def __init__(
        self,
        url_conexao: str,
        tabelas_permitidas: Sequence[str] | None = None,
    ) -> None:
        self.url_conexao = url_conexao
        self.tabelas_permitidas = (
            tuple(tabelas_permitidas) if tabelas_permitidas is not None else None
        )

    def _conectar(self) -> psycopg.Connection:
        if not self.url_conexao:
            raise ValueError("Configure NEON_DATABASE_URL no arquivo .env.")
        conexao = psycopg.connect(self.url_conexao, connect_timeout=15)
        conexao.read_only = True
        return conexao

    @staticmethod
    def _validar_select(comando: str) -> None:
        texto = comando.strip()
        sem_ponto_final = texto[:-1] if texto.endswith(";") else texto
        if not sem_ponto_final or ";" in sem_ponto_final:
            raise ValueError("Envie exatamente uma consulta SQL.")
        primeiro_termo = sem_ponto_final.split(None, 1)[0].upper()
        if primeiro_termo not in {"SELECT", "WITH"}:
            raise ValueError("Apenas consultas SELECT são permitidas.")

    def consultar(
        self, comando: str, parametros: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Executa um SELECT e devolve as linhas como dicionários."""
        self._validar_select(comando)
        with self._conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(comando, parametros)
                if cursor.description is None:
                    return []
                colunas = [coluna.name for coluna in cursor.description]
                return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]

    def listar_tabelas(self) -> list[str]:
        """Lista as tabelas públicas disponibilizadas por este servidor."""
        comando = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        parametros: tuple[Any, ...] | None = None
        if self.tabelas_permitidas is not None:
            comando += " AND table_name = ANY(%s)"
            parametros = (list(self.tabelas_permitidas),)
        comando += " ORDER BY table_name"
        return [linha["table_name"] for linha in self.consultar(comando, parametros)]

    def _validar_tabela(self, tabela: str) -> None:
        if (
            self.tabelas_permitidas is not None
            and tabela not in self.tabelas_permitidas
        ):
            raise ValueError(
                f"Tabela '{tabela}' não está disponível neste servidor MCP."
            )
        with self._conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                    """,
                    (tabela,),
                )
                existe = cursor.fetchone()[0]
        if not existe:
            raise ValueError(f"Tabela '{tabela}' não existe.")

    def descrever_tabela(self, tabela: str) -> list[dict[str, str]]:
        """Retorna todas as colunas e os tipos de uma tabela permitida."""
        self._validar_tabela(tabela)
        with self._conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (tabela,),
                )
                return [
                    {"coluna": coluna, "tipo": tipo}
                    for coluna, tipo in cursor.fetchall()
                ]

    def esquema_completo(self) -> str:
        """Monta o esquema textual enviado ao modelo gerador de SQL."""
        partes = []
        for tabela in self.listar_tabelas():
            colunas = self.descrever_tabela(tabela)
            lista = ", ".join(
                f"{coluna['coluna']} ({coluna['tipo']})" for coluna in colunas
            )
            partes.append(f"- {tabela}: {lista}")
        return "\n".join(partes)

    def contar_linhas(self, tabela: str) -> int:
        """Conta as linhas de uma tabela após validar seu nome."""
        self._validar_tabela(tabela)
        comando = psycopg_sql.SQL("SELECT COUNT(*) AS total FROM {}").format(
            psycopg_sql.Identifier(tabela)
        )
        with self._conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(comando)
                return int(cursor.fetchone()[0])


class BancoComLimite(BancoNeon):
    """BancoNeon que devolve no máximo dez linhas por consulta."""

    def __init__(
        self,
        url_conexao: str,
        limite: int = 10,
        tabelas_permitidas: Sequence[str] | None = None,
    ) -> None:
        super().__init__(url_conexao, tabelas_permitidas)
        if limite < 1:
            raise ValueError("O limite deve ser maior que zero.")
        self.limite = min(limite, 10)

    def consultar(
        self, comando: str, parametros: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        linhas = super().consultar(comando, parametros)
        return linhas[: self.limite]
