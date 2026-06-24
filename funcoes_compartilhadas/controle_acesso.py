# -*- coding: utf-8 -*-
import hashlib
import secrets
from datetime import datetime, timedelta
import os

import streamlit as st
from dotenv import load_dotenv

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.envia_email import enviar_email


load_dotenv("credenciais/.env")

TABELA_USUARIOS = "usuarios"


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def usuario_logado():
    return st.session_state.get("usuario_logado")


def usuario_admin() -> bool:
    usuario = usuario_logado()
    if not usuario:
        return False
    return str(usuario.get("perfil", "")).strip().upper() == "ADMINISTRADOR"


def solicitar_reset_senha(nome_usuario: str):
    df = conversa_banco.select(TABELA_USUARIOS, filtros={"ativo": True})

    if df.empty:
        return

    if "nome" not in df.columns or "email" not in df.columns:
        return

    df = df[df["nome"].astype(str).str.lower() == nome_usuario.strip().lower()]

    if df.empty:
        return

    usuario = df.iloc[0]
    email = str(usuario["email"]).strip()

    if not email:
        return

    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now() + timedelta(hours=1)).isoformat()

    conversa_banco.update(
        TABELA_USUARIOS,
        {
            "reset_token": token,
            "reset_token_expira_em": expira_em,
        },
        {"id": usuario["id"]}
    )

    base_url = os.getenv("APP_BASE_URL", "http://localhost:8501").strip()
    link_reset = f"{base_url}/?recuperar=1&token={token}"

    mensagem = f"""
    <p>Olá, {usuario['nome']}.</p>
    <p>Você solicitou a redefinição da sua senha no WMS.</p>
    <p>Clique no link abaixo para cadastrar uma nova senha:</p>
    <p><a href="{link_reset}">{link_reset}</a></p>
    <p>Esse link expira em 1 hora.</p>
    <p>Se você não pediu isso, ignore este e-mail.</p>
    """

    enviar_email(
        destinatario=email,
        assunto="WMS - Redefinição de senha",
        mensagem_html=mensagem
    )


def login():
    st.title("🔐 Login do WMS")

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        nome = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar", use_container_width=True):
            if not nome.strip() or not senha.strip():
                st.error("Preencha usuário e senha.")
                return

            df = conversa_banco.select(TABELA_USUARIOS, filtros={"ativo": True})

            if df.empty:
                st.error("Nenhum usuário ativo cadastrado no banco.")
                return

            if "nome" not in df.columns or "senha" not in df.columns:
                st.error("Tabela de usuários inválida.")
                return

            df = df[df["nome"].astype(str).str.lower() == nome.strip().lower()]

            if df.empty:
                st.error("Usuário não encontrado.")
                return

            senha_digitada = hash_senha(senha.strip())
            senha_banco = str(df.iloc[0]["senha"]).strip()

            if senha_digitada != senha_banco:
                st.error("Senha incorreta.")
                return

            perfil = "USUARIO"
            if "perfil" in df.columns:
                perfil = str(df.iloc[0]["perfil"]).strip().upper() or "USUARIO"

            st.session_state["usuario_logado"] = {
                "id": df.iloc[0]["id"] if "id" in df.columns else "",
                "nome": df.iloc[0]["nome"],
                "perfil": perfil,
            }

            st.success("Login realizado com sucesso.")
            st.rerun()

        st.write("")

        with st.expander("Esqueci minha senha"):
            nome_reset = st.text_input("Digite seu usuário", key="nome_reset")

            if st.button("Enviar link de redefinição", use_container_width=True):
                try:
                    solicitar_reset_senha(nome_reset)
                    st.success("Se o usuário existir e tiver e-mail cadastrado, enviaremos um link de redefinição.")
                except Exception as e:
                    st.error(f"Erro ao enviar e-mail: {e}")


def logout():
    st.sidebar.write("---")

    usuario = usuario_logado()
    if usuario:
        st.sidebar.write(f"Usuário: {usuario['nome']}")
        st.sidebar.write(f"Perfil: {usuario.get('perfil', 'USUARIO')}")

    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()