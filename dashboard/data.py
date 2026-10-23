"""Consultas somente de leitura no Neon e filtros compartilhados do painel."""

import pandas as pd
from sqlalchemy import text

from src import config


def ler_neon():
    engine = config.criar_engine_neon()
    try:
        with engine.connect() as conn:
            # Uma única fotografia consistente, mesmo durante uma nova carga ETL.
            conn = conn.execution_options(isolation_level="REPEATABLE READ")
            with conn.begin():
                df = pd.read_sql_query(
                    text(f'SELECT * FROM "{config.TABELA_DEMANDAS}"'), conn
                )
                auditoria = pd.read_sql_query(
                    text(f'SELECT * FROM "{config.TABELA_AUDITORIA}"'), conn
                )
    finally:
        engine.dispose()
    for coluna in ("data_demanda", "data_ultima_situacao"):
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
    df["data_extracao"] = pd.to_datetime(df["data_extracao"], errors="coerce", utc=True)
    return df, auditoria


def filtrar(
    df,
    rpas=(),
    bairros=(),
    grupos=(),
    situacoes=(),
    abertura="Todas as datas",
    inicio=None,
    fim=None,
):
    resultado = df.copy()
    for coluna, selecao in (
        ("rpa", rpas),
        ("bairro", bairros),
        ("grupo_servico", grupos),
        ("situacao", situacoes),
    ):
        if selecao:
            valores = (
                resultado[coluna].astype("Int64").astype("string")
                if coluna == "rpa"
                else resultado[coluna]
            )
            resultado = resultado[valores.fillna("Não informado").isin(selecao)]
    if abertura == "Apenas 2026":
        resultado = resultado[resultado["data_demanda"].dt.year.eq(2026)]
    elif abertura == "Anteriores a 2026":
        resultado = resultado[resultado["data_demanda"].dt.year.lt(2026)]
    elif abertura == "Sem data":
        resultado = resultado[resultado["data_demanda"].isna()]
    if inicio is not None and fim is not None:
        resultado = resultado[
            resultado["data_ultima_situacao"].dt.date.between(inicio, fim)
        ]
    return resultado


def indicadores(df):
    atendidas = int(df["situacao_categoria"].eq("Concluída").sum())
    return {
        "total": len(df),
        "atendidas": atendidas,
        "taxa": atendidas / len(df) * 100 if len(df) else None,
        "em_andamento": int(df["situacao_categoria"].eq("Em andamento").sum()),
        "bairros": int(df["bairro"].nunique()),
        "sem_coordenadas": int(
            (~df["tem_coordenadas"].fillna(False).astype(bool)).sum()
        ),
    }
