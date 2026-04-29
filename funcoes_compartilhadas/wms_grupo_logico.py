# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
import uuid
import pandas as pd


def _to_str(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _to_float(valor) -> float:
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


def _garantir_coluna(df: pd.DataFrame, coluna: str, valor_padrao="") -> pd.DataFrame:
    if coluna not in df.columns:
        df[coluna] = valor_padrao
    return df


def novo_grupo_logico_id(produto_codigo: str, localizacao_codigo: str, lote: str, doc_log: str = "") -> str:
    produto = _to_str(produto_codigo).upper() or "SEM_PRODUTO"
    local = _to_str(localizacao_codigo).upper() or "SEM_LOCAL"
    lote_txt = _to_str(lote).upper() or "SEM_LOTE"
    doc = _to_str(doc_log).upper() or "SEM_DOC"

    carimbo = datetime.now().strftime("%Y%m%d%H%M%S%f")
    sufixo = uuid.uuid4().hex[:8].upper()

    return f"{produto}|{local}|{lote_txt}|{doc}|{carimbo}|{sufixo}"


def preparar_movimentacoes_para_grupo_logico(df_mov: pd.DataFrame) -> pd.DataFrame:
    if df_mov is None or df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()

    colunas = [
        "id",
        "tipo",
        "produto_codigo",
        "localizacao_codigo",
        "localizacao_origem_codigo",
        "localizacao_destino_codigo",
        "quantidade_embalagem",
        "peso_calculado",
        "peso_convertido",
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
        "juntar_destino",
        "doc_log",
        "unidade_normal",
        "unidade_convertida",
    ]

    for coluna in colunas:
        df = _garantir_coluna(df, coluna, "")

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
        "doc_log",
        "unidade_normal",
        "unidade_convertida",
    ]:
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna in ["id", "quantidade_embalagem", "peso_calculado", "peso_convertido", "item_gr_origem_id"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    df["juntar_destino"] = df["juntar_destino"].fillna(False).astype(bool)

    def _grupo_destino(row):
        grupo = _to_str(row.get("grupo_logico_id", ""))

        if grupo:
            return grupo

        id_reg = int(_to_float(row.get("id", 0)))

        if id_reg > 0:
            return f"LEGADO|{id_reg}"

        return ""

    def _grupo_origem(row):
        grupo = _to_str(row.get("grupo_logico_origem_id", ""))

        if grupo:
            return grupo

        item_gr_id = int(_to_float(row.get("item_gr_origem_id", 0)))

        if item_gr_id > 0:
            return f"LEGADO|{item_gr_id}"

        grupo_destino = _to_str(row.get("grupo_logico_id", ""))

        if grupo_destino:
            return grupo_destino

        id_reg = int(_to_float(row.get("id", 0)))

        if id_reg > 0:
            return f"LEGADO|{id_reg}"

        return ""

    df["grupo_logico_id"] = df.apply(_grupo_destino, axis=1)
    df["grupo_logico_origem_id"] = df.apply(_grupo_origem, axis=1)

    return df


def montar_saldo_por_grupo_logico(df_mov: pd.DataFrame) -> pd.DataFrame:
    df = preparar_movimentacoes_para_grupo_logico(df_mov)

    if df.empty:
        return pd.DataFrame()

    movimentos = []

    for _, row in df.iterrows():
        tipo = _to_str(row.get("tipo", "")).upper()
        embalagem = _to_str(row.get("embalagem", "")).upper()
        produto = _to_str(row.get("produto_codigo", "")).upper()

        grupo_destino = _to_str(row.get("grupo_logico_id", ""))
        grupo_origem = _to_str(row.get("grupo_logico_origem_id", ""))

        peso = _to_float(row.get("peso_calculado", 0))
        peso_convertido = _to_float(row.get("peso_convertido", 0))
        quantidade_embalagem = _to_float(row.get("quantidade_embalagem", 0))

        unidade_normal = _to_str(row.get("unidade_normal", "")).upper()
        unidade_convertida = _to_str(row.get("unidade_convertida", "")).upper()

        if tipo == "ENTRADA":
            movimentos.append({
                "grupo_logico_id": grupo_destino,
                "produto_codigo": produto,
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _to_str(row.get("lote", "")).upper(),
                "status": _to_str(row.get("status", "")).upper(),
                "embalagem": embalagem,
                "unidade_normal": unidade_normal,
                "unidade_convertida": unidade_convertida,
                "saldo_embalagem_mov": quantidade_embalagem if embalagem != "GR" else 0.0,
                "saldo_normal_mov": peso,
                "saldo_convertido_mov": peso_convertido,
            })

        elif tipo == "SAIDA":
            movimentos.append({
                "grupo_logico_id": grupo_origem,
                "produto_codigo": produto,
                "localizacao_codigo": _to_str(row.get("localizacao_codigo", "")).upper(),
                "lote": _to_str(row.get("lote", "")).upper(),
                "status": _to_str(row.get("status", "")).upper(),
                "embalagem": embalagem,
                "unidade_normal": unidade_normal,
                "unidade_convertida": unidade_convertida,
                "saldo_embalagem_mov": -quantidade_embalagem if embalagem != "GR" else 0.0,
                "saldo_normal_mov": -peso,
                "saldo_convertido_mov": -peso_convertido,
            })

        elif tipo == "MOVIMENTACAO":
            lote_origem = _to_str(row.get("lote_origem", "")).upper()
            lote_destino = _to_str(row.get("lote_destino", "")).upper() or _to_str(row.get("lote", "")).upper()

            status_origem = _to_str(row.get("status_origem", "")).upper()
            status_destino = _to_str(row.get("status_destino", "")).upper() or _to_str(row.get("status", "")).upper()

            movimentos.append({
                "grupo_logico_id": grupo_origem,
                "produto_codigo": produto,
                "localizacao_codigo": _to_str(row.get("localizacao_origem_codigo", "")).upper(),
                "lote": lote_origem,
                "status": status_origem,
                "embalagem": embalagem,
                "unidade_normal": unidade_normal,
                "unidade_convertida": unidade_convertida,
                "saldo_embalagem_mov": -quantidade_embalagem if embalagem != "GR" else 0.0,
                "saldo_normal_mov": -peso,
                "saldo_convertido_mov": -peso_convertido,
            })

            movimentos.append({
                "grupo_logico_id": grupo_destino,
                "produto_codigo": produto,
                "localizacao_codigo": _to_str(row.get("localizacao_destino_codigo", "")).upper(),
                "lote": lote_destino,
                "status": status_destino,
                "embalagem": embalagem,
                "unidade_normal": unidade_normal,
                "unidade_convertida": unidade_convertida,
                "saldo_embalagem_mov": quantidade_embalagem if embalagem != "GR" else 0.0,
                "saldo_normal_mov": peso,
                "saldo_convertido_mov": peso_convertido,
            })

    if not movimentos:
        return pd.DataFrame()

    base = pd.DataFrame(movimentos)

    saldo_grupo = (
        base.groupby(
            [
                "grupo_logico_id",
                "produto_codigo",
                "localizacao_codigo",
                "lote",
                "status",
                "embalagem",
                "unidade_normal",
                "unidade_convertida",
            ],
            as_index=False,
            dropna=False,
        )[["saldo_embalagem_mov", "saldo_normal_mov", "saldo_convertido_mov"]]
        .sum()
    )

    def _saldo_embalagem_final(row):
        embalagem = _to_str(row.get("embalagem", "")).upper()
        saldo_peso = _to_float(row.get("saldo_normal_mov", 0))
        saldo_emb = _to_float(row.get("saldo_embalagem_mov", 0))

        if embalagem == "GR":
            return 1.0 if saldo_peso > 0 else 0.0

        return saldo_emb if saldo_emb > 0 else 0.0

    saldo_grupo["saldo_embalagem_final"] = saldo_grupo.apply(_saldo_embalagem_final, axis=1)
    saldo_grupo["saldo_normal_final"] = saldo_grupo["saldo_normal_mov"]
    saldo_grupo["saldo_convertido_final"] = saldo_grupo["saldo_convertido_mov"]

    saldo_grupo = saldo_grupo[
        (saldo_grupo["saldo_embalagem_final"] > 0)
        | (saldo_grupo["saldo_normal_final"] > 0)
        | (saldo_grupo["saldo_convertido_final"] > 0)
    ].copy()

    return saldo_grupo.reset_index(drop=True)