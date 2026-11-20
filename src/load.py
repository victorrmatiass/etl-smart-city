from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import certifi
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.server_api import ServerApi
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src import config

RAIZ_PROJETO = config.RAIZ_PROJETO


class Load:
    """
    Responsável por carregar os dados do pipeline.

    - MongoDB Atlas: dado bruto, exatamente como veio do portal;
    - SQLite (local): dado transformado, para consulta no VS Code;
    - PostgreSQL do Neon: dado transformado, consumido pelo app/dashboard.
    """

    # Configurações do MongoDB
    MONGODB_URI_ENV = "MONGODB_URI"
    MONGO_DB = config.MONGO_DB
    MONGO_COLLECTION = config.MONGO_COLLECTION
    MONGO_TAMANHO_LOTE = 5_000

    # Configurações do NeonDB (PostgreSQL)
    NEON_DATABASE_URL_ENV = "NEON_DATABASE_URL"

    # Tabelas finais (iguais no SQLite e no Neon)
    TABELA_DEMANDAS = config.TABELA_DEMANDAS
    TABELA_AGREGADO = config.TABELA_AGREGADO

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

        self.mongo_uri = config.MONGODB_URI

        if not self.mongo_uri:
            raise ValueError(f"Variável {self.mongodb_uri_env} não encontrada no .env.")

        self.neon_database_url = config.NEON_DATABASE_URL

        if not self.neon_database_url:
            raise ValueError(
                f"Variável {self.neon_database_url_env} não encontrada no .env."
            )

        self.client = MongoClient(
            self.mongo_uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )
        self.neon_engine = config.criar_engine_neon()

    @staticmethod
    def _sqlalchemy_neon_url(database_url: str) -> str:
        """Seleciona explicitamente o driver Psycopg 3 no SQLAlchemy."""
        return config.sqlalchemy_neon_url(database_url).render_as_string(
            hide_password=False
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
        origem: str = "não informada",
    ) -> str:
        """
        Carrega os dados brutos na coleção do MongoDB, em lotes.

        Parâmetros:
            data: lista de registros brutos que será armazenada.
        """

        if not data:
            raise ValueError(
                "A carga no MongoDB foi cancelada porque nenhum registro foi recebido."
            )

        db = self.client[self.mongo_db]
        collection = db[self.mongo_collection]
        cargas = db[config.MONGO_CARGAS]
        data_extracao = datetime.now(timezone.utc)
        assinatura = self._assinatura(data, origem)
        collection.create_index([("carga_id", 1)])
        collection.create_index([("data_extracao", -1)])
        cargas.create_index("assinatura", unique=True, sparse=True)
        observacao = {"$max": {"ultima_observacao": data_extracao}}
        existente = cargas.find_one({"assinatura": assinatura})
        if existente:
            cargas.update_one({"_id": existente["_id"]}, observacao)
            return existente["carga_id"]

        # Um lote da versão anterior pode já conter exatamente esta extração.
        candidatos = cargas.find(
            {"assinatura": {"$exists": False}, "origem": origem, "total": len(data)}
        ).sort("data_extracao", -1)
        for legado in candidatos:
            linhas = collection.find({"carga_id": legado["carga_id"]})
            if self._assinatura(linhas, origem) == assinatura:
                cargas.update_one(
                    {"_id": legado["_id"]},
                    {"$set": {"assinatura": assinatura}, **observacao},
                )
                return legado["carga_id"]

        def gravar(session):
            # O índice único arbitra escritores concorrentes. O Atlas confirma
            # manifesto e documentos juntos, inclusive em retries do driver.
            cargas.insert_one(
                {
                    "assinatura": assinatura,
                    "carga_id": assinatura,
                    "data_extracao": data_extracao,
                    "ultima_observacao": data_extracao,
                    "origem": origem,
                    "total": len(data),
                },
                session=session,
            )
            for inicio in range(0, len(data), self.MONGO_TAMANHO_LOTE):
                documentos = [
                    {
                        **{k: v for k, v in row.items() if k != "_id"},
                        "data_extracao": data_extracao,
                        "carga_id": assinatura,
                        "origem_extracao": origem,
                    }
                    for row in data[inicio : inicio + self.MONGO_TAMANHO_LOTE]
                ]
                collection.insert_many(documentos, session=session)
            if collection.count_documents(
                {"carga_id": assinatura}, session=session
            ) != len(data):
                raise ValueError(
                    "Contagem do lote bronze divergente; transação cancelada."
                )

        try:
            with self.client.start_session() as session:
                session.with_transaction(gravar)
        except DuplicateKeyError:
            vencedor = cargas.find_one({"assinatura": assinatura})
            if vencedor is None:
                raise
            cargas.update_one({"_id": vencedor["_id"]}, observacao)
            return vencedor["carga_id"]
        return assinatura

    @staticmethod
    def _assinatura(linhas, origem):
        """Identifica um retrato independente da ordem, preservando multiplicidades."""
        metadados = {"_id", "data_extracao", "carga_id", "origem_extracao"}
        hashes = sorted(
            hashlib.sha256(
                json.dumps(
                    {k: v for k, v in linha.items() if k not in metadados},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).digest()
            for linha in linhas
        )
        return hashlib.sha256(origem.encode() + b"\0" + b"".join(hashes)).hexdigest()

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

                if totais[nome] != len(dados):
                    raise ValueError(
                        f"Contagem divergente na tabela {nome}; carga revertida."
                    )

            if int(df_agregado["total"].sum()) != len(df):
                raise ValueError("Agregado perdeu registros; carga revertida.")
            auditoria = dict(df.attrs.get("auditoria", {}))
            auditoria.update(
                total_final=totais[self.TABELA_DEMANDAS],
                total_agregado=int(df_agregado["total"].sum()),
            )
            pd.DataFrame([auditoria]).to_sql(
                config.TABELA_AUDITORIA, conn, if_exists="replace", index=False
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
