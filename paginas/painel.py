# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.wms_regras import calcular_saldo_por_localizacao


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
def _garantir_coluna(df: pd.DataFrame, coluna: str, valor_padrao="") -> pd.DataFrame:
    if coluna not in df.columns:
        df[coluna] = valor_padrao
    return df


def _normalizar_texto(df: pd.DataFrame, colunas: list[str], upper: bool = False) -> pd.DataFrame:
    for coluna in colunas:
        df = _garantir_coluna(df, coluna, "")
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()
        if upper:
            df[coluna] = df[coluna].str.upper()
    return df


def _normalizar_numero(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    df = _garantir_coluna(df, coluna, 0)
    df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)
    return df


def _montar_cards(kpi_1, kpi_2, kpi_3, kpi_4):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📦 Saldo Total", f"{kpi_1:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    with col2:
        st.metric("🧾 Produtos com Saldo", int(kpi_2))

    with col3:
        st.metric("📍 Localizações Ocupadas", int(kpi_3))

    with col4:
        st.metric("🏷️ Lotes Ativos", int(kpi_4))


def _top_produtos(df_saldo: pd.DataFrame) -> pd.DataFrame:
    if df_saldo.empty:
        return pd.DataFrame()

    base = df_saldo.copy()
    base = _normalizar_texto(base, ["produto_codigo"], upper=True)
    base = _normalizar_numero(base, "saldo")

    agrupado = (
        base.groupby(["produto_codigo"], as_index=False)["saldo"]
        .sum()
        .sort_values(by="saldo", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    agrupado.index = agrupado.index + 1
    return agrupado


def _top_localizacoes(df_saldo: pd.DataFrame) -> pd.DataFrame:
    if df_saldo.empty:
        return pd.DataFrame()

    base = df_saldo.copy()
    base = _normalizar_texto(base, ["localizacao_codigo"], upper=True)
    base = _normalizar_numero(base, "saldo")

    agrupado = (
        base.groupby(["localizacao_codigo"], as_index=False)["saldo"]
        .sum()
        .sort_values(by="saldo", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    agrupado.index = agrupado.index + 1
    return agrupado


def _produtos_sem_movimento_recentes(df_mov: pd.DataFrame, dias: int = 7) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    base = df_mov.copy()
    base = _normalizar_texto(base, ["produto_codigo"], upper=True)
    base = _garantir_coluna(base, "data_hora", None)

    base["data_hora"] = pd.to_datetime(base["data_hora"], errors="coerce")
    limite = pd.Timestamp.now() - pd.Timedelta(days=dias)

    recentes = base[base["data_hora"] >= limite].copy()

    if recentes.empty:
        return pd.DataFrame()

    agrupado = (
        recentes.groupby("produto_codigo", as_index=False)
        .size()
        .rename(columns={"size": "movimentacoes"})
        .sort_values(by=["movimentacoes", "produto_codigo"], ascending=[True, True])
        .head(10)
        .reset_index(drop=True)
    )

    agrupado.index = agrupado.index + 1
    return agrupado


def _ultimas_movimentacoes(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    base = df_mov.copy()

    colunas = [
        "data_hora",
        "tipo",
        "produto_codigo",
        "quantidade",
        "localizacao_codigo",
        "localizacao_origem_codigo",
        "localizacao_destino_codigo",
        "lote",
        "status",
        "usuario",
        "observacao",
    ]

    for coluna in colunas:
        base = _garantir_coluna(base, coluna, "")

    base = _normalizar_texto(
        base,
        [
            "tipo",
            "produto_codigo",
            "localizacao_codigo",
            "localizacao_origem_codigo",
            "localizacao_destino_codigo",
            "lote",
            "status",
            "usuario",
            "observacao",
        ],
        upper=False,
    )

    base["quantidade"] = pd.to_numeric(base["quantidade"], errors="coerce").fillna(0.0)
    base["data_hora"] = pd.to_datetime(base["data_hora"], errors="coerce")

    base = base.sort_values(by="data_hora", ascending=False).head(20).copy()

    base["data_hora"] = base["data_hora"].dt.strftime("%d/%m/%Y %H:%M:%S")
    base = base.rename(
        columns={
            "data_hora": "Data/Hora",
            "tipo": "Tipo",
            "produto_codigo": "Produto",
            "quantidade": "Quantidade",
            "localizacao_codigo": "Localização",
            "localizacao_origem_codigo": "Origem",
            "localizacao_destino_codigo": "Destino",
            "lote": "Lote",
            "status": "Status",
            "usuario": "Usuário",
            "observacao": "Observação",
        }
    )

    return base[
        ["Data/Hora", "Tipo", "Produto", "Quantidade", "Localização", "Origem", "Destino", "Lote", "Status", "Usuário", "Observação"]
    ]


def app():
    st.title("📊 Painel Operacional do WMS")
    st.caption("Leitura rápida do estoque, movimentações e ocupação do armazém.")

    # ==========================================================
    # BUSCA DE DADOS
    # ==========================================================
    try:
        df_mov = conversa_banco.select("movimentacoes", order_by="data_hora")
    except Exception:
        df_mov = conversa_banco.select("movimentacoes")

    try:
        df_prod = conversa_banco.select("produtos", order_by="codigo")
    except Exception:
        df_prod = conversa_banco.select("produtos")

    try:
        df_loc = conversa_banco.select("localizacoes", order_by="codigo")
    except Exception:
        df_loc = conversa_banco.select("localizacoes")

    df_saldo = calcular_saldo_por_localizacao()

    if df_saldo.empty:
        st.warning("Ainda não existe saldo consolidado para exibir no painel.")
        return

    # ==========================================================
    # PADRONIZAÇÃO
    # ==========================================================
    df_saldo = df_saldo.copy()

    for coluna in ["produto_codigo", "localizacao_codigo", "lote", "status", "observacao"]:
        df_saldo = _garantir_coluna(df_saldo, coluna, "")

    df_saldo = _normalizar_texto(
        df_saldo,
        ["produto_codigo", "localizacao_codigo", "lote", "status"],
        upper=True
    )
    df_saldo = _normalizar_texto(df_saldo, ["observacao"], upper=False)
    df_saldo = _normalizar_numero(df_saldo, "saldo")

    df_saldo = df_saldo[df_saldo["saldo"] > 0].copy()

    if df_saldo.empty:
        st.info("Não existem posições com saldo positivo no momento.")
        return

    # ==========================================================
    # FILTROS DO PAINEL
    # ==========================================================
    st.write("### Filtros")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        filtro_produto = st.text_input("Produto")

    with col2:
        filtro_localizacao = st.text_input("Localização")

    with col3:
        lista_status = ["TODOS"] + sorted(
            [x for x in df_saldo["status"].dropna().astype(str).unique().tolist() if x.strip()]
        )
        filtro_status = st.selectbox("Status", lista_status)

    with col4:
        lista_lotes = ["TODOS"] + sorted(
            [x for x in df_saldo["lote"].dropna().astype(str).unique().tolist() if x.strip()]
        )
        filtro_lote = st.selectbox("Lote", lista_lotes)

    df_painel = df_saldo.copy()

    if filtro_produto.strip():
        df_painel = df_painel[
            df_painel["produto_codigo"].astype(str).str.contains(
                filtro_produto.strip(),
                case=False,
                na=False
            )
        ]

    if filtro_localizacao.strip():
        df_painel = df_painel[
            df_painel["localizacao_codigo"].astype(str).str.contains(
                filtro_localizacao.strip(),
                case=False,
                na=False
            )
        ]

    if filtro_status != "TODOS":
        df_painel = df_painel[df_painel["status"] == filtro_status]

    if filtro_lote != "TODOS":
        df_painel = df_painel[df_painel["lote"] == filtro_lote]

    if df_painel.empty:
        st.warning("Nenhum dado encontrado com os filtros aplicados.")
        return

    # ==========================================================
    # KPIs
    # ==========================================================
    saldo_total = float(df_painel["saldo"].sum())
    produtos_com_saldo = df_painel["produto_codigo"].nunique()
    localizacoes_ocupadas = df_painel["localizacao_codigo"].nunique()
    lotes_ativos = df_painel["lote"].replace("", pd.NA).dropna().nunique()

    _montar_cards(
        saldo_total,
        produtos_com_saldo,
        localizacoes_ocupadas,
        lotes_ativos,
    )

    st.divider()

    # ==========================================================
    # RESUMO ESTRUTURAL
    # ==========================================================
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        total_produtos_cadastrados = 0 if df_prod.empty else len(df_prod)
        st.info(f"**Produtos cadastrados:** {total_produtos_cadastrados}")

    with col_b:
        total_localizacoes_cadastradas = 0 if df_loc.empty else len(df_loc)
        st.info(f"**Localizações cadastradas:** {total_localizacoes_cadastradas}")

    with col_c:
        total_movimentacoes = 0 if df_mov.empty else len(df_mov)
        st.info(f"**Movimentações registradas:** {total_movimentacoes}")

    # ==========================================================
    # BLOCOS ANALÍTICOS
    # ==========================================================
    col1, col2 = st.columns(2)

    with col1:
        st.write("### 🔝 Top 10 Produtos com Maior Saldo")
        df_top_produtos = _top_produtos(df_painel)
        if df_top_produtos.empty:
            st.info("Nada para exibir.")
        else:
            st.dataframe(df_top_produtos, use_container_width=True, hide_index=False)

    with col2:
        st.write("### 📍 Top 10 Localizações com Maior Saldo")
        df_top_local = _top_localizacoes(df_painel)
        if df_top_local.empty:
            st.info("Nada para exibir.")
        else:
            st.dataframe(df_top_local, use_container_width=True, hide_index=False)

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        st.write("### 🕒 Últimas 20 Movimentações")
        df_ultimas = _ultimas_movimentacoes(df_mov)
        if df_ultimas.empty:
            st.info("Nenhuma movimentação encontrada.")
        else:
            st.dataframe(df_ultimas, use_container_width=True, hide_index=True)

    with col4:
        st.write("### 🚨 Produtos com Menos Movimento nos Últimos 7 Dias")
        df_sem_mov = _produtos_sem_movimento_recentes(df_mov, dias=7)
        if df_sem_mov.empty:
            st.info("Sem dados suficientes para análise.")
        else:
            st.dataframe(df_sem_mov, use_container_width=True, hide_index=False)

    st.divider()

    # ==========================================================
    # DETALHE OPERACIONAL
    # ==========================================================
    st.write("### 📦 Detalhe do Saldo Atual")

    detalhe = df_painel.copy()
    detalhe = detalhe.rename(
        columns={
            "produto_codigo": "Produto",
            "localizacao_codigo": "Localização",
            "lote": "Lote",
            "status": "Status",
            "observacao": "Observação",
            "saldo": "Saldo",
        }
    )

    colunas_final = ["Produto", "Localização", "Lote", "Status", "Observação", "Saldo"]
    colunas_final = [col for col in colunas_final if col in detalhe.columns]

    st.dataframe(
        detalhe[colunas_final].sort_values(by=colunas_final[:2]).reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )