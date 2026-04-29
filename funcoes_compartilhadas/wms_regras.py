# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from funcoes_compartilhadas import conversa_banco


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


def _normalizar_texto(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    for coluna in colunas:
        df = _garantir_coluna(df, coluna, "")
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()
    return df


def calcular_saldo_por_localizacao() -> pd.DataFrame:
    try:
        df = conversa_banco.select("movimentacoes", order_by="data_hora")
    except Exception:
        df = conversa_banco.select("movimentacoes")

    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    colunas_necessarias = [
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
    ]

    for coluna in colunas_necessarias:
        df = _garantir_coluna(df, coluna, "")

    df = _normalizar_texto(df, [
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
    ])

    for coluna_num in ["quantidade", "quantidade_embalagem", "peso_calculado"]:
        df[coluna_num] = pd.to_numeric(df[coluna_num], errors="coerce").fillna(0.0)

    movimentos = []

    for _, row in df.iterrows():
        tipo = _to_str(row["tipo"]).upper()

        if tipo == "ENTRADA":
            movimentos.append({
                "produto_codigo": _to_str(row["produto_codigo"]).upper(),
                "localizacao_codigo": _to_str(row["localizacao_codigo"]).upper(),
                "lote": _to_str(row["lote"]).upper(),
                "status": _to_str(row["status"]).upper(),
                "saldo": float(row["peso_calculado"]),
                "saldo_embalagem": float(row["quantidade_embalagem"]),
                "saldo_peso": float(row["peso_calculado"]),
            })

        elif tipo == "SAIDA":
            movimentos.append({
                "produto_codigo": _to_str(row["produto_codigo"]).upper(),
                "localizacao_codigo": _to_str(row["localizacao_codigo"]).upper(),
                "lote": _to_str(row["lote"]).upper(),
                "status": _to_str(row["status"]).upper(),
                "saldo": -float(row["peso_calculado"]),
                "saldo_embalagem": -float(row["quantidade_embalagem"]),
                "saldo_peso": -float(row["peso_calculado"]),
            })

        elif tipo == "MOVIMENTACAO":
            produto = _to_str(row["produto_codigo"]).upper()
            origem = _to_str(row["localizacao_origem_codigo"]).upper()
            destino = _to_str(row["localizacao_destino_codigo"]).upper()

            lote_origem = _to_str(row["lote_origem"]).upper()
            lote_destino = _to_str(row["lote_destino"]).upper()
            if not lote_destino:
                lote_destino = _to_str(row["lote"]).upper()

            status_origem = _to_str(row["status_origem"]).upper()
            status_destino = _to_str(row["status_destino"]).upper()
            if not status_destino:
                status_destino = _to_str(row["status"]).upper()

            quantidade_embalagem = float(row["quantidade_embalagem"])
            peso_calculado = float(row["peso_calculado"])

            movimentos.append({
                "produto_codigo": produto,
                "localizacao_codigo": origem,
                "lote": lote_origem,
                "status": status_origem,
                "saldo": -peso_calculado,
                "saldo_embalagem": -quantidade_embalagem,
                "saldo_peso": -peso_calculado,
            })

            movimentos.append({
                "produto_codigo": produto,
                "localizacao_codigo": destino,
                "lote": lote_destino,
                "status": status_destino,
                "saldo": peso_calculado,
                "saldo_embalagem": quantidade_embalagem,
                "saldo_peso": peso_calculado,
            })

    if not movimentos:
        return pd.DataFrame()

    saldo = pd.DataFrame(movimentos)

    saldo = (
        saldo.groupby(
            ["produto_codigo", "localizacao_codigo", "lote", "status"],
            as_index=False,
            dropna=False
        )[["saldo", "saldo_embalagem", "saldo_peso"]]
        .sum()
    )

    saldo = saldo[(saldo["saldo"] != 0) | (saldo["saldo_embalagem"] != 0)].copy()

    saldo = saldo.sort_values(
        by=["produto_codigo", "localizacao_codigo", "lote", "status"]
    ).reset_index(drop=True)

    return saldo


def validar_saida(
    produto_codigo: str,
    localizacao_codigo: str,
    lote: str,
    status: str,
    quantidade: float,
    embalagem_item: str,
):
    saldo = calcular_saldo_por_localizacao()

    if saldo.empty:
        return False, "Não existe saldo disponível."

    filtro = saldo[
        (saldo["produto_codigo"].astype(str).str.upper() == str(produto_codigo).upper()) &
        (saldo["localizacao_codigo"].astype(str).str.upper() == str(localizacao_codigo).upper()) &
        (saldo["lote"].astype(str).str.upper() == str(lote).upper()) &
        (saldo["status"].astype(str).str.upper() == str(status).upper())
    ]

    if filtro.empty:
        return False, "Saldo não encontrado para o item selecionado."

    linha = filtro.iloc[0]

    embalagem_item = _to_str(embalagem_item).upper()

    if embalagem_item == "GR":
        saldo_disponivel = float(linha["saldo_peso"])
    else:
        saldo_disponivel = float(linha["saldo_embalagem"])

    if float(quantidade) > saldo_disponivel:
        return False, f"Quantidade maior que o saldo disponível ({saldo_disponivel:.3f})."

    return True, "OK"


def validar_movimentacao(
    produto_codigo: str,
    origem: str,
    destino: str,
    lote_origem: str,
    lote_destino: str,
    status_origem: str,
    status_destino: str,
    quantidade: float,
    embalagem_item: str,
):
    if str(origem).strip().upper() == str(destino).strip().upper():
        return False, "Origem e destino não podem ser iguais."

    saldo = calcular_saldo_por_localizacao()

    if saldo.empty:
        return False, "Não existe saldo disponível."

    filtro = saldo[
        (saldo["produto_codigo"].astype(str).str.upper() == str(produto_codigo).upper()) &
        (saldo["localizacao_codigo"].astype(str).str.upper() == str(origem).upper()) &
        (saldo["lote"].astype(str).str.upper() == str(lote_origem).upper()) &
        (saldo["status"].astype(str).str.upper() == str(status_origem).upper())
    ]

    if filtro.empty:
        return False, "Saldo de origem não encontrado."

    linha = filtro.iloc[0]

    embalagem_item = _to_str(embalagem_item).upper()

    if embalagem_item == "GR":
        saldo_disponivel = float(linha["saldo_peso"])
    else:
        saldo_disponivel = float(linha["saldo_embalagem"])

    if float(quantidade) > saldo_disponivel:
        return False, f"Quantidade maior que o saldo disponível ({saldo_disponivel:.3f})."

    return True, "OK"