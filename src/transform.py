import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional

import pandas as pd


class Transform:
    """
    Responsável por transformar os atendimentos brutos do 156 da EMLURB
    em tabelas limpas, prontas para o app e para o dashboard mobile.

    Gera duas saídas:
      - detalhado: uma linha por demanda (mapa, lista, filtros);
      - agregado: totais por mês / RPA / bairro / grupo de serviço / situação
        (leve o bastante para alimentar gráficos no celular).
    """

    ANO_ALVO = 2026

    # Nome original da coluna (minúsculo) -> nome final no banco.
    RENOMEAR_COLUNAS = {
        "gruposervico_codigo": "grupo_servico_codigo",
        "gruposervico_descricao": "grupo_servico",
        "servico_codigo": "servico_codigo",
        "servico_descricao": "servico",
        "logradouro": "logradouro",
        "numero": "numero",
        "bairro": "bairro",
        "rpa": "rpa",
        "data_demanda": "data_demanda",
        "situacao": "situacao",
        "data_ult_situacao": "data_ultima_situacao",
        "latitude": "latitude",
        "longitude": "longitude",
    }

    # Caixa aproximada de Recife (com folga). Fora dela a coordenada é inválida.
    LATITUDE_MIN, LATITUDE_MAX = -8.25, -7.85
    LONGITUDE_MIN, LONGITUDE_MAX = -35.15, -34.80

    RPA_MIN, RPA_MAX = 1, 6

    # Textos que representam "sem informação" no dado de origem.
    VALORES_NULOS = {"", "NULL", "NONE", "NAN", "NA", "N/A", "-", "NAO INFORMADO"}

    # Variações de "sem número" no campo numero.
    VALORES_SEM_NUMERO = {"0", "00", "S N", "SN", "S/N", "S/N°", "S/NO", "S/Nº"}

    PREPOSICOES = {"de", "da", "do", "das", "dos", "e", "em", "a", "o"}

    DIAS_SEMANA = [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    ]

    # Ordem importa: a primeira categoria cuja palavra-chave aparecer vence.
    # As palavras são comparadas sem acento e em minúsculas.
    # Ajuste aqui se o 156 passar a usar outros nomes de situação.
    CATEGORIAS_SITUACAO = [
        ("Cancelada", ["cancel", "indefer", "improcedent", "duplicad", "arquivad"]),
        (
            "Em andamento",
            [
                "andamento",
                "aguard",
                "pendente",
                "abert",
                "analise",
                "vistoria",
                "programad",
                "agendad",
                "encaminhad",
                "em execu",
                "recebid",
                "registrad",
            ],
        ),
        (
            "Concluída",
            [
                "conclu",
                "execut",
                "atendid",
                "finaliz",
                "resolvid",
                "encerrad",
                "realizad",
            ],
        ),
    ]
    CATEGORIA_PADRAO_SITUACAO = "Outros"

    COLUNAS_FINAIS = [
        "id_demanda",
        "grupo_servico_codigo",
        "grupo_servico",
        "servico_codigo",
        "servico",
        "logradouro",
        "numero",
        "bairro",
        "rpa",
        "latitude",
        "longitude",
        "tem_coordenadas",
        "data_demanda",
        "ano",
        "mes",
        "ano_mes",
        "dia_semana",
        "hora",
        "situacao",
        "situacao_categoria",
        "concluida",
        "data_ultima_situacao",
        "tempo_resolucao_dias",
    ]

    # ------------------------------------------------------------------ #
    # Funções auxiliares
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sem_acento(texto: str) -> str:
        return "".join(
            c
            for c in unicodedata.normalize("NFKD", texto)
            if not unicodedata.combining(c)
        )

    def _limpar_texto(self, valor: Any) -> Optional[str]:
        """
        Remove espaços extras e converte textos vazios ou do tipo
        "NULL" / "NÃO INFORMADO" em None.
        """

        if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
            return None

        texto = re.sub(r"\s+", " ", str(valor)).strip()

        if self._sem_acento(texto).upper() in self.VALORES_NULOS:
            return None

        return texto

    def _titulo(self, valor: Optional[str]) -> Optional[str]:
        """
        Padroniza a caixa de textos que vieram todos em MAIÚSCULAS
        ("RUA DO FUTURO" -> "Rua do Futuro"). Textos que já estão em caixa
        mista são preservados, para não estragar siglas e nomes próprios.
        """

        # O pandas pode transformar None em NaN entre dois .map() seguidos.
        if not isinstance(valor, str):
            return None

        if not valor.isupper():
            return valor

        palavras = valor.lower().split(" ")
        resultado = [
            palavra if (i > 0 and palavra in self.PREPOSICOES) else palavra.capitalize()
            for i, palavra in enumerate(palavras)
        ]

        return " ".join(resultado)

    def _limpar_numero(self, valor: Any) -> Optional[str]:
        texto = self._limpar_texto(valor)

        if texto is None:
            return None

        if self._sem_acento(texto).upper() in self.VALORES_SEM_NUMERO:
            return "S/N"

        return texto

    @staticmethod
    def _para_numero(serie: pd.Series) -> pd.Series:
        """Converte texto com vírgula ou ponto decimal em número."""

        return pd.to_numeric(
            serie.astype("string").str.strip().str.replace(",", ".", regex=False),
            errors="coerce",
        )

    @staticmethod
    def _para_data(serie: pd.Series) -> pd.Series:
        """
        Converte texto em data/hora. Tenta primeiro o formato ISO
        (2026-03-04T10:15:00) e, para o que sobrar, o formato brasileiro
        (04/03/2026 10:15).
        """

        texto = serie.astype("string").str.strip()
        datas = pd.to_datetime(texto, errors="coerce", format="ISO8601")

        pendentes = datas.isna() & texto.notna()

        if pendentes.any():
            datas.loc[pendentes] = pd.to_datetime(
                texto[pendentes],
                errors="coerce",
                dayfirst=True,
                format="mixed",
            )

        # Descarta fuso horário, se existir, para manter tudo "naive".
        if getattr(datas.dt, "tz", None) is not None:
            datas = datas.dt.tz_localize(None)

        return datas

    def _categorizar_situacao(self, situacao: Optional[str]) -> Optional[str]:
        if not isinstance(situacao, str):
            return None

        normalizada = self._sem_acento(situacao).lower()

        for categoria, palavras in self.CATEGORIAS_SITUACAO:
            if any(palavra in normalizada for palavra in palavras):
                return categoria

        return self.CATEGORIA_PADRAO_SITUACAO

    @staticmethod
    def _gerar_id(linha: pd.Series) -> str:
        """
        ID determinístico da demanda. O dataset não tem identificador, então
        ele é calculado a partir do que identifica o atendimento (e NÃO da
        situação, que muda ao longo do tempo). Assim, o mesmo atendimento
        recebe sempre o mesmo ID entre execuções.
        """

        chave = "|".join(
            "" if pd.isna(linha[campo]) else str(linha[campo])
            for campo in (
                "servico_codigo",
                "logradouro",
                "numero",
                "bairro",
                "data_demanda",
                "latitude",
                "longitude",
            )
        )

        return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:20]

    # ------------------------------------------------------------------ #
    # Transformação principal
    # ------------------------------------------------------------------ #

    def transform_demandas_156(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Limpa, padroniza e enriquece os atendimentos do 156.

        Parâmetros:
            data: registros brutos recebidos do Extract ou do MongoDB.

        Retorno:
            DataFrame com uma linha por demanda de `ANO_ALVO`.
        """

        if not data:
            print("Nenhum dado recebido para transformação.")
            return pd.DataFrame(columns=self.COLUNAS_FINAIS)

        bruto = pd.DataFrame(data)
        total_bruto = len(bruto)

        # Padroniza nomes de colunas e remove o _id criado pelo MongoDB.
        bruto.columns = [str(c).strip().lower().lstrip("\ufeff") for c in bruto.columns]
        bruto = bruto.drop(columns=["_id"], errors="ignore")

        ausentes = set(self.RENOMEAR_COLUNAS) - set(bruto.columns)
        if ausentes:
            raise ValueError(
                "O dataset não possui as colunas esperadas: "
                f"{sorted(ausentes)}. Colunas recebidas: {list(bruto.columns)}"
            )

        df = bruto[list(self.RENOMEAR_COLUNAS)].rename(columns=self.RENOMEAR_COLUNAS)

        # --- Textos -----------------------------------------------------
        for coluna in ("grupo_servico", "servico", "logradouro", "bairro"):
            df[coluna] = df[coluna].map(self._limpar_texto).map(self._titulo)

        df["numero"] = df["numero"].map(self._limpar_numero)
        df["situacao"] = df["situacao"].map(self._limpar_texto).map(self._titulo)

        # --- Códigos e RPA ---------------------------------------------
        for coluna in ("grupo_servico_codigo", "servico_codigo"):
            df[coluna] = self._para_numero(df[coluna]).round().astype("Int64")

        rpa = self._para_numero(df["rpa"]).round()
        df["rpa"] = rpa.where(rpa.between(self.RPA_MIN, self.RPA_MAX)).astype("Int64")

        # --- Datas ------------------------------------------------------
        df["data_demanda"] = self._para_data(df["data_demanda"])
        df["data_ultima_situacao"] = self._para_data(df["data_ultima_situacao"])

        sem_data = df["data_demanda"].isna().sum()
        df = df[df["data_demanda"].notna()]

        fora_do_ano = (df["data_demanda"].dt.year != self.ANO_ALVO).sum()
        df = df[df["data_demanda"].dt.year == self.ANO_ALVO].copy()

        # --- Coordenadas -----------------------------------------------
        df["latitude"] = self._para_numero(df["latitude"])
        df["longitude"] = self._para_numero(df["longitude"])

        # Corrige latitude/longitude trocadas.
        trocadas = df["latitude"].between(self.LONGITUDE_MIN, self.LONGITUDE_MAX) & df[
            "longitude"
        ].between(self.LATITUDE_MIN, self.LATITUDE_MAX)
        df.loc[trocadas, ["latitude", "longitude"]] = df.loc[
            trocadas, ["longitude", "latitude"]
        ].values

        coordenada_valida = df["latitude"].between(
            self.LATITUDE_MIN, self.LATITUDE_MAX
        ) & df["longitude"].between(self.LONGITUDE_MIN, self.LONGITUDE_MAX)
        df.loc[~coordenada_valida, ["latitude", "longitude"]] = pd.NA

        df["latitude"] = df["latitude"].round(6)
        df["longitude"] = df["longitude"].round(6)
        df["tem_coordenadas"] = coordenada_valida

        # --- Situação ---------------------------------------------------
        df["situacao_categoria"] = df["situacao"].map(self._categorizar_situacao)
        df["concluida"] = df["situacao_categoria"] == "Concluída"

        # Última situação não pode ser anterior à abertura da demanda.
        invalida = df["data_ultima_situacao"] < df["data_demanda"]
        df.loc[invalida, "data_ultima_situacao"] = pd.NaT

        dias = (df["data_ultima_situacao"] - df["data_demanda"]).dt.total_seconds()
        df["tempo_resolucao_dias"] = (dias / 86400).round(2).where(df["concluida"])

        # --- Colunas derivadas de tempo (facilitam filtros e gráficos) --
        df["ano"] = df["data_demanda"].dt.year.astype("Int64")
        df["mes"] = df["data_demanda"].dt.month.astype("Int64")
        df["ano_mes"] = df["data_demanda"].dt.strftime("%Y-%m")
        df["dia_semana"] = df["data_demanda"].dt.dayofweek.map(
            dict(enumerate(self.DIAS_SEMANA))
        )
        df["hora"] = df["data_demanda"].dt.hour.astype("Int64")

        # --- Qualidade --------------------------------------------------
        # Sem serviço não há o que mostrar no dashboard.
        sem_servico = (df["servico"].isna() & df["grupo_servico"].isna()).sum()
        df = df[df["servico"].notna() | df["grupo_servico"].notna()].copy()

        df["id_demanda"] = df.apply(self._gerar_id, axis=1)

        antes = len(df)
        df = df.drop_duplicates(subset="id_demanda", keep="last")
        duplicadas = antes - len(df)

        df = df[self.COLUNAS_FINAIS].sort_values("data_demanda").reset_index(drop=True)

        print("Atendimentos do 156 transformados com sucesso!")
        print(f"Registros brutos: {total_bruto}")
        print(f"  Descartados sem data da demanda: {sem_data}")
        print(f"  Descartados fora de {self.ANO_ALVO}: {fora_do_ano}")
        print(f"  Descartados sem serviço: {sem_servico}")
        print(f"  Descartados por duplicidade: {duplicadas}")
        print(f"Registros finais: {len(df)} | Colunas: {len(df.columns)}")
        print(f"Com coordenadas válidas: {int(df['tem_coordenadas'].sum())}")
        print("Situações encontradas (original -> categoria):")
        resumo = (
            df.groupby(["situacao", "situacao_categoria"], dropna=False)
            .size()
            .sort_values(ascending=False)
        )
        for (situacao, categoria), total in resumo.items():
            print(f"  {situacao} -> {categoria}: {total}")

        return df

    def agregar_para_dashboard(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera a tabela agregada usada pelo dashboard mobile: total de
        demandas e tempo médio de resolução por mês, RPA, bairro, grupo de
        serviço e categoria de situação.

        Parâmetros:
            df: DataFrame detalhado devolvido por `transform_demandas_156`.

        Retorno:
            DataFrame agregado.
        """

        colunas = [
            "ano_mes",
            "rpa",
            "bairro",
            "grupo_servico_codigo",
            "grupo_servico",
            "situacao_categoria",
        ]

        if df.empty:
            return pd.DataFrame(columns=[*colunas, "total", "tempo_medio_dias"])

        base = df.copy()
        base["bairro"] = base["bairro"].fillna("Não informado")
        base["grupo_servico"] = base["grupo_servico"].fillna("Não informado")
        base["situacao_categoria"] = base["situacao_categoria"].fillna("Outros")

        agregado = (
            base.groupby(colunas, dropna=False)
            .agg(
                total=("id_demanda", "count"),
                tempo_medio_dias=("tempo_resolucao_dias", "mean"),
            )
            .reset_index()
        )
        agregado["tempo_medio_dias"] = agregado["tempo_medio_dias"].round(2)

        print(f"Tabela agregada do dashboard: {len(agregado)} linhas")

        return agregado
