import unittest

from src.transform import Transform


class TransformTestCase(unittest.TestCase):
    def test_preserva_codigo_de_projeto_alfanumerico(self) -> None:
        dados = [
            {
                "_id": "mongo-id",
                "rm": "RM Recife",
                "cod_proj": "20302B",
                "id_gpkg": "20302",
                "invest_total": "123,45",
            }
        ]

        df = Transform().transform_mobilidade_fichas_projetos(dados)

        self.assertEqual(df.loc[0, "cod_proj"], "20302B")
        self.assertEqual(str(df["cod_proj"].dtype), "string")
        self.assertEqual(df.loc[0, "id_gpkg"], 20302)
        self.assertEqual(df.loc[0, "invest_total"], 123.45)
        self.assertNotIn("_id", df.columns)

    def test_retorna_dataframe_vazio_sem_dados(self) -> None:
        df = Transform().transform_mobilidade_fichas_projetos([])

        self.assertTrue(df.empty)


if __name__ == "__main__":
    unittest.main()
