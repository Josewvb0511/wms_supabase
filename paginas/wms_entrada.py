# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_logado
from funcoes_compartilhadas.wms_pesos import calcular_quantidades_wms
from funcoes_compartilhadas.wms_grupo_logico import novo_grupo_logico_id


def _to_str(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _to_float(valor):
    if valor is None or valor == "":
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    txt = str(valor).strip().replace(" ", "")

    try:
        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", ".")
        return float(txt)
    except Exception:
        return 0.0


def _normalizar_codigo_texto(valor: str) -> str:
    txt = _to_str(valor).upper()
    txt = txt.replace(";", "/")
    txt = txt.replace("\\", "/")

    while "//" in txt:
        txt = txt.replace("//", "/")

    return txt.strip()


def _normalizar_lote_texto(valor: str) -> str:
    txt = _to_str(valor).upper()
    txt = txt.replace(";", "/")
    txt = txt.replace("\\", "/")

    while "//" in txt:
        txt = txt.replace("//", "/")

    return txt.strip()


def _normalizar_codigo_entrada():
    chave = "entrada_codigo_produto_widget"

    if chave in st.session_state:
        valor_atual = st.session_state[chave]
        valor_corrigido = _normalizar_codigo_texto(valor_atual)

        if valor_corrigido != valor_atual:
            st.session_state[chave] = valor_corrigido


def _normalizar_lote_entrada():
    chave = "entrada_lote_widget"

    if chave in st.session_state:
        valor_atual = st.session_state[chave]
        valor_corrigido = _normalizar_lote_texto(valor_atual)

        if valor_corrigido != valor_atual:
            st.session_state[chave] = valor_corrigido


def _montar_mapa_localizacoes(df_local):
    return {
        f"{str(row.get('setor', '')).upper()} | {str(row.get('codigo', '')).upper()} | {str(row.get('local', '')).upper()}":
        f"{str(row.get('setor', '')).upper()}-{str(row.get('codigo', '')).upper()}-{str(row.get('local', '')).upper()}"
        for _, row in df_local.iterrows()
    }


def _montar_opcoes_embalagem_produto(produto_encontrado):
    opcoes = ["Selecione..."]

    if produto_encontrado is None:
        opcoes.append("GR")
        return opcoes

    emb_produto = _to_str(produto_encontrado.get("emb", "")).upper()

    if emb_produto and emb_produto != "GR":
        opcoes.append(emb_produto)

    opcoes.append("GR")
    return list(dict.fromkeys(opcoes))


def _montar_opcoes_unidade_produto(produto_encontrado):
    opcoes = ["Selecione..."]

    if produto_encontrado is None:
        return opcoes

    unidade_produto = _to_str(produto_encontrado.get("unidade", "")).upper()

    if unidade_produto:
        opcoes.append(unidade_produto)

    return opcoes


@st.cache_data(ttl=60, show_spinner=False)
def _carregar_localizacoes_ativas():
    df_local = conversa_banco.select(
        "localizacoes",
        filtros={"ativo": True},
        order_by="setor"
    )

    if df_local is None or len(df_local) == 0:
        return pd.DataFrame()

    return df_local.copy()


@st.cache_data(ttl=20, show_spinner=False)
def _buscar_produto_por_codigo_cache(codigo_digitado: str):
    codigo = _normalizar_codigo_texto(codigo_digitado)

    if not codigo:
        return pd.DataFrame()

    df_prod = conversa_banco.select(
        "produtos",
        filtros={"codigo": codigo, "ativo": True},
        order_by="id"
    )

    if df_prod is None or len(df_prod) == 0:
        return pd.DataFrame()

    return df_prod.head(1).copy()


def _pegar_produto_encontrado(codigo_digitado: str):
    df = _buscar_produto_por_codigo_cache(codigo_digitado)

    if df.empty:
        return None

    return df.iloc[0]


def _inicializar_estado():
    padroes = {
        "entrada_codigo_produto_widget": "",
        "entrada_localizacao_widget": "Selecione...",
        "entrada_quantidade_widget": 0.0,
        "entrada_lote_widget": "",
        "entrada_embalagem_widget": "Selecione...",
        "entrada_unidade_widget": "Selecione...",
        "entrada_status_widget": "Selecione...",
        "entrada_observacao_widget": "",
        "entrada_codigo_produto_anterior": "",
        "resetar_entrada": False,
    }

    for chave, valor in padroes.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _executar_reset_entrada_se_necessario():
    if not st.session_state.get("resetar_entrada", False):
        return

    st.session_state["entrada_codigo_produto_widget"] = ""
    st.session_state["entrada_localizacao_widget"] = "Selecione..."
    st.session_state["entrada_quantidade_widget"] = 0.0
    st.session_state["entrada_lote_widget"] = ""
    st.session_state["entrada_embalagem_widget"] = "Selecione..."
    st.session_state["entrada_unidade_widget"] = "Selecione..."
    st.session_state["entrada_status_widget"] = "Selecione..."
    st.session_state["entrada_observacao_widget"] = ""
    st.session_state["entrada_codigo_produto_anterior"] = ""
    st.session_state["resetar_entrada"] = False


def _mostrar_mensagens():
    if "msg_sucesso_entrada" in st.session_state:
        st.success(st.session_state["msg_sucesso_entrada"])
        del st.session_state["msg_sucesso_entrada"]

    if "msg_erro_entrada" in st.session_state:
        st.error(st.session_state["msg_erro_entrada"])
        del st.session_state["msg_erro_entrada"]


def app():
    st.title("📥 Entrada de Produtos")

    _inicializar_estado()
    _executar_reset_entrada_se_necessario()
    _mostrar_mensagens()

    df_local = _carregar_localizacoes_ativas()

    if df_local.empty:
        st.warning("Cadastre pelo menos 1 localização ativa em Cadastros.")
        return

    localizacoes = _montar_mapa_localizacoes(df_local)
    opcoes_localizacoes = ["Selecione..."] + list(localizacoes.keys())
    opcoes_status = ["Selecione...", "DISPONIVEL", "BLOQUEADO", "AVARIA"]

    if st.session_state.get("entrada_localizacao_widget") not in opcoes_localizacoes:
        st.session_state["entrada_localizacao_widget"] = "Selecione..."

    if st.session_state.get("entrada_status_widget") not in opcoes_status:
        st.session_state["entrada_status_widget"] = "Selecione..."

    st.caption("Digite ou escaneie o código do produto. Se não tiver leitor, digite manualmente.")

    codigo_digitado = st.text_input(
        "Código do Produto",
        placeholder="Ex: PROD-A",
        key="entrada_codigo_produto_widget",
        on_change=_normalizar_codigo_entrada
    )

    codigo_produto_final = _normalizar_codigo_texto(codigo_digitado)
    produto_encontrado = _pegar_produto_encontrado(codigo_produto_final)

    opcoes_embalagens = _montar_opcoes_embalagem_produto(produto_encontrado)
    opcoes_unidades = _montar_opcoes_unidade_produto(produto_encontrado)

    codigo_anterior = _to_str(st.session_state.get("entrada_codigo_produto_anterior", ""))
    produto_mudou = codigo_produto_final != codigo_anterior

    if codigo_produto_final and produto_encontrado is not None:
        st.success(
            f"Produto encontrado: {codigo_produto_final} - {_to_str(produto_encontrado.get('descricao', ''))}"
        )

        if produto_mudou:
            emb_padrao = _to_str(produto_encontrado.get("emb", "")).upper()
            unidade_padrao = _to_str(produto_encontrado.get("unidade", "")).upper()

            if emb_padrao and emb_padrao in opcoes_embalagens:
                st.session_state["entrada_embalagem_widget"] = emb_padrao
            else:
                st.session_state["entrada_embalagem_widget"] = "GR"

            if unidade_padrao and unidade_padrao in opcoes_unidades:
                st.session_state["entrada_unidade_widget"] = unidade_padrao
            else:
                st.session_state["entrada_unidade_widget"] = "Selecione..."

            st.session_state["entrada_codigo_produto_anterior"] = codigo_produto_final

    elif codigo_produto_final and produto_encontrado is None:
        st.error("Código do produto não cadastrado. Corrija o código para continuar.")
        st.session_state["entrada_embalagem_widget"] = "Selecione..."
        st.session_state["entrada_unidade_widget"] = "Selecione..."
        st.session_state["entrada_codigo_produto_anterior"] = ""

    else:
        st.session_state["entrada_embalagem_widget"] = "Selecione..."
        st.session_state["entrada_unidade_widget"] = "Selecione..."
        st.session_state["entrada_codigo_produto_anterior"] = ""

    if st.session_state.get("entrada_embalagem_widget") not in opcoes_embalagens:
        st.session_state["entrada_embalagem_widget"] = "Selecione..."

    if st.session_state.get("entrada_unidade_widget") not in opcoes_unidades:
        st.session_state["entrada_unidade_widget"] = "Selecione..."

    st.selectbox(
        "Localização",
        opcoes_localizacoes,
        key="entrada_localizacao_widget"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Quantidade",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="entrada_quantidade_widget"
        )

        st.text_input(
            "Lote",
            placeholder="Digite ou escaneie o lote",
            key="entrada_lote_widget",
            on_change=_normalizar_lote_entrada
        )

    with col2:
        st.selectbox(
            "Embalagem",
            opcoes_embalagens,
            key="entrada_embalagem_widget"
        )

        st.selectbox(
            "Unidade",
            opcoes_unidades,
            key="entrada_unidade_widget"
        )

        st.selectbox(
            "Status",
            opcoes_status,
            key="entrada_status_widget"
        )

    st.text_area(
        "Observação",
        key="entrada_observacao_widget"
    )

    if produto_encontrado is not None:
        quantidade_preview = float(st.session_state.get("entrada_quantidade_widget", 0.0))
        embalagem_preview = st.session_state.get("entrada_embalagem_widget", "Selecione...")

        if quantidade_preview > 0 and embalagem_preview != "Selecione...":
            peso_liquido_item = _to_float(produto_encontrado.get("peso_liquido", 0))
            densidade_item = _to_float(produto_encontrado.get("densidade", 0))
            unidade_item = _to_str(produto_encontrado.get("unidade", "")).upper()

            calculo_preview = calcular_quantidades_wms(
                embalagem_lancada=embalagem_preview,
                unidade_item=unidade_item,
                quantidade_digitada=quantidade_preview,
                peso_liquido_item=peso_liquido_item,
                densidade_item=densidade_item,
            )

            st.info(
                f"Prévia do cálculo | Embalagens: {calculo_preview['quantidade_embalagem']:.3f} | "
                f"Peso calculado: {calculo_preview['peso_calculado']:.3f} KG | "
                f"Quantidade convertida: {calculo_preview['quantidade_convertida']:.3f} {calculo_preview['unidade_convertida']}"
            )

    if st.button("Salvar Entrada"):
        codigo_produto_final = _normalizar_codigo_texto(
            st.session_state.get("entrada_codigo_produto_widget", "")
        )

        localizacao_escolhida = st.session_state.get("entrada_localizacao_widget", "Selecione...")
        quantidade_digitada = float(st.session_state.get("entrada_quantidade_widget", 0.0))
        lote = _normalizar_lote_texto(st.session_state.get("entrada_lote_widget", ""))
        embalagem_escolhida = st.session_state.get("entrada_embalagem_widget", "Selecione...")
        unidade_escolhida = st.session_state.get("entrada_unidade_widget", "Selecione...")
        status = st.session_state.get("entrada_status_widget", "Selecione...")
        observacao = _to_str(st.session_state.get("entrada_observacao_widget", ""))

        if not codigo_produto_final:
            st.session_state["msg_erro_entrada"] = "Informe o código do produto."
            st.rerun()

        produto_encontrado = _pegar_produto_encontrado(codigo_produto_final)

        if produto_encontrado is None:
            st.session_state["msg_erro_entrada"] = "Código do produto não cadastrado. Corrija o código para continuar."
            st.rerun()

        if localizacao_escolhida == "Selecione...":
            st.session_state["msg_erro_entrada"] = "Selecione uma localização."
            st.rerun()

        if embalagem_escolhida == "Selecione...":
            st.session_state["msg_erro_entrada"] = "Selecione uma embalagem."
            st.rerun()

        if unidade_escolhida == "Selecione...":
            st.session_state["msg_erro_entrada"] = "Selecione uma unidade."
            st.rerun()

        if status == "Selecione...":
            st.session_state["msg_erro_entrada"] = "Selecione um status."
            st.rerun()

        if quantidade_digitada <= 0:
            st.session_state["msg_erro_entrada"] = "Informe uma quantidade maior que zero."
            st.rerun()

        peso_liquido_item = _to_float(produto_encontrado.get("peso_liquido", 0))
        densidade_item = _to_float(produto_encontrado.get("densidade", 0))
        unidade_item = _to_str(produto_encontrado.get("unidade", "")).upper()

        calculo = calcular_quantidades_wms(
            embalagem_lancada=embalagem_escolhida,
            unidade_item=unidade_item,
            quantidade_digitada=quantidade_digitada,
            peso_liquido_item=peso_liquido_item,
            densidade_item=densidade_item,
        )

        localizacao_codigo_real = localizacoes[localizacao_escolhida]

        grupo_logico_id = novo_grupo_logico_id(
            produto_codigo=codigo_produto_final,
            localizacao_codigo=localizacao_codigo_real,
            lote=lote,
            doc_log="ENTRADA"
        )

        usuario = usuario_logado()

        try:
            conversa_banco.insert("movimentacoes", {
                "data_movimento": datetime.now().isoformat(),
                "data_hora": datetime.now().isoformat(),
                "tipo": "ENTRADA",
                "produto_codigo": codigo_produto_final,
                "localizacao_codigo": localizacao_codigo_real,
                "localizacao_origem_codigo": "",
                "localizacao_destino_codigo": "",
                "quantidade": float(calculo["peso_calculado"]),
                "quantidade_embalagem": float(calculo["quantidade_embalagem"]),
                "peso_calculado": float(calculo["peso_calculado"]),
                "lote": lote,
                "embalagem": embalagem_escolhida,
                "unidade": unidade_escolhida,
                "status": status,
                "status_origem": "",
                "status_destino": "",
                "lote_origem": "",
                "lote_destino": "",
                "observacao": observacao,
                "usuario": usuario["nome"] if usuario else "N/A",
                "grupo_logico_id": grupo_logico_id,
                "grupo_logico_origem_id": "",
                "juntar_destino": False,
                "doc_log": "ENTRADA",
            })

            st.session_state["msg_sucesso_entrada"] = (
                f"Entrada registrada com sucesso. "
                f"Embalagens: {calculo['quantidade_embalagem']:.3f} | "
                f"Peso calculado: {calculo['peso_calculado']:.3f} KG | "
                f"Quantidade convertida: {calculo['quantidade_convertida']:.3f} {calculo['unidade_convertida']}"
            )

            st.session_state["resetar_entrada"] = True
            st.rerun()

        except Exception as e:
            st.session_state["msg_erro_entrada"] = f"Erro ao salvar entrada: {e}"
            st.rerun()