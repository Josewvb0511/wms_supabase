# -*- coding: utf-8 -*-
from typing import Any


def _to_str(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _to_float(valor: Any) -> float:
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


def calcular_quantidades_wms(
    embalagem_lancada: str,
    unidade_item: str,
    quantidade_digitada: float,
    peso_liquido_item: float,
    densidade_item: float,
) -> dict:
    """
    Regra definitiva:

    Campos retornados:
    - quantidade_embalagem
    - peso_calculado
    - quantidade_convertida
    - unidade_convertida

    Regras:
    1) Embalagem = GR
       - quantidade_embalagem = 1
       - se unidade = L:
            peso_calculado = quantidade_digitada * densidade
            quantidade_convertida = quantidade_digitada
            unidade_convertida = L
       - outras unidades:
            peso_calculado = quantidade_digitada
            quantidade_convertida = quantidade_digitada
            unidade_convertida = unidade_item

    2) Embalagem != GR
       - quantidade_embalagem = quantidade_digitada
       - peso_calculado = peso_liquido_item * quantidade_digitada
       - se unidade = L:
            quantidade_convertida = peso_calculado / densidade
            unidade_convertida = L
       - outras unidades:
            quantidade_convertida = peso_calculado
            unidade_convertida = unidade_item
    """
    embalagem = _to_str(embalagem_lancada).upper()
    unidade = _to_str(unidade_item).upper()

    quantidade = _to_float(quantidade_digitada)
    peso_liquido = _to_float(peso_liquido_item)
    densidade = _to_float(densidade_item)

    if quantidade <= 0:
        return {
            "quantidade_embalagem": 0.0,
            "peso_calculado": 0.0,
            "quantidade_convertida": 0.0,
            "unidade_convertida": unidade if unidade else "UN",
        }

    # ----------------------------------------------------------
    # GRANEL / ABERTO
    # ----------------------------------------------------------
    if embalagem == "GR":
        quantidade_embalagem = 1.0

        if unidade == "L":
            peso_calculado = quantidade * densidade
            quantidade_convertida = quantidade
            unidade_convertida = "L"
        else:
            peso_calculado = quantidade
            quantidade_convertida = quantidade
            unidade_convertida = unidade if unidade else "UN"

        return {
            "quantidade_embalagem": round(quantidade_embalagem, 6),
            "peso_calculado": round(peso_calculado, 6),
            "quantidade_convertida": round(quantidade_convertida, 6),
            "unidade_convertida": unidade_convertida,
        }

    # ----------------------------------------------------------
    # EMBALAGEM FECHADA
    # peso_liquido já está em KG
    # ----------------------------------------------------------
    quantidade_embalagem = quantidade
    peso_calculado = peso_liquido * quantidade

    if unidade == "L" and densidade > 0:
        quantidade_convertida = peso_calculado / densidade
        unidade_convertida = "L"
    else:
        quantidade_convertida = peso_calculado
        unidade_convertida = unidade if unidade else "UN"

    return {
        "quantidade_embalagem": round(quantidade_embalagem, 6),
        "peso_calculado": round(peso_calculado, 6),
        "quantidade_convertida": round(quantidade_convertida, 6),
        "unidade_convertida": unidade_convertida,
    }