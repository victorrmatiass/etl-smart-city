import unittest
from unittest.mock import MagicMock, patch
import requests
from src import config

from src.extract import Extract


def resposta_ckan(registros, total):
    resposta = MagicMock()
    resposta.json.return_value = {
        "success": True,
        "result": {"records": registros, "total": total},
    }
    return resposta


class ExtractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Evita abrir conexão com o MongoDB.
        self.extract = Extract(usar_mongo=False)
        self.extract.tamanho_pagina = 2

    @patch("src.extract.requests.get")
    def test_api_pagina_ate_o_total_e_remove_id_interno(self, requests_get) -> None:
        requests_get.side_effect = [
            resposta_ckan([{"_id": 1, "BAIRRO": "A"}, {"_id": 2, "BAIRRO": "B"}], 3),
            resposta_ckan([{"_id": 3, "BAIRRO": "C"}], 3),
        ]

        resultado = self.extract.baixar_demandas_api()

        self.assertEqual([r["BAIRRO"] for r in resultado], ["A", "B", "C"])
        self.assertTrue(all("_id" not in r for r in resultado))
        self.assertEqual([r["id_origem"] for r in resultado], [1, 2, 3])
        self.assertEqual(requests_get.call_count, 2)

    def test_rejeita_rpa_fora_do_conjunto_valido(self) -> None:
        with self.assertRaises(ValueError):
            self.extract.baixar_demandas_api(rpa=9)

    @patch("src.extract.requests.get")
    def test_api_envia_filtro_de_rpa(self, requests_get) -> None:
        requests_get.return_value = resposta_ckan([{"RPA": 3}], 1)

        self.extract.baixar_demandas_api(rpa=3)

        parametros = requests_get.call_args.kwargs["params"]
        self.assertEqual(parametros["filters"], '{"RPA": 3}')
        self.assertEqual(parametros["resource_id"], self.extract.resource_id)

    def test_filtra_csv_local_por_rpa(self) -> None:
        linhas = [{"RPA": "3", "BAIRRO": "A"}, {"RPA": "6", "BAIRRO": "B"}]

        self.assertEqual(self.extract._filtrar_por_rpa(linhas, 6), [linhas[1]])
        self.assertEqual(self.extract._filtrar_por_rpa(linhas, None), linhas)

    def test_le_csv_com_ponto_e_virgula_e_cp1252(self) -> None:
        conteudo = "BAIRRO;SERVICO\nBoa Viagem;Poda de árvore\n".encode("cp1252")

        linhas = Extract._ler_csv_bytes(conteudo)

        self.assertEqual(
            linhas, [{"BAIRRO": "Boa Viagem", "SERVICO": "Poda de árvore"}]
        )

    def test_le_csv_com_virgula_e_bom_utf8(self) -> None:
        conteudo = "BAIRRO,SERVICO\nVárzea,Capina\n".encode("utf-8-sig")

        linhas = Extract._ler_csv_bytes(conteudo)

        self.assertEqual(linhas, [{"BAIRRO": "Várzea", "SERVICO": "Capina"}])

    @patch("src.extract.requests.get")
    def test_recusa_paginacao_incompleta(self, get):
        get.side_effect = [resposta_ckan([{"_id": 1}], 3), resposta_ckan([], 3)]
        with self.assertRaises(requests.exceptions.RequestException):
            self.extract.baixar_demandas_api()

    def test_le_apenas_lote_completo_mais_recente(self):
        self.extract.client = MagicMock()
        db = self.extract.client[self.extract.mongo_db]
        db[config.MONGO_CARGAS].find_one.return_value = {"carga_id": "nova", "total": 2}
        collection = db[self.extract.mongo_collection]
        collection.find.return_value = [{"carga_id": "nova"}, {"carga_id": "nova"}]
        self.assertEqual(len(self.extract.extract_latest_from_mongo()), 2)
        collection.find.assert_called_once_with({"carga_id": "nova"})
        db[config.MONGO_CARGAS].find_one.assert_called_once_with(
            {}, sort=[("data_extracao", -1)]
        )

    def test_bloqueia_lote_incompleto(self):
        self.extract.client = MagicMock()
        db = self.extract.client[self.extract.mongo_db]
        db[config.MONGO_CARGAS].find_one.return_value = {
            "carga_id": "nova",
            "total": 10,
        }
        db[self.extract.mongo_collection].find.return_value = [{"carga_id": "nova"}]
        with self.assertRaises(ValueError):
            self.extract.extract_latest_from_mongo()


if __name__ == "__main__":
    unittest.main()
