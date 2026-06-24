# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.wms_conversoes import (
    carregar_produtos_para_conversao,
    enriquecer_movimentacoes_com_conversoes,
)
from funcoes_compartilhadas.wms_grupo_logico import montar_saldo_por_grupo_logico


def _normalizar_texto_coluna(df: pd.DataFrame, coluna: str, upper: bool = False) -> pd.DataFrame:
    if coluna in df.columns:
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()
        if upper:
            df[coluna] = df[coluna].str.upper()
    return df


def _definir_tipo_estoque(embalagem: str) -> str:
    embalagem = str(embalagem).strip().upper()

    if embalagem == "GR":
        return "SOBRA / GR"

    return "FECHADOS"


def _definir_detalhe_sobra(row) -> str:
    tipo_estoque = str(row.get("tipo_estoque", "")).strip().upper()

    if tipo_estoque == "SOBRA / GR":
        return str(row.get("grupo_logico_id", "")).strip()

    return ""


def _agrupar_saldos(df: pd.DataFrame, colunas_agrupar: list[str]) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    colunas_soma = ["saldo_embalagem", "saldo_normal", "saldo_convertido"]

    if not colunas_agrupar:
        totais = {coluna: float(df[coluna].sum()) for coluna in colunas_soma}
        totais["unidade_normal"] = ""
        totais["unidade_convertida"] = ""
        return pd.DataFrame([totais])

    colunas_fixas = []

    for coluna in ["detalhe_sobra", "unidade_normal", "unidade_convertida"]:
        if coluna not in colunas_agrupar and coluna in df.columns:
            colunas_fixas.append(coluna)

    agrupamento = (
        df.groupby(colunas_agrupar + colunas_fixas, dropna=False, as_index=False)[colunas_soma]
        .sum()
        .sort_values(by=colunas_agrupar + colunas_fixas)
        .reset_index(drop=True)
    )

    return agrupamento


def app():
    st.title("📦 Saldos por Localização")

    try:
        df_mov = conversa_banco.select("movimentacoes", order_by="data_hora")
    except Exception:
        df_mov = conversa_banco.select("movimentacoes")

    if df_mov is None or df_mov.empty:
        st.warning("Nenhum saldo calculado até o momento.")
        return

    df_prod = carregar_produtos_para_conversao()
    df_enriquecido = enriquecer_movimentacoes_com_conversoes(df_mov, df_prod)

    if df_enriquecido.empty:
        st.warning("Nenhum saldo calculado até o momento.")
        return

    saldo_grupo = montar_saldo_por_grupo_logico(df_enriquecido)

    if saldo_grupo.empty:
        st.info("Nenhum saldo encontrado.")
        return

    if "embalagem" not in saldo_grupo.columns:
        saldo_grupo["embalagem"] = ""

    if "grupo_logico_id" not in saldo_grupo.columns:
        saldo_grupo["grupo_logico_id"] = ""

    saldo_grupo["tipo_estoque"] = saldo_grupo["embalagem"].apply(_definir_tipo_estoque)
    saldo_grupo["detalhe_sobra"] = saldo_grupo.apply(_definir_detalhe_sobra, axis=1)

    saldo = (
        saldo_grupo.groupby(
            [
                "tipo_estoque",
                "detalhe_sobra",
                "produto_codigo",
                "localizacao_codigo",
                "lote",
                "status",
                "unidade_normal",
                "unidade_convertida",
            ],
            as_index=False,
            dropna=False
        )[["saldo_embalagem_final", "saldo_normal_final", "saldo_convertido_final"]]
        .sum()
    )

    saldo = saldo.rename(
        columns={
            "saldo_embalagem_final": "saldo_embalagem",
            "saldo_normal_final": "saldo_normal",
            "saldo_convertido_final": "saldo_convertido",
        }
    )

    if saldo.empty:
        st.info("Nenhum saldo encontrado.")
        return

    colunas_upper = [
        "tipo_estoque",
        "produto_codigo",
        "localizacao_codigo",
        "lote",
        "status",
        "unidade_normal",
        "unidade_convertida",
    ]

    for coluna in colunas_upper:
        saldo = _normalizar_texto_coluna(saldo, coluna, upper=True)

    saldo["detalhe_sobra"] = saldo["detalhe_sobra"].fillna("").astype(str).str.strip()

    for coluna_num in ["saldo_embalagem", "saldo_normal", "saldo_convertido"]:
        if coluna_num in saldo.columns:
            saldo[coluna_num] = pd.to_numeric(saldo[coluna_num], errors="coerce").fillna(0.0)

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        filtro_produto = st.text_input("Filtrar Produto")

    with col2:
        filtro_localizacao = st.text_input("Filtrar Localização")

    with col3:
        filtro_tipo_estoque = st.selectbox(
            "Tipo de Estoque",
            ["TODOS", "FECHADOS", "SOBRA / GR"]
        )

    with col4:
        lista_lotes = ["TODOS"] + sorted(
            [x for x in saldo["lote"].dropna().astype(str).unique().tolist() if x.strip() != ""]
        )
        filtro_lote = st.selectbox("Lote", lista_lotes)

    with col5:
        lista_status = ["TODOS"] + sorted(
            [x for x in saldo["status"].dropna().astype(str).unique().tolist() if x.strip() != ""]
        )
        filtro_status = st.selectbox("Status", lista_status)

    st.write("### Colunas para visualizar e agrupar")

    mapa_rotulos = {
        "tipo_estoque": "Tipo Estoque",
        "detalhe_sobra": "ID Sobra",
        "produto_codigo": "Produto",
        "localizacao_codigo": "Localização",
        "lote": "Lote",
        "status": "Status",
    }

    colunas_disponiveis = [
        col for col in [
            "tipo_estoque",
            "detalhe_sobra",
            "produto_codigo",
            "localizacao_codigo",
            "lote",
            "status",
        ]
        if col in saldo.columns
    ]

    colunas_padrao = [
        col for col in [
            "tipo_estoque",
            "detalhe_sobra",
            "produto_codigo",
            "localizacao_codigo",
            "lote",
            "status",
        ]
        if col in colunas_disponiveis
    ]

    colunas_selecionadas = st.multiselect(
        "Escolha as colunas",
        options=colunas_disponiveis,
        default=colunas_padrao,
        format_func=lambda x: mapa_rotulos.get(x, x),
        key="saldos_colunas_visiveis",
    )

    df = saldo.copy()

    if filtro_produto.strip():
        termo = filtro_produto.strip()
        df = df[df["produto_codigo"].astype(str).str.contains(termo, case=False, na=False)]

    if filtro_localizacao.strip():
        df = df[
            df["localizacao_codigo"].astype(str).str.contains(
                filtro_localizacao.strip(),
                case=False,
                na=False
            )
        ]

    if filtro_tipo_estoque != "TODOS":
        df = df[df["tipo_estoque"].astype(str).str.upper() == filtro_tipo_estoque.upper()]

    if filtro_lote != "TODOS":
        df = df[df["lote"].astype(str).str.upper() == filtro_lote.upper()]

    if filtro_status != "TODOS":
        df = df[df["status"].astype(str).str.upper() == filtro_status.upper()]

    if df.empty:
        st.info("Nenhum saldo encontrado com os filtros informados.")
        return

    df = _agrupar_saldos(df, colunas_selecionadas)

    if df.empty:
        st.info("Nenhum saldo encontrado após o agrupamento.")
        return

    colunas_exibir = list(colunas_selecionadas)

    for coluna in [
        "saldo_embalagem",
        "saldo_normal",
        "unidade_normal",
        "saldo_convertido",
        "unidade_convertida",
    ]:
        if coluna in df.columns:
            colunas_exibir.append(coluna)

    st.dataframe(
        df[colunas_exibir],
        use_container_width=True,
        hide_index=True
    )

    total_embalagem = float(df["saldo_embalagem"].sum()) if "saldo_embalagem" in df.columns else 0.0
    total_normal = float(df["saldo_normal"].sum()) if "saldo_normal" in df.columns else 0.0
    total_convertido = float(df["saldo_convertido"].sum()) if "saldo_convertido" in df.columns else 0.0

    unidade_normal_total = ""
    unidade_convertida_total = ""

    if "unidade_normal" in df.columns and df["unidade_normal"].nunique() == 1:
        unidade_normal_total = df["unidade_normal"].iloc[0]

    if "unidade_convertida" in df.columns and df["unidade_convertida"].nunique() == 1:
        unidade_convertida_total = df["unidade_convertida"].iloc[0]

    st.success(
        f"Saldo total filtrado | "
        f"Embalagens: {total_embalagem:.3f} | "
        f"Normal: {total_normal:.3f} {unidade_normal_total} | "
        f"Convertido: {total_convertido:.3f} {unidade_convertida_total}"
    )