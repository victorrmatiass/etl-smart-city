"""Teste de interface em memória, sem credenciais e sem gravar no Neon."""

import contextlib
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.transform import Transform
from tests.test_transform import registro

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        df = Transform().transform_demandas_156(
            [
                registro(
                    id_origem=1,
                    SITUACAO="ATENDIDA",
                    data_extracao="2026-10-23T12:00:00Z",
                ),
                registro(
                    id_origem=2,
                    RPA="3",
                    BAIRRO="CASA AMARELA",
                    SITUACAO="EXECUCAO",
                    DATA_DEMANDA="2025-01-10",
                    data_extracao="2026-10-23T12:00:00Z",
                ),
            ]
        )
    auditoria = pd.DataFrame([df.attrs["auditoria"]])
    st.cache_data.clear()
    with patch("dashboard.data.ler_neon", return_value=(df, auditoria)):
        app = AppTest.from_file(APP, default_timeout=45).run()
        assert not app.exception, app.exception
        assert app.metric[0].value == "2"
        assert app.metric[1].value == "50,0%"
        app.multiselect[0].set_value(["6"]).run()
        assert not app.exception, app.exception
        assert app.metric[0].value == "1"
        assert app.metric[1].value == "100,0%"
        app.multiselect[1].set_value(["Casa Amarela"]).run()
        assert not app.exception, app.exception
        assert app.metric[0].value == "0"
        assert app.metric[1].value == "—"
        assert len(app.info) > 0
    st.cache_data.clear()
    with patch(
        "dashboard.data.ler_neon", side_effect=RuntimeError("connection unavailable")
    ):
        app = AppTest.from_file(APP, default_timeout=45).run()
        assert not app.exception, app.exception
        assert len(app.error) == 1
    st.cache_data.clear()
    print(
        "Dashboard OK: inicial, filtro, combinação vazia e indisponibilidade do Neon."
    )


if __name__ == "__main__":
    main()
