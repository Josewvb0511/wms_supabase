# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_admin


def _to_bool(valor):
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ["true", "1", "sim", "s", "ativo"]


def _df(tabela, filtros=None, order_by=None):
    try:
        return conversa_banco.select(tabela, filtros=filtros, order_by=order_by)
    except Exception:
        return pd.DataFrame()


def _normalizar_empresas(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "codigo", "nome", "cnpj", "ativo"])
    df = df.copy()
    for col, padrao in {"id": 0, "codigo": "", "nome": "", "cnpj": "", "ativo": True}.items():
        if col not in df.columns:
            df[col] = padrao
    df["codigo"] = df["codigo"].fillna("").astype(str).str.strip().str.upper()
    df["nome"] = df["nome"].fillna("").astype(str).str.strip()
    df["cnpj"] = df["cnpj"].fillna("").astype(str).str.strip()
    df["ativo"] = df["ativo"].apply(_to_bool)
    return df


def _normalizar_usuarios(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "nome", "email", "ativo"])
    df = df.copy()
    for col, padrao in {"id": 0, "nome": "", "email": "", "ativo": True}.items():
        if col not in df.columns:
            df[col] = padrao
    df["ativo"] = df["ativo"].apply(_to_bool)
    return df


def _aba_empresas():
    st.subheader("Cadastro de Empresas")

    with st.form("form_empresa", enter_to_submit=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            codigo = st.text_input("Código", placeholder="Ex: SIDER")
        with col2:
            nome = st.text_input("Nome", placeholder="Ex: Siderquímica")
        with col3:
            cnpj = st.text_input("CNPJ")
        with col4:
            ativo = st.checkbox("Ativo", value=True)

        if st.form_submit_button("Salvar Empresa"):
            if not codigo.strip() or not nome.strip():
                st.error("Código e nome são obrigatórios.")
            else:
                try:
                    conversa_banco.insert("empresas", {
                        "codigo": codigo.strip().upper(),
                        "nome": nome.strip(),
                        "cnpj": cnpj.strip(),
                        "ativo": bool(ativo),
                    })
                    st.success("Empresa salva com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar empresa: {e}")

    df_emp = _normalizar_empresas(_df("empresas", order_by="nome"))
    if df_emp.empty:
        st.info("Nenhuma empresa cadastrada.")
        return

    editor = st.data_editor(
        df_emp[["id", "codigo", "nome", "cnpj", "ativo"]],
        use_container_width=True,
        hide_index=True,
        key="editor_empresas",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "codigo": st.column_config.TextColumn("Código"),
            "nome": st.column_config.TextColumn("Nome"),
            "cnpj": st.column_config.TextColumn("CNPJ"),
            "ativo": st.column_config.CheckboxColumn("Ativo"),
        },
    )

    if st.button("Salvar alterações de empresas"):
        try:
            original = df_emp[["id", "codigo", "nome", "cnpj", "ativo"]].reset_index(drop=True)
            editado = editor.reset_index(drop=True)
            for i in range(len(editado)):
                rid = int(original.iloc[i]["id"])
                dados = {}
                for col in ["codigo", "nome", "cnpj", "ativo"]:
                    if str(original.iloc[i][col]) != str(editado.iloc[i][col]):
                        dados[col] = editado.iloc[i][col]
                if dados:
                    if "codigo" in dados:
                        dados["codigo"] = str(dados["codigo"]).strip().upper()
                    conversa_banco.update("empresas", dados, {"id": rid})
            st.success("Empresas atualizadas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao atualizar empresas: {e}")


def _aba_usuario_empresas():
    st.subheader("Empresas liberadas por usuário")

    df_user = _normalizar_usuarios(_df("usuarios", filtros={"ativo": True}, order_by="nome"))
    df_emp = _normalizar_empresas(_df("empresas", filtros={"ativo": True}, order_by="nome"))

    if df_user.empty or df_emp.empty:
        st.info("Cadastre usuários e empresas ativas primeiro.")
        return

    user_map = {f'{r["nome"]} | {r["email"]}': int(r["id"]) for _, r in df_user.iterrows()}
    emp_map = {f'{r["codigo"]} - {r["nome"]}': int(r["id"]) for _, r in df_emp.iterrows()}

    usuario_rotulo = st.selectbox("Usuário", list(user_map.keys()))
    usuario_id = user_map[usuario_rotulo]

    df_perm = _df("usuario_empresas", filtros={"usuario_id": usuario_id, "ativo": True})
    ids_atuais = []
    if df_perm is not None and not df_perm.empty and "empresa_id" in df_perm.columns:
        ids_atuais = pd.to_numeric(df_perm["empresa_id"], errors="coerce").dropna().astype(int).tolist()

    padrao = [rot for rot, eid in emp_map.items() if eid in ids_atuais]
    selecionadas = st.multiselect("Empresas que este usuário pode visualizar", list(emp_map.keys()), default=padrao)

    if st.button("Salvar empresas do usuário"):
        try:
            # desativa permissões atuais
            if df_perm is not None and not df_perm.empty and "id" in df_perm.columns:
                for pid in pd.to_numeric(df_perm["id"], errors="coerce").dropna().astype(int).tolist():
                    conversa_banco.update("usuario_empresas", {"ativo": False}, {"id": int(pid)})

            for rotulo in selecionadas:
                empresa_id = emp_map[rotulo]
                conversa_banco.upsert(
                    "usuario_empresas",
                    {"usuario_id": usuario_id, "empresa_id": empresa_id, "ativo": True},
                    on_conflict="usuario_id,empresa_id",
                )
            st.success("Permissões de empresas atualizadas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar permissões: {e}")


def app():
    st.title("🏢 Empresas")

    if not usuario_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    aba1, aba2 = st.tabs(["Empresas", "Usuário x Empresas"])
    with aba1:
        _aba_empresas()
    with aba2:
        _aba_usuario_empresas()
