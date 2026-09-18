import os
from pathlib import Path
from typing import Any, Dict, List

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

    Os dados brutos são armazenados no MongoDB Atlas e os dados
    transformados são armazenados no PostgreSQL do Neon.
    """

    # Configurações do MongoDB
    MONGODB_URI_ENV = "MONGODB_URI"
    MONGO_DB = "SMART_CITY"
    MONGO_COLLECTION = "MOBILIDADE_FICHAS_PROJETOS"

    # Configurações do NeonDB (PostgreSQL)
    NEON_DATABASE_URL_ENV = "NEON_DATABASE_URL"
    NEON_TABLE = "mobilidade_fichas_projetos"

    def __init__(self) -> None:
        """
        Inicializa as conexões com o MongoDB Atlas e o NeonDB.
        """

        self.mongodb_uri_env = self.MONGODB_URI_ENV
        self.mongo_db = self.MONGO_DB
        self.mongo_collection = self.MONGO_COLLECTION
        self.neon_database_url_env = self.NEON_DATABASE_URL_ENV
        self.neon_table = self.NEON_TABLE

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
        self.neon_engine: Engine = create_engine(
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
        """Encerra as conexões com o MongoDB e o NeonDB."""
        self.client.close()
        self.neon_engine.dispose()

    def load_mongo(
        self,
        data: List[Dict[str, Any]],
    ) -> None:
        """
        Carrega os dados brutos na coleção do MongoDB.

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
        collection.insert_many(data)

        print("Dados brutos carregados com sucesso no MongoDB!")
        print(f"Banco: {self.mongo_db}")
        print(f"Coleção: {self.mongo_collection}")
        print(f"Total de documentos: {len(data)}")

    def load_neon(
        self,
        df: pd.DataFrame,
    ) -> int:
        """
        Salva o DataFrame transformado no PostgreSQL do Neon e confirma
        a quantidade de registros persistidos.

        Parâmetros:
            df: DataFrame transformado que será salvo no NeonDB.

        Retorno:
            Quantidade de registros confirmada no banco de dados.
        """

        if df.empty or len(df.columns) == 0:
            raise ValueError(
                "A carga no NeonDB foi cancelada porque o DataFrame está vazio."
            )

        with self.neon_engine.begin() as conn:
            df.to_sql(
                self.neon_table,
                conn,
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=500,
            )

            total_registros = conn.execute(
                text(f'SELECT COUNT(*) FROM "{self.neon_table}"')
            ).scalar_one()

        print("Dados transformados salvos com sucesso no NeonDB!")
        print(f"Tabela: {self.neon_table}")
        print(f"Total de registros confirmados no NeonDB: {total_registros}")

        return int(total_registros)
