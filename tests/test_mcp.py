import unittest
from unittest.mock import MagicMock, patch

from assistente import AssistenteGPT
from banco import BancoComLimite, BancoNeon
from src import config


class BancoMCPTestCase(unittest.TestCase):
    def test_banco_com_limite_herda_e_devolve_no_maximo_dez(self):
        banco = BancoComLimite("postgresql://exemplo", limite=50)
        linhas = [{"id": numero} for numero in range(20)]

        with patch.object(BancoNeon, "consultar", return_value=linhas):
            resultado = banco.consultar("SELECT * FROM exemplo")

        self.assertIsInstance(banco, BancoNeon)
        self.assertEqual(len(resultado), 10)
        self.assertEqual(resultado[-1], {"id": 9})

    def test_limite_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            BancoComLimite("postgresql://exemplo", limite=0)

    def test_consulta_de_escrita_e_rejeitada(self):
        banco = BancoNeon("postgresql://exemplo")
        with self.assertRaisesRegex(ValueError, "Apenas consultas SELECT"):
            banco.consultar("DELETE FROM exemplo")

    def test_multiplas_instrucoes_sao_rejeitadas(self):
        banco = BancoNeon("postgresql://exemplo")
        with self.assertRaisesRegex(ValueError, "exatamente uma"):
            banco.consultar("SELECT 1; SELECT 2")


class AssistenteMCPTestCase(unittest.TestCase):
    def test_modelo_padrao_da_classe(self):
        assistente = AssistenteGPT("chave")
        self.assertEqual(assistente.modelo, "gpt-6-luna")

    def test_configuracao_central_tem_modelo(self):
        self.assertTrue(config.MODELO)

    @patch("assistente.OpenAI")
    def test_base_url_compativel_com_outro_provedor(self, openai):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="SELECT 1"))
        ]
        openai.return_value = cliente
        assistente = AssistenteGPT(
            "chave", modelo="modelo-gratuito", base_url="https://api.exemplo/v1"
        )

        resultado = assistente.perguntar("instrução", "pergunta")

        openai.assert_called_once_with(
            api_key="chave", base_url="https://api.exemplo/v1"
        )
        self.assertEqual(resultado, "SELECT 1")

    def test_chave_ausente_falha_so_ao_usar_modelo(self):
        assistente = AssistenteGPT("")
        with self.assertRaisesRegex(ValueError, "GPT_API_KEY"):
            assistente.perguntar("instrução", "pergunta")


if __name__ == "__main__":
    unittest.main()
