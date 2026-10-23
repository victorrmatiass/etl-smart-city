"""Reconcilia o último lote bronze com o Neon, sem alterar nenhum banco."""

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.extract import Extract


def main():
    engine = config.criar_engine_neon()
    ext = Extract()
    try:
        with engine.connect() as conn:
            audit = dict(
                conn.execute(text(f'SELECT * FROM "{config.TABELA_AUDITORIA}"'))
                .mappings()
                .one()
            )
            final = conn.execute(
                text(f'SELECT COUNT(*) FROM "{config.TABELA_DEMANDAS}"')
            ).scalar_one()
            agregado = conn.execute(
                text(f'SELECT SUM(total) FROM "{config.TABELA_AGREGADO}"')
            ).scalar_one()
            ids = set(
                conn.execute(
                    text(f'SELECT id_origem FROM "{config.TABELA_DEMANDAS}"')
                ).scalars()
            )
        bronze = ext.extract_latest_from_mongo(audit["carga_id"])
        assert (
            len(bronze)
            == audit["total_bronze"]
            == audit["total_transformado"]
            == final
            == agregado
        )
        if audit["origem_extracao"] == "API CKAN":
            assert ids == {str(row["id_origem"]) for row in bronze}
        historico = ext.client[config.MONGO_DB][
            config.MONGO_COLLECTION
        ].count_documents({})
        print(
            f"Bronze (lote): {len(bronze)}; Neon: {final}; soma agregado: {agregado}."
        )
        print(f"Histórico completo no MongoDB: {historico} documentos.")
        print("Reconciliação OK: contagens e IDs de origem preservados.")
    finally:
        engine.dispose()
        ext.close()


if __name__ == "__main__":
    main()
