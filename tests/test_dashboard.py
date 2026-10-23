import unittest

from dashboard.data import filtrar, indicadores
from src.transform import Transform
from tests.test_transform import registro


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.df = Transform().transform_demandas_156(
            [
                registro(id_origem=1, SITUACAO="ATENDIDA"),
                registro(
                    id_origem=2,
                    SITUACAO="EXECUCAO",
                    RPA="3",
                    BAIRRO="CASA AMARELA",
                    DATA_DEMANDA="2019-01-01",
                ),
                registro(
                    id_origem=3,
                    SITUACAO="...",
                    DATA_DEMANDA="...",
                    latitude=None,
                    longitude=None,
                ),
            ]
        )

    def test_filtros_combinados_e_denominador(self):
        selecionado = filtrar(self.df, rpas=["6"], situacoes=["Atendida"])
        self.assertEqual(indicadores(selecionado)["total"], 1)
        self.assertEqual(indicadores(selecionado)["taxa"], 100)
        self.assertEqual(indicadores(self.df)["total"], 3)
        self.assertAlmostEqual(indicadores(self.df)["taxa"], 100 / 3)

    def test_filtro_vazio_e_datas_ausentes(self):
        self.assertEqual(len(filtrar(self.df, abertura="Anteriores a 2026")), 1)
        self.assertEqual(len(filtrar(self.df, abertura="Sem data")), 1)
        self.assertIsNone(
            indicadores(filtrar(self.df, bairros=["Inexistente"]))["taxa"]
        )


if __name__ == "__main__":
    unittest.main()
