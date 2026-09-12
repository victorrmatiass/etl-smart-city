from typing import Any, Dict, List

import pandas as pd


class Transform:
    """
    Responsável por transformar os dados brutos de mobilidade
    em um DataFrame limpo e organizado para o SQLite.
    """

    # Colunas que representam identificadores
    COLUNAS_IDENTIFICADORAS_MOBILIDADE = (
        "cod_proj",
        "id_gpkg",
    )

    # Percentual mínimo de valores numéricos para conversão
    LIMIAR_DETECCAO_NUMERICA = 0.9

    @staticmethod
    def _limpar_texto(valor: Any) -> Any:
        """
        Remove espaços extras de valores textuais.

        Parâmetros:
            valor: valor que será analisado.

        Retorno:
            Valor sem espaços extras ou None quando estiver vazio.
        """

        if isinstance(valor, str):
            valor = valor.strip()

            if valor:
                return valor

            return None

        return valor

    def _converter_coluna_numerica(
        self,
        serie: pd.Series,
    ) -> pd.Series:
        """
        Converte uma coluna para número quando possível.

        Parâmetros:
            serie: coluna do DataFrame que será analisada.

        Retorno:
            Série original ou convertida para tipo numérico.
        """

        preenchidos = serie.notna()

        if preenchidos.sum() == 0:
            return serie

        convertido = pd.to_numeric(
            serie.astype(str).str.replace(
                ",",
                ".",
                regex=False,
            ),
            errors="coerce",
        )

        taxa_sucesso = (
            convertido[preenchidos]
            .notna()
            .mean()
        )

        if taxa_sucesso < self.LIMIAR_DETECCAO_NUMERICA:
            return serie

        convertido = convertido.where(preenchidos)

        valores = convertido.dropna()

        if (
            not valores.empty
            and (valores % 1 == 0).all()
        ):
            return (
                convertido
                .round()
                .astype("Int64")
            )

        return convertido

    def transform_mobilidade_fichas_projetos(
        self,
        data: List[Dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Limpa e organiza os dados brutos das fichas de mobilidade.

        Parâmetros:
            data: registros brutos recebidos do Extract ou MongoDB.

        Retorno:
            DataFrame limpo e organizado para carga no SQLite.
        """

        if not data:
            print("Nenhum dado recebido para transformação.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Remove o identificador criado automaticamente pelo MongoDB.
        df = df.drop(
            columns=["_id"],
            errors="ignore",
        )

        # Limpa valores textuais.
        df = df.apply(
            lambda coluna: coluna.map(self._limpar_texto)
        )

        # Remove linhas completamente vazias.
        df = df.dropna(how="all")

        # Remove registros duplicados.
        df = df.drop_duplicates()

        # Converte identificadores para inteiro nullable.
        for coluna in self.COLUNAS_IDENTIFICADORAS_MOBILIDADE:
            if coluna in df.columns:
                df[coluna] = (
                    pd.to_numeric(
                        df[coluna],
                        errors="coerce",
                    )
                    .round()
                    .astype("Int64")
                )

        # Tenta converter automaticamente outras colunas numéricas.
        colunas_restantes = [
            coluna
            for coluna in df.columns
            if coluna not in self.COLUNAS_IDENTIFICADORAS_MOBILIDADE
        ]

        for coluna in colunas_restantes:
            df[coluna] = self._converter_coluna_numerica(
                df[coluna]
            )

        df = df.reset_index(drop=True)

        print("Dados de mobilidade transformados com sucesso!")
        print(f"Linhas: {len(df)}")
        print(f"Colunas: {len(df.columns)}")

        return df