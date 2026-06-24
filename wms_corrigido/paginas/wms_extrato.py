# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.contexto_empresa import filtrar_df_empresas, empresa_operacional_obrigatoria
from funcoes_compartilhadas.wms_conversoes import (
    carregar_produtos_para_conversao,
    enriquecer_movimentacoes_com_conversoes,
)


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


def _garantir_coluna(df: pd.DataFrame, coluna: str, padrao="") -> pd.DataFrame:
    if coluna not in df.columns:
        df[coluna] = padrao
    return df


def _preparar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    colunas_texto = [
        "tipo",
        "produto_codigo",
        "descricao_cadastro",
        "embalagem",
        "unidade",
        "unidade_normal",
        "unidade_convertida",
        "localizacao_codigo",
        "localizacao_origem_codigo",
        "localizacao_destino_codigo",
        "lote",
        "lote_origem",
        "lote_destino",
        "status",
        "status_origem",
        "status_destino",
        "grupo_logico_id",
        "grupo_logico_origem_id",
        "doc_log",
        "observacao",
        "usuario",
    ]

    colunas_numero = [
        "id",
        "quantidade_embalagem_ajustada",
        "peso_liquido",
        "peso_calculado",
        "peso_convertido",
        "item_gr_origem_id",
    ]

    for coluna in colunas_texto:
        df = _garantir_coluna(df, coluna, "")
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna in colunas_numero:
        df = _garantir_coluna(df, coluna, 0)
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    df = _garantir_coluna(df, "juntar_destino", False)
    df["juntar_destino"] = df["juntar_destino"].fillna(False).astype(bool)

    return df


def _grupo_destino(row) -> str:
    grupo = _to_str(row.get("grupo_logico_id", ""))

    if grupo:
        return grupo

    id_reg = int(_to_float(row.get("id", 0)))

    if id_reg > 0:
        return f"LEGADO|{id_reg}"

    return ""


def _grupo_origem(row) -> str:
    grupo = _to_str(row.get("grupo_logico_origem_id", ""))

    if grupo:
        return grupo

    item_id = int(_to_float(row.get("item_gr_origem_id", 0)))

    if item_id > 0:
        return f"LEGADO|{item_id}"

    return _grupo_destino(row)


def _linha_extrato(
    row,
    acao_extrato: str,
    quantidade_emb: float,
    peso_evento: float,
    peso_calculado: float,
    peso_convertido: float,
    localizacao: str,
    origem: str,
    destino: str,
    lote: str,
    lote_origem: str,
    lote_destino: str,
    status: str,
    status_origem: str,
    status_destino: str,
    grupo_origem: str,
    grupo_destino: str,
    juntou_destino: bool,
    observacao: str = "",
):
    return {
        "data_hora": row.get("data_hora", ""),
        "acao_extrato": acao_extrato,
        "produto_codigo": row.get("produto_codigo", ""),
        "descricao": row.get("descricao_cadastro", ""),
        "embalagem": row.get("embalagem", ""),
        "quantidade_emb": quantidade_emb,
        "peso_liquido": row.get("peso_liquido", 0),
        "peso_evento": peso_evento,
        "peso_calculado": peso_calculado,
        "peso_convertido": peso_convertido,
        "unidade_normal": row.get("unidade_normal", ""),
        "unidade_convertida": row.get("unidade_convertida", ""),
        "unidade": row.get("unidade", ""),
        "localizacao": localizacao,
        "origem": origem,
        "destino": destino,
        "lote": lote,
        "lote_origem": lote_origem,
        "lote_destino": lote_destino,
        "status": status,
        "status_origem": status_origem,
        "status_destino": status_destino,
        "grupo_origem": grupo_origem,
        "grupo_destino": grupo_destino,
        "juntou_destino": juntou_destino,
        "doc_log": row.get("doc_log", ""),
        "observacao": observacao,
        "usuario": row.get("usuario", ""),
    }


def _montar_extrato_expandido(df: pd.DataFrame) -> pd.DataFrame:
    df = _preparar_df(df)

    linhas = []
    saldo_por_grupo = {}

    df_ordem = df.copy()
    df_ordem["data_hora_ordem"] = pd.to_datetime(df_ordem["data_hora"], errors="coerce")
    df_ordem = df_ordem.sort_values(by=["data_hora_ordem", "id"], ascending=True)

    for _, row in df_ordem.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        embalagem = _to_str(row.get("embalagem", "")).upper()

        peso = _to_float(row.get("peso_calculado", 0))
        peso_convertido = _to_float(row.get("peso_convertido", 0))
        quantidade_emb = _to_float(row.get("quantidade_embalagem_ajustada", 0))

        grupo_destino = _grupo_destino(row)
        grupo_origem = _grupo_origem(row)

        localizacao = _to_str(row.get("localizacao_codigo", ""))
        origem = _to_str(row.get("localizacao_origem_codigo", ""))
        destino = _to_str(row.get("localizacao_destino_codigo", ""))

        lote = _to_str(row.get("lote", ""))
        lote_origem = _to_str(row.get("lote_origem", ""))
        lote_destino = _to_str(row.get("lote_destino", "")) or lote

        status = _to_str(row.get("status", ""))
        status_origem = _to_str(row.get("status_origem", ""))
        status_destino = _to_str(row.get("status_destino", "")) or status

        juntou_destino = bool(row.get("juntar_destino", False))

        if tipo == "ENTRADA":
            linhas.append(
                _linha_extrato(
                    row=row,
                    acao_extrato="ENTRADA",
                    quantidade_emb=quantidade_emb,
                    peso_evento=peso,
                    peso_calculado=peso,
                    peso_convertido=peso_convertido,
                    localizacao=localizacao,
                    origem="",
                    destino=localizacao,
                    lote=lote,
                    lote_origem="",
                    lote_destino=lote,
                    status=status,
                    status_origem="",
                    status_destino=status,
                    grupo_origem="",
                    grupo_destino=grupo_destino,
                    juntou_destino=False,
                    observacao=row.get("observacao", ""),
                )
            )

            if embalagem == "GR":
                saldo_por_grupo[grupo_destino] = saldo_por_grupo.get(grupo_destino, 0.0) + peso

        elif tipo == "SAIDA":
            linhas.append(
                _linha_extrato(
                    row=row,
                    acao_extrato="SAÍDA",
                    quantidade_emb=-quantidade_emb,
                    peso_evento=-peso,
                    peso_calculado=peso,
                    peso_convertido=peso_convertido,
                    localizacao=localizacao,
                    origem=localizacao,
                    destino="",
                    lote=lote,
                    lote_origem=lote,
                    lote_destino="",
                    status=status,
                    status_origem=status,
                    status_destino="",
                    grupo_origem=grupo_origem,
                    grupo_destino="",
                    juntou_destino=False,
                    observacao=row.get("observacao", ""),
                )
            )

            if embalagem == "GR":
                saldo_por_grupo[grupo_origem] = saldo_por_grupo.get(grupo_origem, 0.0) - peso

        elif tipo == "MOVIMENTACAO":
            if embalagem == "GR" and juntou_destino:
                saldo_origem_antes = saldo_por_grupo.get(grupo_origem, 0.0)
                saldo_destino_antes = saldo_por_grupo.get(grupo_destino, 0.0)
                saldo_final_destino = saldo_destino_antes + peso

                linhas.append(
                    _linha_extrato(
                        row=row,
                        acao_extrato="MOVIMENTAÇÃO SAÍDA ORIGEM",
                        quantidade_emb=0,
                        peso_evento=-peso,
                        peso_calculado=peso,
                        peso_convertido=peso,
                        localizacao=origem,
                        origem=origem,
                        destino=destino,
                        lote=lote_origem,
                        lote_origem=lote_origem,
                        lote_destino=lote_destino,
                        status=status_origem,
                        status_origem=status_origem,
                        status_destino=status_destino,
                        grupo_origem=grupo_origem,
                        grupo_destino=grupo_destino,
                        juntou_destino=True,
                        observacao=f"Saiu {peso:.3f} KG da sobra de origem.",
                    )
                )

                linhas.append(
                    _linha_extrato(
                        row=row,
                        acao_extrato="MOVIMENTAÇÃO SAÍDA SOBRA DESTINO",
                        quantidade_emb=0,
                        peso_evento=-saldo_destino_antes,
                        peso_calculado=saldo_destino_antes,
                        peso_convertido=saldo_destino_antes,
                        localizacao=destino,
                        origem=destino,
                        destino=destino,
                        lote=lote_destino,
                        lote_origem=lote_destino,
                        lote_destino=lote_destino,
                        status=status_destino,
                        status_origem=status_destino,
                        status_destino=status_destino,
                        grupo_origem=grupo_destino,
                        grupo_destino=grupo_destino,
                        juntou_destino=True,
                        observacao=f"Sobra destino anterior removida para junção: {saldo_destino_antes:.3f} KG.",
                    )
                )

                linhas.append(
                    _linha_extrato(
                        row=row,
                        acao_extrato="MOVIMENTAÇÃO ENTRADA JUNÇÃO",
                        quantidade_emb=1,
                        peso_evento=saldo_final_destino,
                        peso_calculado=saldo_final_destino,
                        peso_convertido=saldo_final_destino,
                        localizacao=destino,
                        origem=origem,
                        destino=destino,
                        lote=lote_destino,
                        lote_origem=lote_origem,
                        lote_destino=lote_destino,
                        status=status_destino,
                        status_origem=status_origem,
                        status_destino=status_destino,
                        grupo_origem=grupo_origem,
                        grupo_destino=grupo_destino,
                        juntou_destino=True,
                        observacao=f"Nova sobra após junção: {peso:.3f} KG + {saldo_destino_antes:.3f} KG = {saldo_final_destino:.3f} KG.",
                    )
                )

                saldo_por_grupo[grupo_origem] = saldo_origem_antes - peso
                saldo_por_grupo[grupo_destino] = saldo_final_destino

            else:
                linhas.append(
                    _linha_extrato(
                        row=row,
                        acao_extrato="MOVIMENTAÇÃO SAÍDA",
                        quantidade_emb=-quantidade_emb,
                        peso_evento=-peso,
                        peso_calculado=peso,
                        peso_convertido=peso_convertido,
                        localizacao=origem,
                        origem=origem,
                        destino=destino,
                        lote=lote_origem,
                        lote_origem=lote_origem,
                        lote_destino=lote_destino,
                        status=status_origem,
                        status_origem=status_origem,
                        status_destino=status_destino,
                        grupo_origem=grupo_origem,
                        grupo_destino=grupo_destino,
                        juntou_destino=False,
                        observacao=f"Saída da origem: {peso:.3f}.",
                    )
                )

                linhas.append(
                    _linha_extrato(
                        row=row,
                        acao_extrato="MOVIMENTAÇÃO ENTRADA",
                        quantidade_emb=quantidade_emb,
                        peso_evento=peso,
                        peso_calculado=peso,
                        peso_convertido=peso_convertido,
                        localizacao=destino,
                        origem=origem,
                        destino=destino,
                        lote=lote_destino,
                        lote_origem=lote_origem,
                        lote_destino=lote_destino,
                        status=status_destino,
                        status_origem=status_origem,
                        status_destino=status_destino,
                        grupo_origem=grupo_origem,
                        grupo_destino=grupo_destino,
                        juntou_destino=False,
                        observacao=f"Entrada no destino: {peso:.3f}.",
                    )
                )

                if embalagem == "GR":
                    saldo_por_grupo[grupo_origem] = saldo_por_grupo.get(grupo_origem, 0.0) - peso
                    saldo_por_grupo[grupo_destino] = saldo_por_grupo.get(grupo_destino, 0.0) + peso

    if not linhas:
        return pd.DataFrame()

    df_extrato = pd.DataFrame(linhas)
    df_extrato["data_hora"] = pd.to_datetime(df_extrato["data_hora"], errors="coerce")
    df_extrato = df_extrato.sort_values(by="data_hora", ascending=False).reset_index(drop=True)

    return df_extrato


def app():
    st.title("📊 Extrato de Movimentações")

    try:
        df_mov = filtrar_df_empresas(conversa_banco.select("movimentacoes", order_by="data_hora"))
    except Exception:
        df_mov = filtrar_df_empresas(conversa_banco.select("movimentacoes"))

    if df_mov is None or df_mov.empty:
        st.warning("Nenhuma movimentação encontrada.")
        return

    df_prod = carregar_produtos_para_conversao()
    df = enriquecer_movimentacoes_com_conversoes(df_mov, df_prod)

    if df.empty:
        st.warning("Nenhuma movimentação encontrada.")
        return

    df_extrato = _montar_extrato_expandido(df)

    if df_extrato.empty:
        st.warning("Nenhuma movimentação encontrada.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_produto = st.text_input("Produto")

    with col2:
        filtro_tipo = st.selectbox(
            "Tipo",
            [
                "TODOS",
                "ENTRADA",
                "SAÍDA",
                "MOVIMENTAÇÃO SAÍDA",
                "MOVIMENTAÇÃO ENTRADA",
                "MOVIMENTAÇÃO SAÍDA ORIGEM",
                "MOVIMENTAÇÃO SAÍDA SOBRA DESTINO",
                "MOVIMENTAÇÃO ENTRADA JUNÇÃO",
            ]
        )

    with col3:
        filtro_localizacao = st.text_input("Localização")

    df_filtrado = df_extrato.copy()

    if filtro_produto.strip():
        termo = filtro_produto.strip()

        df_filtrado = df_filtrado[
            df_filtrado["produto_codigo"].astype(str).str.contains(termo, case=False, na=False)
            | df_filtrado["descricao"].astype(str).str.contains(termo, case=False, na=False)
        ]

    if filtro_tipo != "TODOS":
        df_filtrado = df_filtrado[
            df_filtrado["acao_extrato"].astype(str).str.upper() == filtro_tipo.upper()
        ]

    if filtro_localizacao.strip():
        termo = filtro_localizacao.strip()

        df_filtrado = df_filtrado[
            df_filtrado["localizacao"].astype(str).str.contains(termo, case=False, na=False)
            | df_filtrado["origem"].astype(str).str.contains(termo, case=False, na=False)
            | df_filtrado["destino"].astype(str).str.contains(termo, case=False, na=False)
        ]

    if df_filtrado.empty:
        st.info("Nenhuma movimentação encontrada com os filtros informados.")
        return

    colunas_exibir = [
        "data_hora",
        "acao_extrato",
        "produto_codigo",
        "descricao",
        "embalagem",
        "quantidade_emb",
        "peso_evento",
        "peso_calculado",
        "peso_convertido",
        "unidade_normal",
        "unidade_convertida",
        "localizacao",
        "origem",
        "destino",
        "lote",
        "lote_origem",
        "lote_destino",
        "status",
        "status_origem",
        "status_destino",
        "grupo_origem",
        "grupo_destino",
        "juntou_destino",
        "doc_log",
        "observacao",
        "usuario",
    ]

    colunas_exibir = [c for c in colunas_exibir if c in df_filtrado.columns]

    st.dataframe(
        df_filtrado[colunas_exibir],
        use_container_width=True,
        hide_index=True
    )