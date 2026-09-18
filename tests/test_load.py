import unittest

import pandas as pd

from src.load import Load


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
            load.load_neon(pd.DataFrame())


if __name__ == "__main__":
    unittest.main()
