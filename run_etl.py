from src.extract import Extract
from src.load import Load
from src.transform import Transform


# Região utilizada pelo projeto Smart City.
REGIAO_METROPOLITANA = "RM Recife"


def main() -> None:
    """
    Executa o pipeline completo de ETL.
    """

    ext = Extract()
    ld = Load()
    transformer = Transform()

    try:
        # ==========================================================
        # ETAPA 1 - EXTRAÇÃO
        # ==========================================================

        print()
        print("=" * 60)
        print("ETAPA 1 - EXTRAÇÃO")
        print("=" * 60)

        data = ext.baixar_mobilidade_fichas_projetos()

        print(f"Registros extraídos: {len(data)}")

        # ==========================================================
        # ETAPA 2 - CARGA DO DADO BRUTO NO MONGODB
        # ==========================================================

        print()
        print("=" * 60)
        print("ETAPA 2 - CARGA DO DADO BRUTO NO MONGODB")
        print("=" * 60)

        ld.load_mongo(data)

        # ==========================================================
        # ETAPA 3 - LEITURA E FILTRO
        # ==========================================================

        print()
        print("=" * 60)
        print("ETAPA 3 - LEITURA E FILTRO")
        print("=" * 60)

        data_mongo = ext.extract_collection_from_mongo()

        data_recife = ext.filtrar_por_regiao_metropolitana(
            data_mongo,
            REGIAO_METROPOLITANA,
        )

        # ==========================================================
        # ETAPA 4 - TRANSFORMAÇÃO
        # ==========================================================

        print()
        print("=" * 60)
        print("ETAPA 4 - TRANSFORMAÇÃO")
        print("=" * 60)

        df = transformer.transform_mobilidade_fichas_projetos(
            data_recife
        )

        # ==========================================================
        # ETAPA 5 - CARGA NO SQLITE
        # ==========================================================

        print()
        print("=" * 60)
        print("ETAPA 5 - CARGA NO SQLITE")
        print("=" * 60)

        ld.load_sqlite(df)

        # ==========================================================
        # RESULTADO FINAL
        # ==========================================================

        print()
        print("=" * 60)
        print("PIPELINE EXECUTADO COM SUCESSO!")
        print("=" * 60)

        print(f"Dados brutos no MongoDB: {len(data_mongo)}")
        print(
            f"Dados da {REGIAO_METROPOLITANA}: "
            f"{len(data_recife)}"
        )
        print(
            f"Dados transformados no SQLite: "
            f"{len(df)}"
        )

    finally:
        ld.close()
        ext.close()


if __name__ == "__main__":
    main()
