import argparse
from pathlib import Path
from typing import Optional

import requests

from src.extract import Extract
from src.load import Load
from src.transform import Transform

RAIZ_PROJETO = Path(__file__).resolve().parent
CAMINHO_CSV_LOCAL = RAIZ_PROJETO / "data" / "156_cco_diario_2026.csv"


def extrair_demandas_156(ext: Extract, rpa: Optional[int] = None) -> list:
    """
    Baixa os atendimentos do 156 pela API do Portal de Dados do Recife.
    Se a API falhar, tenta o download do CSV e, por último, o CSV local.

    Parâmetros:
        ext: instância de Extract já inicializada.
        rpa: código da RPA (1 a 6) para filtrar; None traz todas.

    Retorno:
        Lista de dicionários com os atendimentos.
    """

    try:
        return ext.baixar_demandas_api(rpa=rpa)
    except requests.exceptions.RequestException as erro:
        print(f"Falha ao consultar a API ({erro}). Tentando o download do CSV.")

    try:
        return ext.baixar_demandas_csv(rpa=rpa)
    except requests.exceptions.RequestException as erro:
        print(f"Falha ao baixar o CSV ({erro}).")
        print(f"Usando o CSV local em '{CAMINHO_CSV_LOCAL}'.")
        return ext.carregar_demandas_local(CAMINHO_CSV_LOCAL, rpa=rpa)


def titulo_etapa(texto: str) -> None:
    print()
    print("=" * 60)
    print(texto)
    print("=" * 60)


def main(somente_sqlite: bool = False, rpa: Optional[int] = None) -> None:
    """
    Executa o pipeline de ETL.

    Parâmetros:
        somente_sqlite: gera apenas o banco SQLite local (data/db/smart_city.db),
            sem MongoDB e sem NeonDB, portanto sem precisar do .env.
        rpa: código da RPA (1 a 6) para filtrar a extração; None traz todas.
    """

    ext = None
    ld = None

    try:
        ext = Extract(usar_mongo=not somente_sqlite)
        ld = Load(somente_sqlite=somente_sqlite)
        transformer = Transform()

        titulo_etapa("ETAPA 1 - EXTRAÇÃO (Central 156 / EMLURB - 2026)")
        data = extrair_demandas_156(ext, rpa)
        print(f"Registros extraídos: {len(data)}")

        if somente_sqlite:
            data_mongo = data
        else:
            titulo_etapa("ETAPA 2 - CARGA DO DADO BRUTO NO MONGODB")
            ld.load_mongo(data)

            titulo_etapa("ETAPA 3 - LEITURA DO DADO BRUTO NO MONGODB")
            data_mongo = ext.extract_collection_from_mongo()

        titulo_etapa("ETAPA 4 - TRANSFORMAÇÃO")
        df = transformer.transform_demandas_156(data_mongo)
        df_agregado = transformer.agregar_para_dashboard(df)

        titulo_etapa("ETAPA 5 - CARGA NO SQLITE (local)")
        total_sqlite = ld.load_sqlite(df, df_agregado)

        total_neon = None
        if not somente_sqlite:
            titulo_etapa("ETAPA 6 - CARGA NO NEONDB")
            total_neon = ld.load_neon(df, df_agregado)

        titulo_etapa("PIPELINE EXECUTADO COM SUCESSO!")
        print(f"Registros brutos lidos: {len(data_mongo)}")
        print(f"Demandas transformadas: {len(df)}")
        print(f"Linhas na tabela agregada: {len(df_agregado)}")
        print(f"Demandas confirmadas no SQLite: {total_sqlite}")
        if total_neon is not None:
            print(f"Demandas confirmadas no NeonDB: {total_neon}")
        print(f"Banco SQLite: {ld.CAMINHO_SQLITE}")

    finally:
        if ld is not None:
            ld.close()
        if ext is not None:
            ext.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL Smart City - EMLURB 156")
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
    main(somente_sqlite=args.somente_sqlite, rpa=args.rpa)
