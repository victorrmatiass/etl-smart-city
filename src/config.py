"""Configuração compartilhada. O .env é lido uma vez, na importação."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ_PROJETO / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
MONGO_DB = "SMART_CITY"
MONGO_COLLECTION = "EMLURB_156_DEMANDAS_2026"
MONGO_CARGAS = MONGO_COLLECTION + "_CARGAS"
TABELA_DEMANDAS = "emlurb_156_demandas"
TABELA_AGREGADO = "emlurb_156_agregado_mensal"
TABELA_AUDITORIA = "emlurb_156_auditoria"
CKAN_BASE_URL = "https://dados.recife.pe.gov.br"
RESOURCE_ID = "80c5b3cd-d4f7-466e-9031-e636ef56dd99"
PACKAGE_ID = "331e88a9-d878-464b-b0bb-cb803d7091b3"
NOME_ARQUIVO_CSV = "156_cco_diario_2026.csv"
CAMINHO_CSV_LOCAL = RAIZ_PROJETO / "data" / NOME_ARQUIVO_CSV


def sqlalchemy_neon_url(database_url: str):
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError(
            "Configure NEON_DATABASE_URL com a URL PostgreSQL do Neon no .env."
        )
    return make_url(database_url).set(drivername="postgresql+psycopg")


def criar_engine_neon():
    return create_engine(
        sqlalchemy_neon_url(NEON_DATABASE_URL),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 15},
    )
