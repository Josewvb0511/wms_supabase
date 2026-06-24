# -*- coding: utf-8 -*-

import streamlit as st
import importlib

from funcoes_compartilhadas.controle_acesso import (
    login,
    logout,
    usuario_logado,
    usuario_admin,
)
from funcoes_compartilhadas.contexto_empresa import selecionar_empresas_sidebar

st.set_page_config(
    page_title="WMS - Controle de Estoque",
    layout="wide"
)


def carregar_pagina(nome_arquivo):
    try:
        modulo = importlib.import_module(f"paginas.{nome_arquivo}")
        importlib.reload(modulo)
        modulo.app()
    except Exception as e:
        st.error(f"Erro ao carregar página: {e}")


# ==========================================================
# FLUXO DE REDEFINIÇÃO DE SENHA
# ==========================================================
if st.query_params.get("recuperar", "") == "1":
    carregar_pagina("redefinir_senha")
    st.stop()


# ==========================================================
# LOGIN
# ==========================================================
usuario = usuario_logado()

if not usuario:
    login()
    st.stop()


# ==========================================================
# SIDEBAR
# ==========================================================
st.sidebar.title("📦 WMS")

# Seleção multiempresa aplicada ao estoque
selecionar_empresas_sidebar()


if usuario_admin():
    areas_disponiveis = ["Operações", "Administração"]
else:
    areas_disponiveis = ["Operações"]

area = st.sidebar.selectbox("Área", areas_disponiveis)

st.sidebar.write("")


# ==========================================================
# MENU OPERAÇÕES
# ==========================================================
if area == "Operações":
    menu = st.sidebar.radio(
        "Funcionalidade",
        [
            "Selecionar...",
            "Entrada",
            "Saída",
            "Movimentação",
            "Extrato",
            "Saldos",
            "Inventário",
        ]
    )


# ==========================================================
# MENU ADMINISTRAÇÃO
# ==========================================================
else:
    menu = st.sidebar.radio(
        "Funcionalidade",
        [
            "Selecionar...",
            "Cadastros",
            "Empresas",
            "Parâmetros",
        ]
    )


# ==========================================================
# LOGOUT
# ==========================================================
logout()


# ==========================================================
# ROTAS OPERAÇÕES
# ==========================================================
if menu == "Entrada":
    carregar_pagina("wms_entrada")

elif menu == "Saída":
    carregar_pagina("wms_saida")

elif menu == "Movimentação":
    carregar_pagina("wms_movimentacao")

elif menu == "Extrato":
    carregar_pagina("wms_extrato")

elif menu == "Saldos":
    carregar_pagina("wms_saldos")

elif menu == "Inventário":
    carregar_pagina("wms_inventario")


# ==========================================================
# ROTAS ADMINISTRAÇÃO
# ==========================================================
elif menu == "Cadastros":
    if not usuario_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    carregar_pagina("wms_cadastros")

elif menu == "Empresas":
    if not usuario_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    carregar_pagina("wms_empresas")

elif menu == "Parâmetros":
    if not usuario_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    carregar_pagina("wms_parametros")


# ==========================================================
# TELA INICIAL
# ==========================================================
else:
    st.title("📦 WMS - Controle de Estoque")
    st.success("Sistema rodando com sucesso 🚀")
    st.info("Escolha uma funcionalidade no menu lateral.")