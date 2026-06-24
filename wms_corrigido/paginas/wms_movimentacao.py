# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.contexto_empresa import filtrar_df_empresas, empresa_operacional_obrigatoria
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
    txt = _to_str(valor).upper().replace(";", "/").replace("\\", "/")

    while "//" in txt:
        txt = txt.replace("//", "/")

    return txt.strip()


def _normalizar_lote_texto(valor: str) -> str:
    txt = _to_str(valor).upper().replace(";", "/").replace("\\", "/")

    while "//" in txt:
        txt = txt.replace("//", "/")

    return txt.strip()


def _normalizar_codigo_movimentacao():
    chave = "mov_codigo_produto_widget"

    if chave in st.session_state:
        valor_atual = st.session_state[chave]
        valor_corrigido = _normalizar_codigo_texto(valor_atual)

        if valor_corrigido != valor_atual:
            st.session_state[chave] = valor_corrigido


def _normalizar_lote_movimentacao():
    chave = "mov_lote_destino_widget"

    if chave in st.session_state:
        valor_atual = st.session_state[chave]
        valor_corrigido = _normalizar_lote_texto(valor_atual)

        if valor_corrigido != valor_atual:
            st.session_state[chave] = valor_corrigido


def _mostrar_lote(valor: str) -> str:
    valor = _normalizar_lote_texto(valor)
    return valor if valor else "[SEM LOTE]"


def _buscar_produto_por_codigo(df_prod: pd.DataFrame, codigo_digitado: str):
    codigo = _normalizar_codigo_texto(codigo_digitado)

    if not codigo:
        return None

    df_filtrado = df_prod[df_prod["codigo"].astype(str).str.strip().str.upper() == codigo]

    if df_filtrado.empty:
        return None

    return df_filtrado.iloc[0]


def _montar_destinos(df_local: pd.DataFrame):
    return {
        f"{str(row.get('setor', '')).upper()} | {str(row.get('codigo', '')).upper()} | {str(row.get('local', '')).upper()}":
        f"{str(row.get('setor', '')).upper()}-{str(row.get('codigo', '')).upper()}-{str(row.get('local', '')).upper()}"
        for _, row in df_local.iterrows()
    }


def _inicializar_estado():
    padroes = {
        "mov_codigo_produto_widget": "",
        "mov_tipo_lancamento_widget": "FECHADOS",
        "mov_origem_widget": "Selecione...",
        "mov_destino_widget": "Selecione...",
        "mov_quantidade_widget": 0.0,
        "mov_lote_destino_widget": "",
        "mov_status_destino_widget": "Selecione...",
        "mov_modo_sobra_destino_widget": "MANTER / MOVER SOBRA",
        "mov_sobra_destino_juntar_widget": "Selecione...",
        "mov_observacao_widget": "",
        "mov_resetar_tela": False,
    }

    for chave, valor in padroes.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _resetar_tela_se_necessario():
    if not st.session_state.get("mov_resetar_tela", False):
        return

    st.session_state["mov_codigo_produto_widget"] = ""
    st.session_state["mov_tipo_lancamento_widget"] = "FECHADOS"
    st.session_state["mov_origem_widget"] = "Selecione..."
    st.session_state["mov_destino_widget"] = "Selecione..."
    st.session_state["mov_quantidade_widget"] = 0.0
    st.session_state["mov_lote_destino_widget"] = ""
    st.session_state["mov_status_destino_widget"] = "Selecione..."
    st.session_state["mov_modo_sobra_destino_widget"] = "MANTER / MOVER SOBRA"
    st.session_state["mov_sobra_destino_juntar_widget"] = "Selecione..."
    st.session_state["mov_observacao_widget"] = ""
    st.session_state["mov_resetar_tela"] = False


def _mostrar_mensagens():
    if "msg_sucesso_mov" in st.session_state:
        st.success(st.session_state["msg_sucesso_mov"])
        del st.session_state["msg_sucesso_mov"]

    if "msg_erro_mov" in st.session_state:
        st.error(st.session_state["msg_erro_mov"])
        del st.session_state["msg_erro_mov"]


def _buscar_localizacoes():
    df_local = conversa_banco.select("localizacoes", filtros={"ativo": True}, order_by="setor")

    df_local = filtrar_df_empresas(df_local)

    if df_local is None or df_local.empty:
        return pd.DataFrame()

    return df_local.copy()


def _buscar_movimentacoes():
    try:
        df = conversa_banco.select("movimentacoes", order_by="data_hora")
        df = filtrar_df_empresas(df)
    except Exception:
        df = conversa_banco.select("movimentacoes")
        df = filtrar_df_empresas(df)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    colunas_necessarias = [
        "id",
        "tipo",
        "produto_codigo",
        "localizacao_codigo",
        "localizacao_origem_codigo",
        "localizacao_destino_codigo",
        "quantidade",
        "quantidade_embalagem",
        "peso_calculado",
        "lote",
        "lote_origem",
        "lote_destino",
        "status",
        "status_origem",
        "status_destino",
        "embalagem",
        "grupo_logico_id",
        "grupo_logico_origem_id",
        "item_gr_origem_id",
    ]

    for coluna in colunas_necessarias:
        if coluna not in df.columns:
            df[coluna] = ""

    for coluna in [
        "tipo",
        "produto_codigo",
        "localizacao_codigo",
        "localizacao_origem_codigo",
        "localizacao_destino_codigo",
        "lote",
        "lote_origem",
        "lote_destino",
        "status",
        "status_origem",
        "status_destino",
        "embalagem",
        "grupo_logico_id",
        "grupo_logico_origem_id",
    ]:
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna in ["id", "quantidade", "quantidade_embalagem", "peso_calculado", "item_gr_origem_id"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    return df


def _montar_saldo_fechados(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()
    df = df[df["embalagem"].astype(str).str.upper() != "GR"].copy()

    movimentos = []

    for _, row in df.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        produto_codigo = _to_str(row.get("produto_codigo", "")).upper()
        quantidade_emb = _to_float(row.get("quantidade_embalagem", 0))

        if tipo == "ENTRADA":
            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote", "")),
                "status": _to_str(row.get("status", "")).upper(),
                "saldo_fechados": quantidade_emb,
            })

        elif tipo == "SAIDA":
            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote", "")),
                "status": _to_str(row.get("status", "")).upper(),
                "saldo_fechados": -quantidade_emb,
            })

        elif tipo == "MOVIMENTACAO":
            lote_destino = _normalizar_lote_texto(row.get("lote_destino", "")) or _normalizar_lote_texto(row.get("lote", ""))
            status_destino = _to_str(row.get("status_destino", "")).upper() or _to_str(row.get("status", "")).upper()

            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_origem_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote_origem", "")),
                "status": _to_str(row.get("status_origem", "")).upper(),
                "saldo_fechados": -quantidade_emb,
            })

            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_destino_codigo", "")).upper(),
                "lote": lote_destino,
                "status": status_destino,
                "saldo_fechados": quantidade_emb,
            })

    if not movimentos:
        return pd.DataFrame()

    saldo = pd.DataFrame(movimentos)

    saldo = (
        saldo.groupby(
            ["produto_codigo", "localizacao_codigo", "lote", "status"],
            as_index=False,
            dropna=False
        )[["saldo_fechados"]]
        .sum()
    )

    saldo = saldo[saldo["saldo_fechados"] > 0].copy()

    return saldo.reset_index(drop=True)


def _montar_saldo_sobras_individual(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()
    df = df[df["embalagem"].astype(str).str.upper() == "GR"].copy()

    if df.empty:
        return pd.DataFrame()

    movimentos = []

    for _, row in df.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        produto_codigo = _to_str(row.get("produto_codigo", "")).upper()
        peso = _to_float(row.get("peso_calculado", 0))

        grupo = _to_str(row.get("grupo_logico_id", ""))
        origem_id = int(_to_float(row.get("id", 0)))

        if not grupo and origem_id > 0:
            grupo = f"LEGADO|{origem_id}"

        if tipo == "ENTRADA":
            movimentos.append({
                "grupo_logico_id": grupo,
                "item_gr_id": origem_id,
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote", "")),
                "status": _to_str(row.get("status", "")).upper(),
                "saldo_sobra": peso,
            })

        elif tipo == "SAIDA":
            grupo_origem = _to_str(row.get("grupo_logico_origem_id", ""))

            if not grupo_origem:
                item_gr_origem_id = int(_to_float(row.get("item_gr_origem_id", 0)))
                if item_gr_origem_id > 0:
                    grupo_origem = f"LEGADO|{item_gr_origem_id}"

            if grupo_origem:
                movimentos.append({
                    "grupo_logico_id": grupo_origem,
                    "item_gr_id": 0,
                    "produto_codigo": produto_codigo,
                    "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                    "lote": _normalizar_lote_texto(row.get("lote", "")),
                    "status": _to_str(row.get("status", "")).upper(),
                    "saldo_sobra": -peso,
                })

        elif tipo == "MOVIMENTACAO":
            grupo_origem = _to_str(row.get("grupo_logico_origem_id", "")) or grupo
            grupo_destino = _to_str(row.get("grupo_logico_id", "")) or grupo_origem

            lote_destino = _normalizar_lote_texto(row.get("lote_destino", "")) or _normalizar_lote_texto(row.get("lote", ""))
            status_destino = _to_str(row.get("status_destino", "")).upper() or _to_str(row.get("status", "")).upper()

            movimentos.append({
                "grupo_logico_id": grupo_origem,
                "item_gr_id": 0,
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_origem_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote_origem", "")),
                "status": _to_str(row.get("status_origem", "")).upper(),
                "saldo_sobra": -peso,
            })

            movimentos.append({
                "grupo_logico_id": grupo_destino,
                "item_gr_id": origem_id,
                "produto_codigo": produto_codigo,
                "localizacao_codigo": _to_str(row.get("localizacao_destino_codigo", "")).upper(),
                "lote": lote_destino,
                "status": status_destino,
                "saldo_sobra": peso,
            })

    if not movimentos:
        return pd.DataFrame()

    saldo = pd.DataFrame(movimentos)

    saldo = (
        saldo.groupby(
            ["grupo_logico_id", "produto_codigo", "localizacao_codigo", "lote", "status"],
            as_index=False,
            dropna=False
        )[["saldo_sobra"]]
        .sum()
    )

    saldo = saldo[saldo["saldo_sobra"] > 0].copy()

    return saldo.reset_index(drop=True)


def _rotulo_fechados(row):
    return (
        f"{row['produto_codigo']} | Origem: {row['localizacao_codigo']} | "
        f"Lote: {_mostrar_lote(row.get('lote', ''))} | Status: {row.get('status', '')} | "
        f"Saldo Fechados: {float(row.get('saldo_fechados', 0)):.3f}"
    )


def _rotulo_sobra(row):
    return (
        f"ID Sobra: {row.get('grupo_logico_id', '')} | {row['produto_codigo']} | "
        f"Origem: {row['localizacao_codigo']} | "
        f"Lote: {_mostrar_lote(row.get('lote', ''))} | Status: {row.get('status', '')} | "
        f"Saldo Sobra: {float(row.get('saldo_sobra', 0)):.3f}"
    )


def app():
    st.title("🔁 Movimentação Interna")

    _inicializar_estado()
    _resetar_tela_se_necessario()
    _mostrar_mensagens()

    df_prod = filtrar_df_empresas(conversa_banco.select("produtos", filtros={"ativo": True}, order_by="codigo"))
    if df_prod is None or df_prod.empty:
        st.warning("Cadastre pelo menos 1 produto ativo.")
        return

    df_local = _buscar_localizacoes()
    if df_local.empty:
        st.warning("Cadastre localizações ativas.")
        return

    destinos = _montar_destinos(df_local)
    opcoes_destino = ["Selecione..."] + list(destinos.keys())
    opcoes_status = ["Selecione...", "DISPONIVEL", "BLOQUEADO", "AVARIA"]

    df_mov = _buscar_movimentacoes()
    if df_mov.empty:
        st.warning("Não existe saldo disponível para movimentação.")
        return

    saldo_fechados = _montar_saldo_fechados(df_mov)
    saldo_sobras = _montar_saldo_sobras_individual(df_mov)

    st.text_input(
        "Código do Produto",
        key="mov_codigo_produto_widget",
        on_change=_normalizar_codigo_movimentacao
    )

    codigo_produto_final = _normalizar_codigo_texto(st.session_state.get("mov_codigo_produto_widget", ""))
    produto_encontrado = _buscar_produto_por_codigo(df_prod, codigo_produto_final)

    if codigo_produto_final:
        if produto_encontrado is not None:
            st.success(f"Produto encontrado: {produto_encontrado['codigo']} - {produto_encontrado['descricao']}")
        else:
            st.error("Código do produto não cadastrado.")

    tipo_lancamento = st.radio(
        "Tipo de Movimentação",
        ["FECHADOS", "SOBRA / GR"],
        horizontal=True,
        key="mov_tipo_lancamento_widget"
    )

    tipo_normalizado = "FECHADOS" if tipo_lancamento == "FECHADOS" else "GR"

    if tipo_normalizado == "FECHADOS":
        df_origem = saldo_fechados.copy()
    else:
        df_origem = saldo_sobras.copy()

    if codigo_produto_final and produto_encontrado is not None:
        df_origem = df_origem[
            df_origem["produto_codigo"].astype(str).str.upper() == codigo_produto_final
        ].copy()
    else:
        df_origem = df_origem.iloc[0:0]

    if tipo_normalizado == "FECHADOS":
        if not df_origem.empty:
            df_origem["rotulo_origem"] = df_origem.apply(_rotulo_fechados, axis=1)
    else:
        if not df_origem.empty:
            df_origem["rotulo_origem"] = df_origem.apply(_rotulo_sobra, axis=1)

    opcoes_origem = ["Selecione..."]
    if not df_origem.empty:
        opcoes_origem += df_origem["rotulo_origem"].tolist()

    if st.session_state.get("mov_origem_widget") not in opcoes_origem:
        st.session_state["mov_origem_widget"] = "Selecione..."

    st.selectbox("Origem", opcoes_origem, key="mov_origem_widget")
    st.selectbox("Endereço de Destino", opcoes_destino, key="mov_destino_widget")

    col1, col2 = st.columns(2)

    with col1:
        rotulo_qtd = "Quantidade de embalagens fechadas" if tipo_normalizado == "FECHADOS" else "Quantidade da sobra / ajuste"

        st.number_input(
            rotulo_qtd,
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="mov_quantidade_widget"
        )

    with col2:
        st.text_input(
            "Novo Lote no Destino",
            key="mov_lote_destino_widget",
            on_change=_normalizar_lote_movimentacao
        )

        st.selectbox(
            "Novo Status no Destino",
            opcoes_status,
            key="mov_status_destino_widget"
        )

    if tipo_normalizado == "GR":
        st.selectbox(
            "O que fazer com a sobra no destino?",
            [
                "MANTER / MOVER SOBRA",
                "SEPARAR EM NOVA SOBRA",
                "JUNTAR COM OUTRA SOBRA NO DESTINO",
            ],
            key="mov_modo_sobra_destino_widget"
        )

        destino_escolhido_pre = st.session_state.get("mov_destino_widget", "Selecione...")

        if destino_escolhido_pre != "Selecione...":
            destino_codigo_pre = destinos[destino_escolhido_pre]

            df_sobras_destino = saldo_sobras.copy()

            if codigo_produto_final:
                df_sobras_destino = df_sobras_destino[
                    df_sobras_destino["produto_codigo"].astype(str).str.upper() == codigo_produto_final
                ]

            df_sobras_destino = df_sobras_destino[
                df_sobras_destino["localizacao_codigo"].astype(str).str.upper() == destino_codigo_pre.upper()
            ].copy()

            if not df_sobras_destino.empty:
                df_sobras_destino["rotulo_juntar"] = df_sobras_destino.apply(_rotulo_sobra, axis=1)
                opcoes_juntar = ["Selecione..."] + df_sobras_destino["rotulo_juntar"].tolist()
            else:
                opcoes_juntar = ["Selecione..."]

            if st.session_state.get("mov_sobra_destino_juntar_widget") not in opcoes_juntar:
                st.session_state["mov_sobra_destino_juntar_widget"] = "Selecione..."

            if st.session_state.get("mov_modo_sobra_destino_widget") == "JUNTAR COM OUTRA SOBRA NO DESTINO":
                st.selectbox(
                    "Escolha a sobra do destino para juntar",
                    opcoes_juntar,
                    key="mov_sobra_destino_juntar_widget"
                )

    st.text_area("Observação", key="mov_observacao_widget")

    if st.button("Salvar Movimentação"):
        origem_escolhida = st.session_state.get("mov_origem_widget", "Selecione...")
        destino_escolhido = st.session_state.get("mov_destino_widget", "Selecione...")
        quantidade_digitada = float(st.session_state.get("mov_quantidade_widget", 0.0))
        lote_destino = _normalizar_lote_texto(st.session_state.get("mov_lote_destino_widget", ""))
        status_destino = _to_str(st.session_state.get("mov_status_destino_widget", "Selecione...")).upper()
        observacao = _to_str(st.session_state.get("mov_observacao_widget", ""))

        if produto_encontrado is None:
            st.session_state["msg_erro_mov"] = "Produto inválido."
            st.rerun()

        if origem_escolhida == "Selecione...":
            st.session_state["msg_erro_mov"] = "Selecione a origem."
            st.rerun()

        if destino_escolhido == "Selecione...":
            st.session_state["msg_erro_mov"] = "Selecione o destino."
            st.rerun()

        if status_destino == "SELECIONE...":
            st.session_state["msg_erro_mov"] = "Selecione o status no destino."
            st.rerun()

        if quantidade_digitada <= 0:
            st.session_state["msg_erro_mov"] = "Informe uma quantidade maior que zero."
            st.rerun()

        linha = df_origem[df_origem["rotulo_origem"] == origem_escolhida].iloc[0]

        produto_codigo = _to_str(linha["produto_codigo"]).upper()
        origem = _to_str(linha["localizacao_codigo"]).upper()
        destino = destinos[destino_escolhido]
        lote_origem = _normalizar_lote_texto(linha.get("lote", ""))
        status_origem = _to_str(linha.get("status", "")).upper()

        if not lote_destino:
            lote_destino = lote_origem

        peso_liquido_item = _to_float(produto_encontrado.get("peso_liquido", 0))
        densidade_item = _to_float(produto_encontrado.get("densidade", 0))
        unidade_item = _to_str(produto_encontrado.get("unidade", "")).upper() or "UN"
        embalagem_fechada_item = _to_str(produto_encontrado.get("emb", "")).upper() or "GR"

        if tipo_normalizado == "FECHADOS":
            saldo_disponivel = float(linha.get("saldo_fechados", 0) or 0)

            if quantidade_digitada > saldo_disponivel:
                st.session_state["msg_erro_mov"] = f"Quantidade maior que o saldo disponível ({saldo_disponivel:.3f})."
                st.rerun()

            embalagem_mov = embalagem_fechada_item
            grupo_origem_id = ""
            grupo_destino_id = ""

        else:
            saldo_disponivel = float(linha.get("saldo_sobra", 0) or 0)

            if quantidade_digitada > saldo_disponivel:
                st.session_state["msg_erro_mov"] = f"Quantidade maior que a sobra disponível ({saldo_disponivel:.3f})."
                st.rerun()

            embalagem_mov = "GR"
            grupo_origem_id = _to_str(linha.get("grupo_logico_id", ""))

            modo_sobra = st.session_state.get("mov_modo_sobra_destino_widget", "MANTER / MOVER SOBRA")

            if modo_sobra == "MANTER / MOVER SOBRA":
                grupo_destino_id = grupo_origem_id

            elif modo_sobra == "SEPARAR EM NOVA SOBRA":
                grupo_destino_id = novo_grupo_logico_id(
                    produto_codigo=produto_codigo,
                    localizacao_codigo=destino,
                    lote=lote_destino,
                    doc_log="SEPARACAO_SOBRA"
                )

            else:
                rotulo_juntar = st.session_state.get("mov_sobra_destino_juntar_widget", "Selecione...")

                if rotulo_juntar == "Selecione...":
                    st.session_state["msg_erro_mov"] = "Selecione a sobra do destino para juntar."
                    st.rerun()

                df_sobras_destino = saldo_sobras.copy()
                df_sobras_destino["rotulo_juntar"] = df_sobras_destino.apply(_rotulo_sobra, axis=1)
                linha_juntar = df_sobras_destino[df_sobras_destino["rotulo_juntar"] == rotulo_juntar].iloc[0]
                grupo_destino_id = _to_str(linha_juntar.get("grupo_logico_id", ""))

        calculo = calcular_quantidades_wms(
            embalagem_lancada=embalagem_mov,
            unidade_item=unidade_item,
            quantidade_digitada=quantidade_digitada,
            peso_liquido_item=peso_liquido_item,
            densidade_item=densidade_item,
        )

        quantidade_embalagem = float(calculo["quantidade_embalagem"])

        if tipo_normalizado == "GR":
            quantidade_embalagem = 0.0

        usuario = usuario_logado()
        empresa_id = empresa_operacional_obrigatoria()
        custo_unitario = _to_float(produto.get("custo_unitario", 0)) if produto is not None else 0.0
        custo_total = float(calculo["peso_calculado"]) * custo_unitario

        try:
            conversa_banco.insert("movimentacoes", {
                "data_movimento": datetime.now().isoformat(),
                "data_hora": datetime.now().isoformat(),
                "tipo": "MOVIMENTACAO",
                "empresa_id": empresa_id,
                "produto_codigo": produto_codigo,
                "localizacao_codigo": "",
                "localizacao_origem_codigo": origem,
                "localizacao_destino_codigo": destino,
                "quantidade": float(calculo["peso_calculado"]),
                "quantidade_embalagem": quantidade_embalagem,
                "peso_calculado": float(calculo["peso_calculado"]),
                "custo_unitario": custo_unitario,
                "custo_total": custo_total,
                "lote": lote_destino,
                "lote_origem": lote_origem,
                "lote_destino": lote_destino,
                "embalagem": embalagem_mov,
                "unidade": unidade_item,
                "status": status_destino,
                "status_origem": status_origem,
                "status_destino": status_destino,
                "observacao": observacao,
                "usuario": usuario["nome"] if usuario else "N/A",
                "grupo_logico_id": grupo_destino_id,
                "grupo_logico_origem_id": grupo_origem_id,
                "juntar_destino": st.session_state.get("mov_modo_sobra_destino_widget") == "JUNTAR COM OUTRA SOBRA NO DESTINO",
                "doc_log": st.session_state.get("mov_modo_sobra_destino_widget", ""),
            })

            st.session_state["msg_sucesso_mov"] = "Movimentação registrada com sucesso."
            st.session_state["mov_resetar_tela"] = True
            st.rerun()

        except Exception as e:
            st.session_state["msg_erro_mov"] = f"Erro ao salvar movimentação: {e}"
            st.rerun()