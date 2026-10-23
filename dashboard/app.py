"""Execute da raiz: python -m streamlit run dashboard/app.py."""

import sys
from html import escape
from pathlib import Path

# Também funciona quando o runner do Streamlit prioriza dashboard/ no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data import filtrar, indicadores, ler_neon

st.set_page_config(
    page_title="Recife em demandas | Smart City", page_icon="🏙️", layout="wide"
)

TEAL = "#108778"
CORES = {
    "Atendida": "#13957f",
    "Execucao": "#3b79ba",
    "Cadastrada": "#93bfc7",
    "Preparacao": "#e8ad55",
    "Pendencia": "#c77a50",
    "Fiscalizacao": "#777998",
    "Não informado": "#c0c7cb",
}

st.markdown(
    """<style>
.stApp {background:#f5f8f8;color:#163b40}
.block-container {padding-top:2.2rem;padding-bottom:2rem;max-width:1540px}
h1,h2,h3 {letter-spacing:-.035em;color:#123d40}
h1 {font-size:2.75rem!important;font-weight:750!important}
[data-testid="stSidebar"] {background:#eaf3f1;border-right:1px solid #d7e6e1}
[data-testid="stMetric"] {background:white;border:1px solid #dfebe8;border-radius:14px;padding:18px 22px;min-height:126px}
[data-testid="stMetricValue"] {color:#117d70;font-weight:700}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px}
.eyebrow {font-size:12px;font-weight:750;letter-spacing:.16em;color:#117d70;margin:0 0 6px}
.intro {color:#5c7377;font-size:16px;max-width:900px;margin-bottom:20px}
.note {background:#e4f1ed;border-left:3px solid #108778;border-radius:4px;padding:12px 16px;color:#315b57;font-size:14px;margin:16px 0 22px}
.stamp {font-size:12px;color:#65807c;text-align:right}
.status-legend {display:grid;grid-template-columns:1fr 1fr;gap:12px 18px;margin:10px 0 16px;font-size:13px}
.status-legend small {color:#637c7b;display:block;padding-left:16px;margin-top:2px}
</style>""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=600, show_spinner="Consultando as demandas no Neon…")
def carregar_dados():
    return ler_neon()


def numero(n):
    return f"{int(n):,}".replace(",", ".")


def percentual(n):
    return f"{n:.1f}%".replace(".", ",")


def grafico(fig, height=300):
    fig.update_layout(
        height=height,
        margin=dict(l=5, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", color="#385759", size=12),
        separators=",.",
        showlegend=False,
    )
    fig.update_xaxes(title=None, gridcolor="#e8efed", zeroline=False)
    fig.update_yaxes(title=None, gridcolor="#e8efed", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


try:
    base, auditoria = carregar_dados()
except Exception:
    st.title("Recife em demandas")
    st.error(
        "Não foi possível ler a carga no Neon. Confira NEON_DATABASE_URL no .env e execute python run_etl.py antes de abrir o painel."
    )
    st.caption(
        "O painel consulta apenas o Neon. Não usa dados demonstrativos nem troca silenciosamente para um arquivo local."
    )
    if st.button("Tentar novamente"):
        carregar_dados.clear()
        st.rerun()
    st.stop()

if base.empty:
    st.info("A tabela no Neon está vazia. Execute o pipeline para publicar uma carga.")
    st.stop()

datas = base["data_ultima_situacao"].dropna()
periodo = (
    f"{datas.min():%d/%m/%Y} a {datas.max():%d/%m/%Y}"
    if not datas.empty
    else "período não informado"
)
extracao = base["data_extracao"].max()

with st.sidebar:
    st.markdown("### ◉ Smart City")
    st.caption("OBSERVATÓRIO DE DEMANDAS · RECIFE")
    st.divider()
    st.markdown("#### Explore o território")
    st.caption("Sem seleção = todos os registros. Os filtros se combinam.")
    rpas = st.multiselect(
        "RPA",
        sorted(
            base["rpa"]
            .astype("Int64")
            .astype("string")
            .fillna("Não informado")
            .unique()
        ),
    )
    bairros = st.multiselect(
        "Bairro", sorted(base["bairro"].fillna("Não informado").unique())
    )
    grupos = st.multiselect(
        "Grupo de serviço",
        sorted(base["grupo_servico"].fillna("Não informado").unique()),
    )
    situacoes = st.multiselect(
        "Situação na fonte", sorted(base["situacao"].fillna("Não informado").unique())
    )
    abertura = st.selectbox(
        "Abertura da solicitação",
        ["Todas as datas", "Apenas 2026", "Anteriores a 2026", "Sem data"],
    )
    intervalo = None
    if not datas.empty:
        intervalo = st.date_input(
            "Última situação no recorte",
            (datas.min().date(), datas.max().date()),
            min_value=datas.min().date(),
            max_value=datas.max().date(),
            format="DD/MM/YYYY",
        )
    st.divider()
    st.caption("Fonte: Central 156 · EMLURB\n\nPortal de Dados Abertos do Recife")
    if st.button("Atualizar leitura do Neon", width="stretch"):
        carregar_dados.clear()
        st.rerun()
    st.caption(
        "Cache de leitura: até 10 minutos. Atualizar a leitura não executa a ETL."
    )

st.markdown(
    '<p class="eyebrow">SMART CITY / INTELIGÊNCIA TERRITORIAL</p>',
    unsafe_allow_html=True,
)
st.title("Recife em demandas")
st.markdown(
    '<div class="intro">Onde estão as solicitações de serviços urbanos e o que elas revelam sobre cada território?</div>',
    unsafe_allow_html=True,
)
st.caption(f"RECORTE DA ÚLTIMA SITUAÇÃO · {periodo}  |  Fonte: EMLURB / Central 156")
st.markdown(
    '<div class="note">Retrato histórico de registros administrativos. Inclui solicitações abertas em anos anteriores; não representa todas as necessidades da população nem a situação atual dos serviços.</div>',
    unsafe_allow_html=True,
)

inicio = fim = None
if intervalo is not None:
    if len(intervalo) != 2:
        st.info("Selecione a data final para aplicar o período.")
        st.stop()
    # Período completo também preserva registros sem data de última situação.
    if tuple(intervalo) != (datas.min().date(), datas.max().date()):
        inicio, fim = intervalo

df = filtrar(base, rpas, bairros, grupos, situacoes, abertura, inicio, fim)
m = indicadores(df)
st.caption(
    f"{numero(len(df))} de {numero(len(base))} registros na seleção · todos os gráficos e indicadores abaixo respeitam os filtros"
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Solicitações no recorte", numero(m["total"]))
c2.metric(
    "Atendidas no recorte",
    "—" if m["taxa"] is None else f'{m["taxa"]:.1f}%'.replace(".", ","),
    help=f'{numero(m["atendidas"])} atendidas / {numero(m["total"])} registros selecionados. Não é avaliação de SLA.',
)
c3.metric(
    "Em andamento no recorte",
    numero(m["em_andamento"]),
    help="Preparação, execução, pendência, fiscalização e cadastrada, conforme a situação registrada na fonte.",
)
c4.metric("Bairros representados", numero(m["bairros"]))

if df.empty:
    st.info(
        "Nenhuma solicitação corresponde a essa combinação. Remova um filtro para explorar outros registros."
    )
    st.stop()

st.write("")
visao, territorio, qualidade = st.tabs(
    ["Panorama", "Território e serviços", "Dados e metodologia"]
)

with visao:
    left, right = st.columns([1, 1.2])
    with left, st.container(border=True):
        st.subheader("Distribuição por situação")
        st.caption("Situação original registrada pela Central 156")
        cont = (
            df["situacao"]
            .fillna("Não informado")
            .value_counts()
            .rename_axis("Situação")
            .reset_index(name="Solicitações")
        )
        fig = px.pie(
            cont,
            names="Situação",
            values="Solicitações",
            hole=0.72,
            color="Situação",
            color_discrete_map=CORES,
        )
        fig.update_traces(
            textinfo="none",
            hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
        )
        fig.add_annotation(
            text=f"<b>{numero(len(df))}</b><br>solicitações",
            x=0.5,
            y=0.5,
            showarrow=False,
            font_size=21,
        )
        grafico(fig, 270)
        legenda = []
        for situacao, total in cont.itertuples(index=False, name=None):
            cor = CORES.get(situacao, "#777998")
            legenda.append(
                f'<div><span style="color:{cor}">●</span> {escape(situacao)}<small>{numero(total)} · {percentual(total/len(df)*100)}</small></div>'
            )
        st.markdown(
            '<div class="status-legend">' + "".join(legenda) + "</div>",
            unsafe_allow_html=True,
        )
    with right, st.container(border=True):
        st.subheader("Serviços mais solicitados")
        st.caption("Os cinco grupos com maior volume no recorte")
        ranking = (
            df["grupo_servico"]
            .fillna("Não informado")
            .value_counts()
            .head(5)
            .sort_values()
            .rename_axis("Grupo")
            .reset_index(name="Solicitações")
        )
        fig = px.bar(
            ranking,
            x="Solicitações",
            y="Grupo",
            orientation="h",
            text="Solicitações",
            color_discrete_sequence=[TEAL],
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[0, ranking["Solicitações"].max() * 1.2])
        grafico(fig, 340)
        lider = ranking.iloc[-1]
        st.caption(
            f'{lider["Grupo"]} concentra {percentual(lider["Solicitações"]/len(df)*100)} das solicitações selecionadas.'
        )
    left, right = st.columns([1, 1.2])
    with left, st.container(border=True):
        st.subheader("Demandas por RPA")
        st.caption("Regiões político-administrativas · volume absoluto")
        rpa = (
            df["rpa"]
            .astype("Int64")
            .astype("string")
            .fillna("Não informado")
            .value_counts()
            .sort_index()
            .rename_axis("RPA")
            .reset_index(name="Solicitações")
        )
        fig = px.bar(
            rpa,
            x="RPA",
            y="Solicitações",
            text="Solicitações",
            color_discrete_sequence=[TEAL],
        )
        fig.update_xaxes(type="category")
        grafico(fig)
    with right, st.container(border=True):
        st.subheader("Bairros com mais solicitações")
        st.caption("Top 8 · número de registros, sem ajuste pela população")
        ranking = (
            df["bairro"]
            .fillna("Não informado")
            .value_counts()
            .head(8)
            .sort_values()
            .rename_axis("Bairro")
            .reset_index(name="Solicitações")
        )
        fig = px.bar(
            ranking,
            x="Solicitações",
            y="Bairro",
            orientation="h",
            text="Solicitações",
            color_discrete_sequence=["#438f9c"],
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[0, ranking["Solicitações"].max() * 1.2])
        grafico(fig)

with territorio:
    st.subheader("O que cada bairro solicita?")
    st.caption(
        "Compare os grupos de serviço nos 12 bairros com maior volume da seleção."
    )
    top = df["bairro"].value_counts().head(12).index
    top_grupos = df["grupo_servico"].value_counts().head(8).index
    cruzamento = pd.crosstab(df["bairro"], df["grupo_servico"]).reindex(
        index=top, columns=top_grupos, fill_value=0
    )
    if not cruzamento.empty:
        fig = px.imshow(
            cruzamento,
            text_auto=True,
            aspect="auto",
            color_continuous_scale=["#eff6f3", "#108778"],
            labels=dict(x="Grupo de serviço", y="Bairro", color="Solicitações"),
        )
        grafico(fig, 470)
    st.subheader("Solicitações em andamento por bairro")
    st.caption(
        "Situação no recorte histórico; não significa que continuam abertas hoje."
    )
    pendencias = (
        df.assign(em_andamento=df["situacao_categoria"].eq("Em andamento"))
        .groupby("bairro", dropna=False)
        .agg(total=("id_demanda", "size"), em_andamento=("em_andamento", "sum"))
        .reset_index()
    )
    pendencias["participacao_em_andamento"] = (
        pendencias["em_andamento"] / pendencias["total"] * 100
    ).round(1)
    st.dataframe(
        pendencias.sort_values("em_andamento", ascending=False),
        hide_index=True,
        width="stretch",
        column_config={
            "bairro": "Bairro",
            "total": "Total",
            "em_andamento": "Em andamento",
            "participacao_em_andamento": st.column_config.NumberColumn(
                "Em andamento (%)", format="%.1f%%"
            ),
        },
    )
    st.subheader("Quando essas solicitações foram abertas?")
    st.caption(
        "A data de abertura pode ser anterior ao período da última situação. Não é uma série completa da cidade."
    )
    anos = (
        df["data_demanda"]
        .dt.year.dropna()
        .astype(int)
        .value_counts()
        .sort_index()
        .rename_axis("Ano de abertura")
        .reset_index(name="Solicitações")
    )
    grafico(
        px.bar(
            anos, x="Ano de abertura", y="Solicitações", color_discrete_sequence=[TEAL]
        )
    )

with qualidade:
    st.subheader("Uma linha da fonte, uma linha no destino")
    st.caption("Auditoria da carga completa no Neon, antes dos filtros do painel.")
    st.dataframe(auditoria, hide_index=True, width="stretch")
    st.markdown("**Como ler este painel**")
    st.markdown(
        "- A fonte é a **Central 156 da EMLURB**, disponível no portal municipal operado pela EMPREL.\n- A taxa de atendimento é o número de registros classificados como concluídos dividido pelo total selecionado. Não mede cumprimento de prazo.\n- Os rankings mostram solicitações registradas, não necessidades por habitante. Não há denominador populacional nesta base.\n- Datas, bairros e coordenadas ausentes continuam nulos no banco. ‘Não informado’ é apenas um rótulo de exibição.\n- O identificador CKAN representa uma linha do recurso; não é um protocolo oficial de atendimento.\n- A carga bruta é histórica e cumulativa. O painel lê somente o retrato tratado publicado no Neon."
    )
    st.info(
        f'{numero(m["sem_coordenadas"])} registros da seleção não têm coordenadas válidas. Eles permanecem em todos os totais; não exibimos um mapa que possa sugerir cobertura completa.'
    )
    st.caption(
        f"Última extração: {extracao.tz_convert('America/Sao_Paulo'):%d/%m/%Y %H:%M} (Brasília)"
        if pd.notna(extracao)
        else "Data de extração indisponível"
    )
    detalhes = df[
        [
            "bairro",
            "rpa",
            "grupo_servico",
            "servico",
            "situacao",
            "data_demanda",
            "data_ultima_situacao",
        ]
    ]
    detalhes = detalhes.copy()
    detalhes.attrs = {}
    st.dataframe(detalhes, hide_index=True, width="stretch")
    st.download_button(
        "Baixar seleção em CSV",
        detalhes.to_csv(index=False).encode("utf-8-sig"),
        "demandas_recife_selecao.csv",
        "text/csv",
    )

st.caption(
    "SMART CITY · Central 156 / EMLURB · Leitura direta do Neon · Projeto acadêmico, sem vínculo com painel oficial da Prefeitura"
)
