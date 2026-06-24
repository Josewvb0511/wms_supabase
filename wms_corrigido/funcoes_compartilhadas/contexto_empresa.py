# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_logado, usuario_admin


def _to_int(valor):
    try:
        return int(valor)
    except Exception:
        return None


def carregar_empresas_usuario() -> pd.DataFrame:
    usuario = usuario_logado()
    if not usuario:
        return pd.DataFrame()

    try:
        df_emp = conversa_banco.select("empresas", filtros={"ativo": True}, order_by="nome")
    except Exception:
        return pd.DataFrame()

    if df_emp is None or df_emp.empty:
        return pd.DataFrame()

    if usuario_admin():
        return df_emp.copy()

    usuario_id = _to_int(usuario.get("id"))
    if usuario_id is None:
        return pd.DataFrame()

    try:
        df_perm = conversa_banco.select("usuario_empresas", filtros={"usuario_id": usuario_id, "ativo": True})
    except Exception:
        return pd.DataFrame()

    if df_perm is None or df_perm.empty or "empresa_id" not in df_perm.columns:
        return pd.DataFrame()

    ids = set(pd.to_numeric(df_perm["empresa_id"], errors="coerce").dropna().astype(int).tolist())
    return df_emp[pd.to_numeric(df_emp["id"], errors="coerce").astype("Int64").isin(ids)].copy()


def selecionar_empresas_sidebar():
    df_emp = carregar_empresas_usuario()

    if df_emp.empty:
        st.sidebar.error("Usuário sem empresa liberada.")
        st.stop()

    df_emp = df_emp.copy()
    df_emp["rotulo"] = df_emp["codigo"].astype(str).str.upper() + " - " + df_emp["nome"].astype(str)
    mapa = dict(zip(df_emp["rotulo"], df_emp["id"]))

    opcoes = df_emp["rotulo"].tolist()
    padrao = st.session_state.get("empresas_selecionadas_rotulos")
    if not padrao:
        padrao = opcoes

    selecionadas = st.sidebar.multiselect(
        "Empresas do estoque",
        options=opcoes,
        default=[x for x in padrao if x in opcoes] or opcoes,
        key="empresas_selecionadas_rotulos",
    )

    if not selecionadas:
        st.sidebar.warning("Selecione pelo menos uma empresa.")
        st.stop()

    ids = [int(mapa[x]) for x in selecionadas]
    st.session_state["empresas_selecionadas_ids"] = ids
    return ids


def empresas_selecionadas_ids() -> list[int]:
    ids = st.session_state.get("empresas_selecionadas_ids", [])
    return [int(x) for x in ids if _to_int(x) is not None]


def empresa_operacional_obrigatoria() -> int:
    ids = empresas_selecionadas_ids()
    if len(ids) != 1:
        st.error("Para lançar entrada, saída, movimentação ou inventário selecione apenas 1 empresa no menu lateral.")
        st.stop()
    return int(ids[0])


def filtrar_df_empresas(df: pd.DataFrame, coluna: str = "empresa_id") -> pd.DataFrame:
    if df is None or df.empty or coluna not in df.columns:
        return df

    ids = empresas_selecionadas_ids()
    if not ids:
        return df.iloc[0:0].copy()

    df = df.copy()
    serie = pd.to_numeric(df[coluna], errors="coerce").astype("Int64")
    return df[serie.isin(ids)].copy()
