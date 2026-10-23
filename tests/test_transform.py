import unittest
import pandas as pd

from src.transform import Transform


def registro(**extra):
    base = {
        "GRUPOSERVICO_CODIGO": "10",
        "GRUPOSERVICO_DESCRICAO": "ILUMINAÇÃO PÚBLICA",
        "SERVICO_CODIGO": "101",
        "SERVICO_DESCRICAO": "LÂMPADA APAGADA",
        "LOGRADOURO": "RUA DO FUTURO",
        "NUMERO": "100",
        "BAIRRO": "BOA VIAGEM",
        "RPA": "6",
        "DATA_DEMANDA": "2026-03-04T10:15:00",
        "SITUACAO": "Concluído",
        "DATA_ULT_SITUACAO": "2026-03-06T10:15:00",
        "latitude": "-8,1200",
        "longitude": "-34,9000",
    }
    base.update(extra)
    return base


class TransformTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.t = Transform()

    def test_retorna_dataframe_vazio_sem_dados(self) -> None:
        self.assertTrue(self.t.transform_demandas_156([]).empty)

    def test_falha_se_faltar_coluna_esperada(self) -> None:
        with self.assertRaises(ValueError):
            self.t.transform_demandas_156([{"BAIRRO": "X"}])

    def test_limpeza_e_tipos(self) -> None:
        df = self.t.transform_demandas_156([{"_id": "mongo", **registro()}])

        linha = df.iloc[0]
        self.assertNotIn("_id", df.columns)
        self.assertEqual(linha["bairro"], "Boa Viagem")
        self.assertEqual(linha["logradouro"], "Rua do Futuro")
        self.assertEqual(linha["grupo_servico"], "Iluminação Pública")
        self.assertEqual(linha["rpa"], 6)
        self.assertEqual(linha["latitude"], -8.12)  # vírgula decimal
        self.assertTrue(linha["tem_coordenadas"])
        self.assertEqual(linha["ano_mes"], "2026-03")
        self.assertEqual(linha["dia_semana"], "Quarta-feira")
        self.assertEqual(linha["hora"], 10)
        self.assertTrue(linha["concluida"])
        self.assertAlmostEqual(linha["tempo_resolucao_dias"], 2.0)

    def test_data_no_formato_brasileiro(self) -> None:
        df = self.t.transform_demandas_156(
            [registro(DATA_DEMANDA="04/03/2026 10:15", DATA_ULT_SITUACAO="")]
        )

        self.assertEqual(df.loc[0, "ano_mes"], "2026-03")
        self.assertTrue(df["data_ultima_situacao"].isna().all())

    def test_preserva_aberturas_de_anos_anteriores(self) -> None:
        df = self.t.transform_demandas_156(
            [registro(), registro(DATA_DEMANDA="2025-12-31T23:00:00")]
        )

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["ano"]), {2025, 2026})

    def test_preserva_registros_com_mesmo_hash_sem_colisao_de_id(self) -> None:
        a = self.t.transform_demandas_156([registro(), registro()])
        b = self.t.transform_demandas_156([registro(SITUACAO="Cancelado")])

        self.assertEqual(len(a), 2)
        self.assertTrue(a["id_demanda"].is_unique)
        # A situação muda com o tempo, mas o ID da demanda não.
        self.assertEqual(a.loc[0, "id_demanda"], b.loc[0, "id_demanda"])

    def test_coordenadas_invalidas_viram_nulas_e_trocadas_sao_corrigidas(self) -> None:
        df = self.t.transform_demandas_156(
            [
                registro(latitude="0", longitude="0", NUMERO="1"),
                registro(latitude="-34.9", longitude="-8.1", NUMERO="2"),
                registro(latitude="-23.5", longitude="-46.6", NUMERO="3"),
            ]
        ).set_index("numero")

        self.assertFalse(df.loc["1", "tem_coordenadas"])
        self.assertTrue(df["latitude"].isna()["1"])
        self.assertEqual(df.loc["2", "latitude"], -8.1)
        self.assertEqual(df.loc["2", "longitude"], -34.9)
        self.assertFalse(df.loc["3", "tem_coordenadas"])

    def test_categorias_de_situacao(self) -> None:
        cat = self.t._categorizar_situacao
        self.assertEqual(cat("Concluído"), "Concluída")
        self.assertEqual(cat("Em Execução"), "Em andamento")
        self.assertEqual(cat("Aguardando vistoria"), "Em andamento")
        self.assertEqual(cat("Cancelado"), "Cancelada")
        self.assertEqual(cat("Algo novo"), "Outros")
        self.assertIsNone(cat(None))

    def test_valores_nulos_e_sem_numero(self) -> None:
        df = self.t.transform_demandas_156(
            [registro(BAIRRO="NULL", NUMERO="S/N", RPA="99")]
        )

        self.assertTrue(df["bairro"].isna().all())
        self.assertEqual(df.loc[0, "numero"], "S/N")
        self.assertTrue(df["rpa"].isna().all())

    def test_nulos_em_varias_colunas_nao_quebram(self) -> None:
        df = self.t.transform_demandas_156(
            [
                registro(NUMERO="1"),
                registro(NUMERO="2", BAIRRO="", SITUACAO="", LOGRADOURO="NULL"),
            ]
        )

        self.assertEqual(len(df), 2)
        self.assertEqual(df["bairro"].isna().sum(), 1)
        self.assertEqual(df["situacao_categoria"].isna().sum(), 1)

    def test_agregado_soma_total(self) -> None:
        df = self.t.transform_demandas_156(
            [
                registro(NUMERO="1"),
                registro(NUMERO="2"),
                registro(NUMERO="3", SITUACAO="Cancelado"),
            ]
        )

        agregado = self.t.agregar_para_dashboard(df)

        self.assertEqual(agregado["total"].sum(), 3)
        self.assertEqual(len(agregado), 2)

    def test_nulos_nao_eliminam_linha_nem_viram_zero(self):
        df = self.t.transform_demandas_156(
            [
                registro(
                    DATA_DEMANDA="...",
                    DATA_ULT_SITUACAO="N/A",
                    SERVICO_DESCRICAO="-",
                    GRUPOSERVICO_DESCRICAO="",
                    RPA="N/A",
                    SITUACAO="...",
                    latitude=None,
                    longitude=None,
                )
            ]
        )
        self.assertEqual(len(df), 1)
        for column in (
            "data_demanda",
            "data_ultima_situacao",
            "servico",
            "grupo_servico",
            "rpa",
            "situacao",
            "concluida",
            "latitude",
            "longitude",
            "tempo_resolucao_dias",
        ):
            self.assertTrue(pd.isna(df.loc[0, column]), column)
        ag = self.t.agregar_para_dashboard(df)
        self.assertEqual(ag["total"].sum(), 1)
        self.assertTrue(ag["tempo_medio_dias"].isna().all())

    def test_categorias_da_fonte_real(self):
        for situacao in (
            "PREPARACAO",
            "EXECUCAO",
            "PENDENCIA",
            "FISCALIZACAO",
            "CADASTRADA",
        ):
            self.assertEqual(self.t._categorizar_situacao(situacao), "Em andamento")
        self.assertEqual(self.t._categorizar_situacao("ATENDIDA"), "Concluída")

    def test_preserva_metadados_e_campos_novos(self):
        df = self.t.transform_demandas_156(
            [
                registro(
                    id_origem=42,
                    carga_id="abc",
                    data_extracao="2026-10-23T12:00:00Z",
                    CAMPO_NOVO="valor",
                )
            ]
        )
        self.assertEqual(df.loc[0, "id_origem"], "42")
        self.assertEqual(df.loc[0, "carga_id"], "abc")
        self.assertEqual(df.loc[0, "campo_novo"], "valor")
        self.assertTrue(pd.notna(df.loc[0, "data_extracao"]))


if __name__ == "__main__":
    unittest.main()
