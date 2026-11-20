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
    def setUp(self):
        loader = Load.__new__(Load)
        loader.mongo_db = config.MONGO_DB
        loader.mongo_collection = config.MONGO_COLLECTION
        loader.client = MagicMock()
        db = loader.client[loader.mongo_db]
        self.collection, self.cargas = MagicMock(), MagicMock()
        db.__getitem__.side_effect = {
            loader.mongo_collection: self.collection,
            config.MONGO_CARGAS: self.cargas,
        }.__getitem__
        self.manifestos = {}
        self.cargas.find_one.side_effect = lambda filtro: self.manifestos.get(
            filtro["assinatura"]
        )
        self.cargas.insert_one.side_effect = lambda doc, **_: self.manifestos.update(
            {doc["assinatura"]: {**doc, "_id": doc["assinatura"]}}
        )
        self.session = loader.client.start_session.return_value.__enter__.return_value
        self.session.with_transaction.side_effect = lambda gravar: gravar(self.session)
        self.loader = loader

    def test_bronze_reutiliza_conteudo_e_preserva_multiplicidade(self):
        self.collection.count_documents.side_effect = [3, 2]
        rows = [registro(), registro(NUMERO="2"), registro()]
        a = self.loader.load_mongo(rows, "API CKAN")
        b = self.loader.load_mongo(rows[::-1], "API CKAN")
        self.assertEqual(a, b)
        self.collection.insert_many.assert_called_once()
        self.assertEqual(len(self.collection.insert_many.call_args.args[0]), 3)
        self.assertNotIn("data_extracao", rows[0])
        c = self.loader.load_mongo(rows[:2], "API CKAN")
        self.assertNotEqual(a, c)
        self.assertEqual(self.loader.load_mongo(rows, "API CKAN"), a)
        self.assertEqual(self.collection.insert_many.call_count, 2)

    def test_reaproveita_lote_anterior_sem_assinatura(self):
        self.cargas.find.return_value.sort.return_value = [
            {"_id": 12, "carga_id": "antigo"}
        ]
        self.collection.find.return_value = [
            {**registro(), "_id": 123, "carga_id": "antigo"}
        ]
        self.assertEqual(self.loader.load_mongo([registro()]), "antigo")
        self.cargas.update_one.assert_called_once()
        self.collection.insert_many.assert_not_called()

    def test_carga_parcial_nao_publica_manifesto(self):
        self.collection.insert_many.side_effect = RuntimeError("interrupção")
        with self.assertRaises(RuntimeError):
            self.loader.load_mongo([registro()])
        self.assertIs(self.cargas.insert_one.call_args.kwargs["session"], self.session)
        self.assertIs(
            self.collection.insert_many.call_args.kwargs["session"], self.session
        )

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
