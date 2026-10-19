import argparse
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from dotenv import load_dotenv
from prefect import flow, get_run_logger, task
from run_etl import extrair_demandas_156
from src.extract import Extract
from src.load import Load
from src.transform import Transform

# Carrega as variáveis do arquivo .env localizado na raiz do projeto.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Extrai os dados do portal, usando os fallbacks para CSV e arquivo local
# definidos pelo ETL atual; no modo SQLite, não abre conexão com MongoDB.
@task(name="Extrair demandas 156", retries=3, retry_delay_seconds=10)
def extract_data(
    rpa: Optional[int] = None,
    somente_sqlite: bool = False,
) -> list[dict[str, Any]]:
    logger = get_run_logger()
    extractor = Extract(usar_mongo=not somente_sqlite)

    try:
        data = extrair_demandas_156(extractor, rpa=rpa)
        logger.info("Registros extraídos: %s", len(data))
        return data
    finally:
        extractor.close()


# Persiste o retrato dos dados brutos no MongoDB, como no pipeline original.
@task(name="Carregar dados brutos no MongoDB", retries=3, retry_delay_seconds=10)
def load_raw_mongo(data: list[dict[str, Any]]) -> None:
    logger = get_run_logger()
    loader = Load()

    try:
        loader.load_mongo(data)
        logger.info("Registros brutos carregados no MongoDB: %s", len(data))
    finally:
        loader.close()


@task(name="Ler dados brutos do MongoDB")
def read_raw_mongo() -> list[dict[str, Any]]:
    logger = get_run_logger()
    extractor = Extract()

    try:
        data = extractor.extract_collection_from_mongo()
        logger.info("Registros brutos lidos do MongoDB: %s", len(data))
        return data
    finally:
        extractor.close()

@task(name="Transformar demandas 156")
def transform_data(
    data: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = get_run_logger()
    transformer = Transform()

    df = transformer.transform_demandas_156(data)
    df_agregado = transformer.agregar_para_dashboard(df)
    logger.info(
        "Demandas transformadas: %s; linhas agregadas: %s",
        len(df),
        len(df_agregado),
    )
    return df, df_agregado


# Grava as tabelas detalhada e agregada no banco SQLite local.
@task(name="Carregar dados no SQLite")
def load_sqlite(
    dataframes: tuple[pd.DataFrame, pd.DataFrame],
) -> int:
    logger = get_run_logger()
    loader = Load(somente_sqlite=True)

    try:
        total = loader.load_sqlite(*dataframes)
        logger.info("Demandas confirmadas no SQLite: %s", total)
        return total
    finally:
        loader.close()


# Grava as mesmas tabelas transformadas no PostgreSQL do NeonDB.
@task(name="Carregar dados no NeonDB", retries=3, retry_delay_seconds=10)
def load_neon(dataframes: tuple[pd.DataFrame, pd.DataFrame]) -> int:
    logger = get_run_logger()
    loader = Load()

    try:
        total = loader.load_neon(*dataframes)
        logger.info("Demandas confirmadas no NeonDB: %s", total)
        return total
    finally:
        loader.close()


# Orquestra extração, carga bruta opcional no MongoDB, transformação e cargas
# finais; no modo SQLite-only, não exige nem acessa MongoDB ou NeonDB.
@flow(
    name="ETL Smart City Prefect",
    description="Orquestra o ETL da Central 156 da EMLURB.",
    log_prints=True,
)
def etl_smart_city_flow(
    somente_sqlite: bool = False,
    rpa: Optional[int] = None,
) -> None:
    data = extract_data(rpa=rpa, somente_sqlite=somente_sqlite)

    if somente_sqlite:
        data_transformacao = data
    else:
        load_raw_mongo(data)
        data_transformacao = read_raw_mongo()

    dataframes = transform_data(data_transformacao)
    load_sqlite(dataframes)

    if not somente_sqlite:
        load_neon(dataframes)


# Mantém as opções de linha de comando disponíveis no executor original.
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestração Prefect do ETL Smart City - EMLURB 156"
    )
    parser.add_argument(
        "--somente-sqlite",
        action="store_true",
        help="gera só o SQLite local, sem MongoDB nem NeonDB",
    )
    parser.add_argument(
        "--rpa",
        type=int,
        help="filtra a extração por uma RPA do Recife (1 a 6)",
    )
    args = parser.parse_args()

    etl_smart_city_flow(somente_sqlite=args.somente_sqlite, rpa=args.rpa)


# Permite iniciar o flow diretamente pela linha de comando.
if __name__ == "__main__":
    main()
