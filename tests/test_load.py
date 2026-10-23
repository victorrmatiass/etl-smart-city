import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from sqlalchemy import create_engine, text

from src.load import Load
from src.transform import Transform
from tests.test_transform import registro
from src import config


class LoadTestCase(unittest.TestCase):
    def test_bronze_acrescenta_lotes_sem_apagar_nem_mutar_fonte(self):
        loader = Load.__new__(Load)
        loader.mongo_db = config.MONGO_DB
        loader.mongo_collection = config.MONGO_COLLECTION
        loader.client = MagicMock()
        db = loader.client[loader.mongo_db]
        collection = db[loader.mongo_collection]
        collection.count_documents.return_value = 2
        rows = [registro(), registro(NUMERO="2")]
        a = loader.load_mongo(rows, "API CKAN")
        b = loader.load_mongo(rows, "API CKAN")
        self.assertNotEqual(a, b)
        collection.delete_many.assert_not_called()
        self.assertEqual(collection.insert_many.call_count, 2)
        self.assertEqual(db[config.MONGO_CARGAS].insert_one.call_count, 2)
        inserted = collection.insert_many.call_args.args[0]
        self.assertEqual(len({r["data_extracao"] for r in inserted}), 1)
        self.assertTrue(all(r["carga_id"] == b for r in inserted))
        self.assertNotIn("data_extracao", rows[0])

    def test_carga_parcial_nao_publica_manifesto(self):
        loader = Load.__new__(Load)
        loader.mongo_db, loader.mongo_collection = (
            config.MONGO_DB,
            config.MONGO_COLLECTION,
        )
        loader.client = MagicMock()
        db = loader.client[loader.mongo_db]
        db[loader.mongo_collection].insert_many.side_effect = RuntimeError(
            "interrupção"
        )
        with self.assertRaises(RuntimeError):
            loader.load_mongo([registro()])
        db[config.MONGO_CARGAS].insert_one.assert_not_called()

    def test_adapta_url_do_neon_para_psycopg(self) -> None:
        url = "postgresql://usuario:senha@servidor/neondb?sslmode=require"

        resultado = Load._sqlalchemy_neon_url(url)

        self.assertEqual(
            resultado,
            "postgresql+psycopg://usuario:senha@servidor/neondb?sslmode=require",
        )

    def test_rejeita_url_invalida(self) -> None:
        with self.assertRaises(ValueError):
            Load._sqlalchemy_neon_url("https://servidor")

    def test_rejeita_dataframe_vazio_antes_de_conectar(self) -> None:
        load = Load.__new__(Load)

        with self.assertRaises(ValueError):
            load.load_neon(pd.DataFrame(), pd.DataFrame())

        with self.assertRaises(ValueError):
            load.load_sqlite(pd.DataFrame(), pd.DataFrame())

    def test_grava_sqlite_com_indices(self) -> None:
        transformer = Transform()
        df = transformer.transform_demandas_156([registro(), registro(NUMERO="2")])
        agregado = transformer.agregar_para_dashboard(df)

        with tempfile.TemporaryDirectory() as pasta:
            load = Load.__new__(Load)
            load.CAMINHO_SQLITE = Path(pasta) / "teste.db"
            load.sqlite_engine = create_engine(f"sqlite:///{load.CAMINHO_SQLITE}")

            total = load.load_sqlite(df, agregado)
            # Rodar de novo deve substituir, e não duplicar nem falhar.
            total_2 = load.load_sqlite(df, agregado)

            with load.sqlite_engine.connect() as conn:
                indices = (
                    conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='index'")
                    )
                    .scalars()
                    .all()
                )

            load.sqlite_engine.dispose()

        self.assertEqual((total, total_2), (2, 2))
        self.assertIn("ix_emlurb_156_demandas_bairro", indices)
        self.assertIn("ux_emlurb_156_demandas_id", indices)

    def test_ausencia_chega_ao_sql_como_null_e_auditoria_fecha(self):
        transformer = Transform()
        df = transformer.transform_demandas_156(
            [
                registro(
                    DATA_DEMANDA="...", SITUACAO="N/A", latitude=None, longitude=None
                )
            ]
        )
        agregado = transformer.agregar_para_dashboard(df)
        with tempfile.TemporaryDirectory() as pasta:
            load = Load.__new__(Load)
            load.CAMINHO_SQLITE = Path(pasta) / "ausencias.db"
            load.sqlite_engine = create_engine(f"sqlite:///{load.CAMINHO_SQLITE}")
            try:
                load.load_sqlite(df, agregado)
                with load.sqlite_engine.connect() as conn:
                    row = conn.execute(
                        text(
                            "SELECT data_demanda, situacao, latitude, longitude, concluida, tempo_resolucao_dias FROM emlurb_156_demandas"
                        )
                    ).one()
                    self.assertEqual(tuple(row), (None,) * 6)
                    audit = conn.execute(
                        text(
                            "SELECT total_bronze, total_transformado, total_final, total_agregado FROM emlurb_156_auditoria"
                        )
                    ).one()
                    self.assertEqual(tuple(audit), (1, 1, 1, 1))
            finally:
                load.sqlite_engine.dispose()


if __name__ == "__main__":
    unittest.main()
