import tempfile
import unittest
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from src.load import Load
from src.transform import Transform
from tests.test_transform import registro


class LoadTestCase(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
