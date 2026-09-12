import os
import sqlite3
from typing import Any, Dict, List

import certifi
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()


class Load:
    """
    Responsável por carregar os dados do pipeline.

    Os dados brutos são armazenados no MongoDB e os dados transformados
    são armazenados em uma tabela SQLite.
    """

    # Configurações do MongoDB
    MONGODB_URI_ENV = "MONGODB_URI"
    MONGO_DB = "SMART_CITY"
    MONGO_COLLECTION = "MOBILIDADE_FICHAS_PROJETOS"

    # Configurações do SQLite
    SQLITE_DATABASE = os.path.join("data", "db", "smart_city.db")
    SQLITE_TABLE = "mobilidade_fichas_projetos"

    def __init__(self) -> None:
        """
        Inicializa a conexão com o MongoDB.
        """

        self.mongodb_uri_env = self.MONGODB_URI_ENV
        self.mongo_db = self.MONGO_DB
        self.mongo_collection = self.MONGO_COLLECTION
        self.sqlite_database = self.SQLITE_DATABASE
        self.sqlite_table = self.SQLITE_TABLE

        os.makedirs(os.path.dirname(self.sqlite_database), exist_ok=True)

        self.mongo_uri = os.getenv(self.mongodb_uri_env)

        if not self.mongo_uri:
            raise ValueError(f"Variável {self.mongodb_uri_env} não encontrada no .env.")

        self.client = MongoClient(
            self.mongo_uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )

    def close(self) -> None:
        """Encerra a conexão com o MongoDB."""
        self.client.close()

    def load_mongo(
        self,
        data: List[Dict[str, Any]],
    ) -> None:
        """
        Carrega os dados brutos na coleção do MongoDB.

        Parâmetros:
            data: lista de registros brutos que será armazenada.
        """

        collection = self.client[self.mongo_db][self.mongo_collection]

        # Evita duplicação quando o pipeline é executado novamente.
        collection.delete_many({})

        if data:
            collection.insert_many(data)

        print("Dados brutos carregados com sucesso no MongoDB!")
        print(f"Banco: {self.mongo_db}")
        print(f"Coleção: {self.mongo_collection}")
        print(f"Total de documentos: {len(data)}")

    def load_sqlite(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Salva o DataFrame transformado em uma tabela SQLite.

        Parâmetros:
            df: DataFrame transformado que será salvo.
        """

        conn = sqlite3.connect(self.sqlite_database)

        try:
            df.to_sql(
                self.sqlite_table,
                conn,
                if_exists="replace",
                index=False,
            )
        finally:
            conn.close()

        print("Dados transformados salvos com sucesso no SQLite!")
        print(f"Banco: {self.sqlite_database}")
        print(f"Tabela: {self.sqlite_table}")
        print(f"Total de registros: {len(df)}")
