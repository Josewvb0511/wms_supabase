# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import hash_senha


def app():
    st.title("🔑 Redefinir Senha")

    token = st.query_params.get("token", "")

    if not token:
        st.error("Token inválido ou não informado.")
        st.stop()

    df = conversa_banco.select("usuarios")

    if df.empty:
        st.error("Nenhum usuário encontrado.")
        st.stop()

    if "reset_token" not in df.columns or "reset_token_expira_em" not in df.columns:
        st.error("A tabela de usuários não tem as colunas de redefinição.")
        st.stop()

    df = df[df["reset_token"].astype(str) == str(token)]

    if df.empty:
        st.error("Token inválido.")
        st.stop()

    usuario = df.iloc[0]

    expira_em = usuario["reset_token_expira_em"]

    try:
        expira_dt = pd.to_datetime(expira_em)
        agora = pd.Timestamp.now()
    except Exception:
        st.error("Token inválido.")
        st.stop()

    if agora > expira_dt:
        st.error("Esse link já expirou.")
        st.stop()

    nova_senha = st.text_input("Nova senha", type="password")
    confirmar_senha = st.text_input("Confirmar nova senha", type="password")

    if st.button("Salvar nova senha", use_container_width=True):
        if not nova_senha.strip() or not confirmar_senha.strip():
            st.error("Preencha os dois campos.")
            return

        if nova_senha != confirmar_senha:
            st.error("As senhas não conferem.")
            return

        try:
            conversa_banco.update(
                "usuarios",
                {
                    "senha": hash_senha(nova_senha.strip()),
                    "reset_token": None,
                    "reset_token_expira_em": None,
                },
                {"id": usuario["id"]}
            )

            st.success("Senha redefinida com sucesso. Agora você já pode voltar e fazer login.")
        except Exception as e:
            st.error(f"Erro ao salvar nova senha: {e}")