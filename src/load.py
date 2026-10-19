import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import certifi
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ_PROJETO / ".env")


class Load:
    """
    Responsável por carregar os dados do pipeline.

    - MongoDB Atlas: dado bruto, exatamente como veio do portal;
    - SQLite (local): dado transformado, para consulta no VS Code;
    - PostgreSQL do Neon: dado transformado, consumido pelo app/dashboard.
    """

    # Configurações do MongoDB
    MONGODB_URI_ENV = "MONGODB_URI"
    MONGO_DB = "SMART_CITY"
    MONGO_COLLECTION = "EMLURB_156_DEMANDAS_2026"
    MONGO_TAMANHO_LOTE = 5_000

    # Configurações do NeonDB (PostgreSQL)
    NEON_DATABASE_URL_ENV = "NEON_DATABASE_URL"

    # Tabelas finais (iguais no SQLite e no Neon)
    TABELA_DEMANDAS = "emlurb_156_demandas"
    TABELA_AGREGADO = "emlurb_156_agregado_mensal"

    # Banco SQLite local (a pasta data/db/ já está no .gitignore)
    CAMINHO_SQLITE = RAIZ_PROJETO / "data" / "db" / "smart_city.db"

    # Índices que aceleram os filtros do app/dashboard.
    INDICES_DEMANDAS = (
        "bairro",
        "rpa",
        "grupo_servico",
        "situacao_categoria",
        "ano_mes",
    )
    INDICES_AGREGADO = ("ano_mes", "rpa", "bairro")

    def __init__(self, somente_sqlite: bool = False) -> None:
        """
        Inicializa as conexões com o MongoDB Atlas, o NeonDB e o SQLite.

        Parâmetros:
            somente_sqlite: se True, não exige credenciais do MongoDB nem
                do Neon e só prepara o banco SQLite local.
        """

        self.mongodb_uri_env = self.MONGODB_URI_ENV
        self.mongo_db = self.MONGO_DB
        self.mongo_collection = self.MONGO_COLLECTION
        self.neon_database_url_env = self.NEON_DATABASE_URL_ENV

        self.client = None
        self.neon_engine = None
        self.CAMINHO_SQLITE.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_engine: Engine = create_engine(f"sqlite:///{self.CAMINHO_SQLITE}")

        if somente_sqlite:
            return

        self.mongo_uri = os.getenv(self.mongodb_uri_env)

        if not self.mongo_uri:
            raise ValueError(f"Variável {self.mongodb_uri_env} não encontrada no .env.")

        self.neon_database_url = os.getenv(self.neon_database_url_env)

        if not self.neon_database_url:
            raise ValueError(
                f"Variável {self.neon_database_url_env} não encontrada no .env."
            )

        self.client = MongoClient(
            self.mongo_uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )
        self.neon_engine = create_engine(
            self._sqlalchemy_neon_url(self.neon_database_url),
            pool_pre_ping=True,
        )

    @staticmethod
    def _sqlalchemy_neon_url(database_url: str) -> str:
        """Seleciona explicitamente o driver Psycopg 3 no SQLAlchemy."""

        if database_url.startswith("postgresql+psycopg://"):
            return database_url

        if database_url.startswith("postgresql://"):
            return database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        if database_url.startswith("postgres://"):
            return database_url.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )

        raise ValueError(
            "NEON_DATABASE_URL inválida. Use uma URL iniciada por "
            "'postgresql://' conforme fornecida pelo painel do Neon."
        )

    def close(self) -> None:
        """Encerra as conexões com o MongoDB, o NeonDB e o SQLite."""
        if self.client is not None:
            self.client.close()
        if self.neon_engine is not None:
            self.neon_engine.dispose()
        self.sqlite_engine.dispose()

    def load_mongo(
        self,
        data: List[Dict[str, Any]],
    ) -> None:
        """
        Carrega os dados brutos na coleção do MongoDB, em lotes.

        Parâmetros:
            data: lista de registros brutos que será armazenada.
        """

        if not data:
            raise ValueError(
                "A carga no MongoDB foi cancelada porque nenhum registro foi recebido."
            )

        collection = self.client[self.mongo_db][self.mongo_collection]

        # Substitui o retrato bruto para evitar duplicação entre execuções.
        collection.delete_many({})

        for inicio in range(0, len(data), self.MONGO_TAMANHO_LOTE):
            collection.insert_many(data[inicio : inicio + self.MONGO_TAMANHO_LOTE])

        print("Dados brutos carregados com sucesso no MongoDB!")
        print(f"Banco: {self.mongo_db}")
        print(f"Coleção: {self.mongo_collection}")
        print(f"Total de documentos: {len(data)}")

    def _gravar_tabelas(
        self,
        engine: Engine,
        df: pd.DataFrame,
        df_agregado: pd.DataFrame,
        usar_chave_primaria: bool,
        metodo_insercao: Optional[str] = "multi",
    ) -> Dict[str, int]:
        """
        Grava as duas tabelas finais em um banco SQL (SQLite ou PostgreSQL),
        cria índices e devolve a contagem confirmada de cada tabela.
        """

        tabelas = (
            (self.TABELA_DEMANDAS, df, self.INDICES_DEMANDAS),
            (self.TABELA_AGREGADO, df_agregado, self.INDICES_AGREGADO),
        )
        totais: Dict[str, int] = {}

        with engine.begin() as conn:
            for nome, dados, indices in tabelas:
                dados.to_sql(
                    nome,
                    conn,
                    if_exists="replace",
                    index=False,
                    method=metodo_insercao,
                    chunksize=500,
                )

                if nome == self.TABELA_DEMANDAS:
                    if usar_chave_primaria:
                        conn.execute(
                            text(f'ALTER TABLE "{nome}" ADD PRIMARY KEY (id_demanda)')
                        )
                    else:
                        conn.execute(
                            text(
                                f'CREATE UNIQUE INDEX "ux_{nome}_id" '
                                f'ON "{nome}" (id_demanda)'
                            )
                        )

                for coluna in indices:
                    conn.execute(
                        text(
                            f'CREATE INDEX "ix_{nome}_{coluna}" '
                            f'ON "{nome}" ({coluna})'
                        )
                    )

                totais[nome] = int(
                    conn.execute(text(f'SELECT COUNT(*) FROM "{nome}"')).scalar_one()
                )

        return totais

    def load_sqlite(self, df: pd.DataFrame, df_agregado: pd.DataFrame) -> int:
        """
        Salva as tabelas transformadas no SQLite local (data/db/smart_city.db).

        Retorno:
            Quantidade de demandas confirmada no banco.
        """

        if df.empty or len(df.columns) == 0:
            raise ValueError(
                "A carga no SQLite foi cancelada porque o DataFrame está vazio."
            )

        totais = self._gravar_tabelas(
            self.sqlite_engine,
            df,
            df_agregado,
            usar_chave_primaria=False,
            metodo_insercao=None,  # executemany é mais rápido no SQLite
        )

        print("Dados transformados salvos com sucesso no SQLite!")
        print(f"Arquivo: {self.CAMINHO_SQLITE}")
        for tabela, total in totais.items():
            print(f"Tabela {tabela}: {total} registros")

        return totais[self.TABELA_DEMANDAS]

    def load_neon(self, df: pd.DataFrame, df_agregado: pd.DataFrame) -> int:
        """
        Salva as tabelas transformadas no PostgreSQL do Neon e confirma
        a quantidade de registros persistidos.

        Parâmetros:
            df: DataFrame detalhado das demandas.
            df_agregado: DataFrame agregado para o dashboard.

        Retorno:
            Quantidade de demandas confirmada no banco de dados.
        """

        if df.empty or len(df.columns) == 0:
            raise ValueError(
                "A carga no NeonDB foi cancelada porque o DataFrame está vazio."
            )

        totais = self._gravar_tabelas(
            self.neon_engine, df, df_agregado, usar_chave_primaria=True
        )

        print("Dados transformados salvos com sucesso no NeonDB!")
        for tabela, total in totais.items():
            print(f"Tabela {tabela}: {total} registros confirmados")

        return totais[self.TABELA_DEMANDAS]
