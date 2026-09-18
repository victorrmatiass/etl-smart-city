import unittest
from unittest.mock import MagicMock, patch

from src.extract import Extract


class ExtractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Evita abrir conexão: o filtro não depende do construtor.
        self.extract = Extract.__new__(Extract)

    def test_filtra_regiao_metropolitana(self) -> None:
        dados = [
            {"rm": "RM Recife", "cod_proj": "1"},
            {"rm": "RM Salvador", "cod_proj": "2"},
        ]

        resultado = self.extract.filtrar_por_regiao_metropolitana(
            dados,
            "RM Recife",
        )

        self.assertEqual(resultado, [{"rm": "RM Recife", "cod_proj": "1"}])

    def test_rejeita_regiao_desconhecida(self) -> None:
        with self.assertRaises(ValueError):
            self.extract.filtrar_por_regiao_metropolitana([], "Região inexistente")

    @patch("src.extract.requests.get")
    def test_baixa_link_retornado_pela_api(self, requests_get: MagicMock) -> None:
        self.extract.dados_gov_br_base_url = "https://dados.gov.br"
        self.extract.dados_gov_br_dataset_api = "/dados/api/publico/conjuntos-dados"
        self.extract.headers = {"chave-api-dados-abertos": "chave-teste"}

        resposta_metadados = MagicMock()
        resposta_metadados.json.return_value = {
            "recursos": [
                {
                    "id": "ed69dbee-4eda-4831-9492-d41ea27ba8d9",
                    "link": "https://dadosabertos.bndes.gov.br/recurso.csv",
                }
            ]
        }

        resposta_csv = MagicMock()
        resposta_csv.content = '"rm";"cod_proj"\r\n"RM Recife";"20302B"\r\n'.encode(
            "cp1252"
        )
        requests_get.side_effect = [resposta_metadados, resposta_csv]

        resultado = self.extract.baixar_mobilidade_fichas_projetos()

        self.assertEqual(
            resultado,
            [{"rm": "RM Recife", "cod_proj": "20302B"}],
        )
        requests_get.assert_any_call(
            "https://dadosabertos.bndes.gov.br/recurso.csv",
            timeout=60,
        )


if __name__ == "__main__":
    unittest.main()
