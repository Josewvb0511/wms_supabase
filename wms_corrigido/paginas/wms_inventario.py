# -*- coding: utf-8 -*-
from datetime import datetime
import io

import pandas as pd
import requests
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.contexto_empresa import filtrar_df_empresas, empresa_operacional_obrigatoria
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


def _normalizar_texto(valor):
    txt = _to_str(valor).upper()
    txt = txt.replace(";", "/").replace("\\", "/")

    while "//" in txt:
        txt = txt.replace("//", "/")

    return txt.strip()


def _normalizar_codigo():
    chave = "inv_codigo_widget"

    if chave in st.session_state:
        st.session_state[chave] = _normalizar_texto(st.session_state[chave])


def _normalizar_lote():
    chave = "inv_lote_widget"

    if chave in st.session_state:
        st.session_state[chave] = _normalizar_texto(st.session_state[chave])


def _df_para_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
    return buffer.getvalue().encode("utf-8-sig")


def _buscar_produto(codigo):
    codigo = _normalizar_texto(codigo)

    if not codigo:
        return None

    df_prod = conversa_banco.select(
        "produtos",
        filtros={"codigo": codigo, "ativo": True},
        order_by="id"
    )

    df_prod = filtrar_df_empresas(df_prod)

    if df_prod is None or df_prod.empty:
        return None

    return df_prod.iloc[0]


def _buscar_localizacoes():
    df = conversa_banco.select(
        "localizacoes",
        filtros={"ativo": True},
        order_by="setor"
    )

    df = filtrar_df_empresas(df)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    for coluna in ["setor", "codigo", "local"]:
        if coluna not in df.columns:
            df[coluna] = ""

        df[coluna] = df[coluna].fillna("").astype(str).str.strip().str.upper()

    return df


def _montar_localizacoes(df_local):
    localizacoes = {}

    for _, row in df_local.iterrows():
        setor = _to_str(row.get("setor", "")).upper()
        codigo = _to_str(row.get("codigo", "")).upper()
        local = _to_str(row.get("local", "")).upper()

        texto_tela = f"{setor} | {codigo} | {local}"
        codigo_banco = f"{setor}-{codigo}-{local}"

        localizacoes[texto_tela] = codigo_banco

    return localizacoes


def _inicializar_estado():
    padroes = {
        "inv_contagem_widget": "CONTAGEM 1",
        "inv_codigo_widget": "",
        "inv_localizacao_widget": "Selecione...",
        "inv_quantidade_widget": 0.0,
        "inv_lote_widget": "",
        "inv_embalagem_widget": "Selecione...",
        "inv_status_widget": "DISPONIVEL",
        "inv_observacao_widget": "",
        "inv_confirmar_limpar": False,
        "inv_resetar": False,
        "inv_somente_unicos": False,
    }

    for chave, valor in padroes.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _resetar_se_precisar():
    if not st.session_state.get("inv_resetar", False):
        return

    st.session_state["inv_codigo_widget"] = ""
    st.session_state["inv_quantidade_widget"] = 0.0
    st.session_state["inv_lote_widget"] = ""
    st.session_state["inv_embalagem_widget"] = "Selecione..."
    st.session_state["inv_observacao_widget"] = ""
    st.session_state["inv_resetar"] = False


def _mostrar_mensagens():
    if "msg_sucesso_inv" in st.session_state:
        st.success(st.session_state["msg_sucesso_inv"])
        del st.session_state["msg_sucesso_inv"]

    if "msg_erro_inv" in st.session_state:
        st.error(st.session_state["msg_erro_inv"])
        del st.session_state["msg_erro_inv"]


def _carregar_inventario():
    try:
        df = conversa_banco.select("inventario", order_by="data_hora")
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    colunas_padrao = {
        "contagem": "CONTAGEM 1",
        "peso_convertido": 0.0,
        "unidade_normal": "",
        "unidade_convertida": "",
    }

    for coluna, padrao in colunas_padrao.items():
        if coluna not in df.columns:
            df[coluna] = padrao

    return df


def _limpar_inventario():
    supabase_url = st.secrets["SUPABASE_URL"].rstrip("/")
    supabase_key = st.secrets["SUPABASE_KEY"]

    url = f"{supabase_url}/rest/v1/rpc/limpar_inventario"

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    resposta = requests.post(url, headers=headers, json={}, timeout=30)

    if resposta.status_code not in [200, 204]:
        raise Exception(resposta.text)


def _calcular_inventario(produto, embalagem, quantidade):
    unidade_item = _to_str(produto.get("unidade", "")).upper()
    peso_liquido = _to_float(produto.get("peso_liquido", 0))
    densidade = _to_float(produto.get("densidade", 1))

    if densidade <= 0:
        densidade = 1

    calculo = calcular_quantidades_wms(
        embalagem_lancada=embalagem,
        unidade_item=unidade_item,
        quantidade_digitada=quantidade,
        peso_liquido_item=peso_liquido,
        densidade_item=densidade,
    )

    peso_calculado = _to_float(calculo.get("peso_calculado", 0))
    quantidade_embalagem = _to_float(calculo.get("quantidade_embalagem", 0))

    if unidade_item == "L":
        peso_convertido = peso_calculado / densidade
        unidade_normal = "KG"
        unidade_convertida = "L"
    else:
        peso_convertido = peso_calculado
        unidade_normal = unidade_item if unidade_item else "KG"
        unidade_convertida = unidade_normal

    return {
        "quantidade_embalagem": quantidade_embalagem,
        "peso_calculado": peso_calculado,
        "peso_convertido": peso_convertido,
        "unidade_normal": unidade_normal,
        "unidade_convertida": unidade_convertida,
    }


def _montar_exportacao_estoque(df_base: pd.DataFrame) -> pd.DataFrame:
    if df_base.empty:
        return pd.DataFrame()

    df = df_base.copy()

    for coluna in [
        "produto_codigo",
        "localizacao_codigo",
        "lote",
        "embalagem",
        "peso_calculado",
        "quantidade_embalagem",
        "unidade",
        "status",
        "observacao",
    ]:
        if coluna not in df.columns:
            df[coluna] = ""

    df["embalagem"] = df["embalagem"].fillna("").astype(str).str.upper().str.strip()
    df["peso_calculado"] = pd.to_numeric(df["peso_calculado"], errors="coerce").fillna(0.0)
    df["quantidade_embalagem"] = pd.to_numeric(df["quantidade_embalagem"], errors="coerce").fillna(0.0)

    df["quantidade"] = df.apply(
        lambda row: float(row["peso_calculado"]) if row["embalagem"] == "GR" else float(row["quantidade_embalagem"]),
        axis=1
    )

    return df[
        [
            "produto_codigo",
            "localizacao_codigo",
            "lote",
            "embalagem",
            "quantidade",
            "unidade",
            "status",
            "observacao",
        ]
    ].copy()


def app():
    st.title("📋 Inventário")

    _inicializar_estado()
    _resetar_se_precisar()
    _mostrar_mensagens()

    df_local = _buscar_localizacoes()

    if df_local.empty:
        st.warning("Nenhuma localização ativa encontrada. Cadastre em Administração > Cadastros > Localizações.")
        return

    localizacoes = _montar_localizacoes(df_local)
    opcoes_localizacao = ["Selecione..."] + list(localizacoes.keys())

    opcoes_status = ["DISPONIVEL", "BLOQUEADO", "AVARIA"]
    opcoes_contagem = ["CONTAGEM 1", "CONTAGEM 2", "CONTAGEM 3"]

    st.caption("Escaneie o produto, escolha a contagem e salve. Cada leitura vira uma linha do inventário.")

    col_top1, col_top2, col_top3 = st.columns([2, 3, 1])

    with col_top1:
        st.selectbox(
            "Contagem",
            opcoes_contagem,
            key="inv_contagem_widget"
        )

    with col_top2:
        st.selectbox(
            "Localização",
            opcoes_localizacao,
            key="inv_localizacao_widget"
        )

    with col_top3:
        if st.button("Excluir TODO inventário"):
            st.session_state["inv_confirmar_limpar"] = True
            st.rerun()

    if st.session_state.get("inv_confirmar_limpar", False):
        st.error("Tem certeza que deseja excluir TODO o inventário? Essa ação não pode ser desfeita.")

        col_conf1, col_conf2 = st.columns(2)

        with col_conf1:
            if st.button("Sim, limpar inventário"):
                try:
                    _limpar_inventario()
                    st.session_state["inv_confirmar_limpar"] = False
                    st.session_state["msg_sucesso_inv"] = "Inventário limpo com sucesso. ID reiniciado."
                    st.rerun()
                except Exception as e:
                    st.session_state["msg_erro_inv"] = f"Erro ao limpar inventário: {e}"
                    st.rerun()

        with col_conf2:
            if st.button("Não, cancelar"):
                st.session_state["inv_confirmar_limpar"] = False
                st.rerun()

    st.divider()

    st.text_input(
        "Código do Produto",
        key="inv_codigo_widget",
        on_change=_normalizar_codigo,
        placeholder="Escaneie ou digite o código"
    )

    codigo = _normalizar_texto(st.session_state.get("inv_codigo_widget", ""))
    produto = _buscar_produto(codigo)

    if codigo:
        if produto is None:
            st.error("Produto não encontrado no cadastro.")
        else:
            st.success(f"Produto encontrado: {produto['codigo']} - {produto['descricao']}")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Quantidade",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="inv_quantidade_widget"
        )

        st.text_input(
            "Lote",
            key="inv_lote_widget",
            on_change=_normalizar_lote,
            placeholder="Escaneie ou digite o lote"
        )

    with col2:
        opcoes_embalagem = ["Selecione..."]

        if produto is not None:
            emb = _to_str(produto.get("emb", "")).upper()

            if emb and emb != "GR":
                opcoes_embalagem.append(emb)

            opcoes_embalagem.append("GR")
        else:
            opcoes_embalagem.append("GR")

        if st.session_state.get("inv_embalagem_widget") not in opcoes_embalagem:
            st.session_state["inv_embalagem_widget"] = "Selecione..."

        st.selectbox(
            "Embalagem",
            opcoes_embalagem,
            key="inv_embalagem_widget"
        )

        st.selectbox(
            "Status",
            opcoes_status,
            key="inv_status_widget"
        )

    st.text_area(
        "Observação",
        key="inv_observacao_widget"
    )

    if produto is not None:
        quantidade = float(st.session_state.get("inv_quantidade_widget", 0.0))
        embalagem = st.session_state.get("inv_embalagem_widget", "Selecione...")

        if quantidade > 0 and embalagem != "Selecione...":
            calculo_previa = _calcular_inventario(produto, embalagem, quantidade)

            st.info(
                f"Prévia | Embalagens: {calculo_previa['quantidade_embalagem']:.3f} | "
                f"Normal: {calculo_previa['peso_calculado']:.3f} {calculo_previa['unidade_normal']} | "
                f"Convertido: {calculo_previa['peso_convertido']:.3f} {calculo_previa['unidade_convertida']}"
            )

    if st.button("Salvar Leitura do Inventário"):
        codigo = _normalizar_texto(st.session_state.get("inv_codigo_widget", ""))
        produto = _buscar_produto(codigo)

        contagem = st.session_state.get("inv_contagem_widget", "CONTAGEM 1")
        localizacao_escolhida = st.session_state.get("inv_localizacao_widget", "Selecione...")
        quantidade = float(st.session_state.get("inv_quantidade_widget", 0.0))
        lote = _normalizar_texto(st.session_state.get("inv_lote_widget", ""))
        embalagem = st.session_state.get("inv_embalagem_widget", "Selecione...")
        status = st.session_state.get("inv_status_widget", "DISPONIVEL")
        observacao = _to_str(st.session_state.get("inv_observacao_widget", ""))

        if produto is None:
            st.session_state["msg_erro_inv"] = "Produto inválido."
            st.rerun()

        if localizacao_escolhida == "Selecione...":
            st.session_state["msg_erro_inv"] = "Selecione a localização."
            st.rerun()

        if embalagem == "Selecione...":
            st.session_state["msg_erro_inv"] = "Selecione a embalagem."
            st.rerun()

        if quantidade <= 0:
            st.session_state["msg_erro_inv"] = "Informe quantidade maior que zero."
            st.rerun()

        calculo = _calcular_inventario(produto, embalagem, quantidade)

        usuario = usuario_logado()
        localizacao_codigo = localizacoes[localizacao_escolhida]
        empresa_id = empresa_operacional_obrigatoria()
        custo_unitario = _to_float(produto.get("custo_unitario", 0))
        custo_total = float(calculo["peso_calculado"]) * custo_unitario

        try:
            conversa_banco.insert("inventario", {
                "data_hora": datetime.now().isoformat(),
                "contagem": contagem,
                "empresa_id": empresa_id,
                "produto_codigo": codigo,
                "descricao": _to_str(produto.get("descricao", "")),
                "localizacao_codigo": localizacao_codigo,
                "lote": lote,
                "embalagem": embalagem,
                "quantidade_embalagem": float(calculo["quantidade_embalagem"]),
                "peso_calculado": float(calculo["peso_calculado"]),
                "custo_unitario": custo_unitario,
                "custo_total": custo_total,
                "peso_convertido": float(calculo["peso_convertido"]),
                "unidade": _to_str(produto.get("unidade", "")),
                "unidade_normal": calculo["unidade_normal"],
                "unidade_convertida": calculo["unidade_convertida"],
                "status": status,
                "usuario": usuario["nome"] if usuario else "N/A",
                "observacao": observacao,
            })

            st.session_state["msg_sucesso_inv"] = f"Leitura salva em {contagem}."
            st.session_state["inv_resetar"] = True
            st.rerun()

        except Exception as e:
            st.session_state["msg_erro_inv"] = f"Erro ao salvar inventário: {e}"
            st.rerun()

    st.divider()
    st.subheader("Extrato do Inventário")

    df_inv = _carregar_inventario()

    if df_inv.empty:
        st.info("Nenhuma leitura de inventário registrada ainda.")
        return

    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)

    with col_f1:
        filtro_produto = st.text_input("Filtrar Produto", key="inv_filtro_produto")

    with col_f2:
        filtro_localizacao = st.text_input("Filtrar Localização", key="inv_filtro_localizacao")

    with col_f3:
        filtro_contagem = st.selectbox(
            "Filtrar Contagem",
            ["TODAS", "CONTAGEM 1", "CONTAGEM 2", "CONTAGEM 3"],
            key="inv_filtro_contagem"
        )

    with col_f4:
        filtro_status = st.selectbox(
            "Filtrar Status",
            ["TODOS", "DISPONIVEL", "BLOQUEADO", "AVARIA"],
            key="inv_filtro_status"
        )

    with col_f5:
        somente_unicos = st.checkbox(
            "Códigos únicos",
            key="inv_somente_unicos"
        )

    df_exibir = df_inv.copy()

    if "data_hora" in df_exibir.columns:
        df_exibir["data_hora"] = pd.to_datetime(df_exibir["data_hora"], errors="coerce")
        df_exibir = df_exibir.sort_values(by="data_hora", ascending=False)

    if filtro_produto.strip():
        termo = filtro_produto.strip()
        df_exibir = df_exibir[
            df_exibir["produto_codigo"].astype(str).str.contains(termo, case=False, na=False)
            | df_exibir["descricao"].astype(str).str.contains(termo, case=False, na=False)
        ]

    if filtro_localizacao.strip():
        termo = filtro_localizacao.strip()
        df_exibir = df_exibir[
            df_exibir["localizacao_codigo"].astype(str).str.contains(termo, case=False, na=False)
        ]

    if filtro_contagem != "TODAS":
        df_exibir = df_exibir[df_exibir["contagem"].astype(str).str.upper() == filtro_contagem]

    if filtro_status != "TODOS":
        df_exibir = df_exibir[df_exibir["status"].astype(str).str.upper() == filtro_status]

    if somente_unicos:
        df_exibir = df_exibir.drop_duplicates(
            subset=["produto_codigo"],
            keep="first"
        )

    colunas_exibir = [
        "data_hora",
        "contagem",
        "produto_codigo",
        "descricao",
        "localizacao_codigo",
        "lote",
        "embalagem",
        "quantidade_embalagem",
        "peso_calculado",
        "unidade_normal",
        "peso_convertido",
        "unidade_convertida",
        "status",
        "usuario",
        "observacao",
    ]

    colunas_exibir = [c for c in colunas_exibir if c in df_exibir.columns]

    st.dataframe(
        df_exibir[colunas_exibir],
        use_container_width=True,
        hide_index=True
    )

    st.divider()
    st.subheader("Resumo por Contagem")

    resumo_base = df_exibir.copy()

    if resumo_base.empty:
        st.info("Nenhum dado para resumir com os filtros atuais.")
        return

    resumo = (
        resumo_base.groupby(
            [
                "contagem",
                "produto_codigo",
                "descricao",
                "localizacao_codigo",
                "lote",
                "embalagem",
                "unidade_normal",
                "unidade_convertida",
            ],
            as_index=False,
            dropna=False
        )[["quantidade_embalagem", "peso_calculado", "peso_convertido"]]
        .sum()
    )

    st.dataframe(
        resumo,
        use_container_width=True,
        hide_index=True
    )

    st.divider()
    st.subheader("Exportações")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        csv_completo = _df_para_csv_bytes(df_exibir[colunas_exibir])

        st.download_button(
            label="Exportar Inventário Completo",
            data=csv_completo,
            file_name="inventario_completo.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_exp2:
        df_estoque = _montar_exportacao_estoque(resumo_base)
        csv_estoque = _df_para_csv_bytes(df_estoque)

        st.download_button(
            label="Exportar para Importar Estoque",
            data=csv_estoque,
            file_name="inventario_para_importar_estoque.csv",
            mime="text/csv",
            use_container_width=True
        )