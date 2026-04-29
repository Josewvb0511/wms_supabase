# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_logado
from funcoes_compartilhadas.wms_pesos import calcular_quantidades_wms


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


def _normalizar_codigo_saida():
    chave = "saida_codigo_produto_widget"
    if chave in st.session_state:
        valor_atual = st.session_state[chave]
        valor_corrigido = _normalizar_codigo_texto(valor_atual)
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


def _inicializar_estado():
    padroes = {
        "saida_codigo_produto_widget": "",
        "saida_tipo_lancamento_widget": "FECHADOS",
        "saida_origem_widget": "Selecione...",
        "saida_quantidade_widget": 0.0,
        "saida_observacao_widget": "",
        "saida_resetar_tela": False,
    }

    for chave, valor in padroes.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _resetar_tela_se_necessario():
    if not st.session_state.get("saida_resetar_tela", False):
        return

    st.session_state["saida_codigo_produto_widget"] = ""
    st.session_state["saida_tipo_lancamento_widget"] = "FECHADOS"
    st.session_state["saida_origem_widget"] = "Selecione..."
    st.session_state["saida_quantidade_widget"] = 0.0
    st.session_state["saida_observacao_widget"] = ""
    st.session_state["saida_resetar_tela"] = False


def _mostrar_mensagens():
    if "msg_sucesso_saida" in st.session_state:
        st.success(st.session_state["msg_sucesso_saida"])
        del st.session_state["msg_sucesso_saida"]

    if "msg_erro_saida" in st.session_state:
        st.error(st.session_state["msg_erro_saida"])
        del st.session_state["msg_erro_saida"]


def _buscar_movimentacoes():
    try:
        df = conversa_banco.select("movimentacoes", order_by="data_hora")
    except Exception:
        df = conversa_banco.select("movimentacoes")

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
        "item_gr_origem_id",
        "grupo_logico_id",
        "grupo_logico_origem_id",
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

    for coluna in ["quantidade", "quantidade_embalagem", "peso_calculado", "item_gr_origem_id"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    return df


def _montar_saldo_fechados(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()
    df = df[df["embalagem"].astype(str).str.upper() != "GR"].copy()

    if df.empty:
        return pd.DataFrame()

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
            origem = _to_str(row.get("localizacao_origem_codigo", "")).upper()
            destino = _to_str(row.get("localizacao_destino_codigo", "")).upper()

            lote_origem = _normalizar_lote_texto(row.get("lote_origem", ""))
            lote_destino = _normalizar_lote_texto(row.get("lote_destino", ""))
            if not lote_destino:
                lote_destino = _normalizar_lote_texto(row.get("lote", ""))

            status_origem = _to_str(row.get("status_origem", "")).upper()
            status_destino = _to_str(row.get("status_destino", "")).upper()
            if not status_destino:
                status_destino = _to_str(row.get("status", "")).upper()

            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": origem,
                "lote": lote_origem,
                "status": status_origem,
                "saldo_fechados": -quantidade_emb,
            })

            movimentos.append({
                "produto_codigo": produto_codigo,
                "localizacao_codigo": destino,
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
    saldo["tipo_estoque"] = "FECHADOS"

    return saldo.reset_index(drop=True)


def _montar_saldo_sobras_individual(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()
    df = df[df["embalagem"].astype(str).str.upper() == "GR"].copy()

    if df.empty:
        return pd.DataFrame()

    fontes = []

    for _, row in df.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        origem_id = int(_to_float(row.get("id", 0)))
        grupo_logico_id = _to_str(row.get("grupo_logico_id", ""))

        if tipo == "ENTRADA":
            fontes.append({
                "item_gr_id": origem_id,
                "grupo_logico_id": grupo_logico_id if grupo_logico_id else f"LEGADO|{origem_id}",
                "produto_codigo": _to_str(row.get("produto_codigo", "")).upper(),
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _normalizar_lote_texto(row.get("lote", "")),
                "status": _to_str(row.get("status", "")).upper(),
                "saldo_inicial_sobra": _to_float(row.get("peso_calculado", 0)),
            })

        elif tipo == "MOVIMENTACAO":
            local_destino = _to_str(row.get("localizacao_destino_codigo", "")).upper()
            lote_destino = _normalizar_lote_texto(row.get("lote_destino", ""))
            if not lote_destino:
                lote_destino = _normalizar_lote_texto(row.get("lote", ""))

            status_destino = _to_str(row.get("status_destino", "")).upper()
            if not status_destino:
                status_destino = _to_str(row.get("status", "")).upper()

            if local_destino:
                fontes.append({
                    "item_gr_id": origem_id,
                    "grupo_logico_id": grupo_logico_id if grupo_logico_id else f"LEGADO|{origem_id}",
                    "produto_codigo": _to_str(row.get("produto_codigo", "")).upper(),
                    "localizacao_codigo": local_destino,
                    "lote": lote_destino,
                    "status": status_destino,
                    "saldo_inicial_sobra": _to_float(row.get("peso_calculado", 0)),
                })

    if not fontes:
        return pd.DataFrame()

    df_fontes = pd.DataFrame(fontes)

    consumos = []

    for _, row in df.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        if tipo not in ["SAIDA", "MOVIMENTACAO"]:
            continue

        grupo_origem = _to_str(row.get("grupo_logico_origem_id", ""))
        if not grupo_origem:
            item_gr_origem_id = int(_to_float(row.get("item_gr_origem_id", 0)))
            if item_gr_origem_id > 0:
                grupo_origem = f"LEGADO|{item_gr_origem_id}"

        if not grupo_origem:
            continue

        consumos.append({
            "grupo_logico_id": grupo_origem,
            "consumo_sobra": _to_float(row.get("peso_calculado", 0)),
        })

    if consumos:
        df_consumos = pd.DataFrame(consumos)
        df_consumos = df_consumos.groupby("grupo_logico_id", as_index=False)[["consumo_sobra"]].sum()
        df_fontes = df_fontes.merge(df_consumos, how="left", on="grupo_logico_id")
    else:
        df_fontes["consumo_sobra"] = 0.0

    df_fontes["consumo_sobra"] = pd.to_numeric(df_fontes["consumo_sobra"], errors="coerce").fillna(0.0)
    df_fontes["saldo_sobra"] = df_fontes["saldo_inicial_sobra"] - df_fontes["consumo_sobra"]

    df_fontes = df_fontes[df_fontes["saldo_sobra"] > 0].copy()
    df_fontes["tipo_estoque"] = "GR"

    return df_fontes.reset_index(drop=True)


def _montar_rotulo_saida_fechados(row):
    produto_codigo = _to_str(row.get("produto_codigo", "")).upper()
    localizacao_codigo = _to_str(row.get("localizacao_codigo", "")).upper()
    lote = _mostrar_lote(row.get("lote", ""))
    status = _to_str(row.get("status", "")).upper()
    saldo_fechados = float(row.get("saldo_fechados", 0) or 0)

    return (
        f"{produto_codigo} | {localizacao_codigo} | "
        f"Lote: {lote} | Status: {status} | "
        f"Saldo Fechados: {saldo_fechados:.3f}"
    )


def _montar_rotulo_saida_sobra(row):
    item_gr_id = int(_to_float(row.get("item_gr_id", 0)))
    produto_codigo = _to_str(row.get("produto_codigo", "")).upper()
    localizacao_codigo = _to_str(row.get("localizacao_codigo", "")).upper()
    lote = _mostrar_lote(row.get("lote", ""))
    status = _to_str(row.get("status", "")).upper()
    saldo_sobra = float(row.get("saldo_sobra", 0) or 0)

    return (
        f"ID Sobra {item_gr_id} | {produto_codigo} | {localizacao_codigo} | "
        f"Lote: {lote} | Status: {status} | "
        f"Saldo Sobra: {saldo_sobra:.3f}"
    )


def _quantidade_embalagem_para_gravar_saida(
    tipo_lancamento_normalizado: str,
    quantidade_embalagem_calculada: float,
    quantidade_digitada: float,
    saldo_sobra_disponivel: float,
    tolerancia: float = 0.000001,
) -> float:
    if tipo_lancamento_normalizado == "FECHADOS":
        return float(quantidade_embalagem_calculada)

    restante = float(saldo_sobra_disponivel) - float(quantidade_digitada)

    if restante <= tolerancia:
        return 1.0

    return 0.0


def app():
    st.title("📤 Saída de Produtos")

    _inicializar_estado()
    _resetar_tela_se_necessario()
    _mostrar_mensagens()

    df_prod = conversa_banco.select("produtos", filtros={"ativo": True}, order_by="codigo")
    if df_prod is None or df_prod.empty:
        st.warning("Cadastre pelo menos 1 produto ativo em Cadastros.")
        return

    df_mov = _buscar_movimentacoes()
    if df_mov.empty:
        st.warning("Não existe saldo disponível para saída.")
        return

    saldo_fechados = _montar_saldo_fechados(df_mov)
    saldo_sobras = _montar_saldo_sobras_individual(df_mov)

    st.text_input(
        "Código do Produto",
        placeholder="Ex: PROD-A",
        key="saida_codigo_produto_widget",
        on_change=_normalizar_codigo_saida
    )

    codigo_produto_final = _normalizar_codigo_texto(
        st.session_state.get("saida_codigo_produto_widget", "")
    )

    produto_encontrado = _buscar_produto_por_codigo(df_prod, codigo_produto_final)

    if codigo_produto_final:
        if produto_encontrado is not None:
            st.success(
                f"Produto encontrado: {produto_encontrado['codigo']} - {produto_encontrado['descricao']}"
            )
        else:
            st.error("Código do produto não cadastrado. Corrija o código para continuar.")

    tipo_lancamento = st.radio(
        "Tipo de Ajuste / Saída",
        options=["FECHADOS", "SOBRA / GR"],
        horizontal=True,
        key="saida_tipo_lancamento_widget"
    )

    tipo_lancamento_normalizado = "FECHADOS" if tipo_lancamento == "FECHADOS" else "GR"

    if tipo_lancamento_normalizado == "FECHADOS":
        df_opcoes = saldo_fechados.copy()
    else:
        df_opcoes = saldo_sobras.copy()

    if codigo_produto_final and produto_encontrado is not None:
        df_opcoes = df_opcoes[
            df_opcoes["produto_codigo"].astype(str).str.strip().str.upper() == codigo_produto_final
        ].copy()
    else:
        df_opcoes = df_opcoes.iloc[0:0]

    if tipo_lancamento_normalizado == "FECHADOS":
        if not df_opcoes.empty:
            df_opcoes["rotulo_saida"] = df_opcoes.apply(_montar_rotulo_saida_fechados, axis=1)
    else:
        if not df_opcoes.empty:
            df_opcoes["rotulo_saida"] = df_opcoes.apply(_montar_rotulo_saida_sobra, axis=1)

    opcoes_origem = ["Selecione..."]
    if not df_opcoes.empty:
        opcoes_origem += df_opcoes["rotulo_saida"].tolist()

    if st.session_state.get("saida_origem_widget") not in opcoes_origem:
        st.session_state["saida_origem_widget"] = "Selecione..."

    st.selectbox(
        "Origem para Saída",
        opcoes_origem,
        key="saida_origem_widget"
    )

    rotulo_quantidade = (
        "Quantidade de embalagens fechadas"
        if tipo_lancamento_normalizado == "FECHADOS"
        else "Quantidade da sobra / ajuste"
    )

    st.number_input(
        rotulo_quantidade,
        min_value=0.0,
        step=1.0,
        format="%.2f",
        key="saida_quantidade_widget"
    )

    st.text_area(
        "Observação",
        key="saida_observacao_widget"
    )

    if produto_encontrado is not None and st.session_state.get("saida_origem_widget") != "Selecione...":
        linha_preview = df_opcoes[df_opcoes["rotulo_saida"] == st.session_state["saida_origem_widget"]]
        if not linha_preview.empty:
            linha_preview = linha_preview.iloc[0]

            if tipo_lancamento_normalizado == "FECHADOS":
                saldo_disp = float(linha_preview.get("saldo_fechados", 0) or 0)
                st.info(
                    f"Saldo disponível para fechados: {saldo_disp:.3f} embalagem(ns). "
                    f"As sobras ficaram fora dessa lista."
                )
            else:
                saldo_disp = float(linha_preview.get("saldo_sobra", 0) or 0)
                item_gr_id = int(_to_float(linha_preview.get("item_gr_id", 0)))
                st.info(
                    f"Sobra selecionada: ID {item_gr_id} | "
                    f"Saldo disponível: {saldo_disp:.3f}. "
                    f"Baixa parcial não derruba embalagem. "
                    f"A última baixa que zerar a sobra derruba 1 embalagem."
                )

    if st.button("Salvar Saída"):
        origem_escolhida = st.session_state.get("saida_origem_widget", "Selecione...")
        quantidade_digitada = float(st.session_state.get("saida_quantidade_widget", 0.0))
        observacao = _to_str(st.session_state.get("saida_observacao_widget", ""))

        if not codigo_produto_final:
            st.session_state["msg_erro_saida"] = "Informe o código do produto."
            st.rerun()

        if produto_encontrado is None:
            st.session_state["msg_erro_saida"] = "Código do produto não cadastrado. Corrija o código para continuar."
            st.rerun()

        if origem_escolhida == "Selecione...":
            st.session_state["msg_erro_saida"] = "Selecione a origem para saída."
            st.rerun()

        if quantidade_digitada <= 0:
            st.session_state["msg_erro_saida"] = "Informe uma quantidade maior que zero."
            st.rerun()

        linha = df_opcoes[df_opcoes["rotulo_saida"] == origem_escolhida].iloc[0]

        produto_codigo = _to_str(linha["produto_codigo"]).upper()
        localizacao_codigo = _to_str(linha["localizacao_codigo"]).upper()
        lote = _normalizar_lote_texto(linha.get("lote", ""))
        status = _to_str(linha.get("status", "")).upper()

        peso_liquido_item = _to_float(produto_encontrado.get("peso_liquido", 0))
        densidade_item = _to_float(produto_encontrado.get("densidade", 0))
        unidade_item = _to_str(produto_encontrado.get("unidade", "")).upper() or "UN"
        embalagem_fechada_item = _to_str(produto_encontrado.get("emb", "")).upper() or "GR"

        saldo_sobra_disponivel = 0.0
        grupo_logico_origem_id = ""

        if tipo_lancamento_normalizado == "FECHADOS":
            saldo_disponivel = float(linha.get("saldo_fechados", 0) or 0)
            if quantidade_digitada > saldo_disponivel:
                st.session_state["msg_erro_saida"] = (
                    f"Quantidade maior que o saldo de fechados disponível ({saldo_disponivel:.3f})."
                )
                st.rerun()

            embalagem_item_para_saida = embalagem_fechada_item
            item_gr_origem_id = None

        else:
            saldo_sobra_disponivel = float(linha.get("saldo_sobra", 0) or 0)
            if quantidade_digitada > saldo_sobra_disponivel:
                st.session_state["msg_erro_saida"] = (
                    f"Quantidade maior que o saldo de sobra disponível ({saldo_sobra_disponivel:.3f})."
                )
                st.rerun()

            embalagem_item_para_saida = "GR"
            item_gr_origem_id = int(_to_float(linha.get("item_gr_id", 0)))
            grupo_logico_origem_id = _to_str(linha.get("grupo_logico_id", ""))

        calculo = calcular_quantidades_wms(
            embalagem_lancada=embalagem_item_para_saida,
            unidade_item=unidade_item,
            quantidade_digitada=quantidade_digitada,
            peso_liquido_item=peso_liquido_item,
            densidade_item=densidade_item,
        )

        quantidade_embalagem_gravada = _quantidade_embalagem_para_gravar_saida(
            tipo_lancamento_normalizado=tipo_lancamento_normalizado,
            quantidade_embalagem_calculada=float(calculo["quantidade_embalagem"]),
            quantidade_digitada=float(quantidade_digitada),
            saldo_sobra_disponivel=float(saldo_sobra_disponivel),
        )

        usuario = usuario_logado()

        try:
            payload = {
                "data_movimento": datetime.now().isoformat(),
                "data_hora": datetime.now().isoformat(),
                "tipo": "SAIDA",
                "produto_codigo": produto_codigo,
                "localizacao_codigo": localizacao_codigo,
                "localizacao_origem_codigo": "",
                "localizacao_destino_codigo": "",
                "quantidade": float(calculo["peso_calculado"]),
                "quantidade_embalagem": float(quantidade_embalagem_gravada),
                "peso_calculado": float(calculo["peso_calculado"]),
                "lote": lote,
                "embalagem": embalagem_item_para_saida,
                "unidade": unidade_item,
                "status": status,
                "status_origem": "",
                "status_destino": "",
                "lote_origem": "",
                "lote_destino": "",
                "observacao": observacao,
                "usuario": usuario["nome"] if usuario else "N/A",
                "grupo_logico_id": "",
                "grupo_logico_origem_id": grupo_logico_origem_id,
            }

            if item_gr_origem_id is not None:
                payload["item_gr_origem_id"] = item_gr_origem_id

            conversa_banco.insert("movimentacoes", payload)

            st.session_state["msg_sucesso_saida"] = (
                f"Saída registrada com sucesso. "
                f"Tipo: {'Fechados' if tipo_lancamento_normalizado == 'FECHADOS' else 'Sobra / GR'} | "
                f"Embalagens gravadas: {quantidade_embalagem_gravada:.3f} | "
                f"Peso calculado: {calculo['peso_calculado']:.3f}"
            )

            st.session_state["saida_resetar_tela"] = True
            st.rerun()

        except Exception as e:
            st.session_state["msg_erro_saida"] = f"Erro ao salvar saída: {e}"
            st.rerun()