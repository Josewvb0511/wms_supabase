# -*- coding: utf-8 -*-
import os
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import streamlit as st
from supabase import Client, create_client


# ==========================================================
# CONFIGURAÇÃO DO SUPABASE
# ==========================================================
def _pegar_config(nome: str) -> str:
    """
    Busca configuração primeiro no st.secrets e depois nas variáveis de ambiente.
    Não quebra se o secrets.toml não existir.
    """
    valor = None

    # Comentário: tenta ler do st.secrets sem quebrar se o arquivo não existir
    try:
        valor = st.secrets.get(nome)
    except Exception:
        valor = None

    # Comentário: se não encontrou em st.secrets, tenta variável de ambiente
    if valor is None or str(valor).strip() == "":
        valor = os.getenv(nome)

    if valor is None or str(valor).strip() == "":
        raise RuntimeError(
            f"Configuração '{nome}' não encontrada.\n\n"
            f"Você precisa definir essa chave em UMA destas opções:\n"
            f"1. Arquivo .streamlit/secrets.toml\n"
            f"2. Variável de ambiente do Windows\n\n"
            f"Chaves esperadas:\n"
            f"- SUPABASE_URL\n"
            f"- SUPABASE_KEY"
        )

    return str(valor).strip()


SUPABASE_URL = _pegar_config("SUPABASE_URL")
SUPABASE_KEY = _pegar_config("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
def _aplicar_filtros(query, filtros: Optional[Dict[str, Any]] = None):
    """
    Aplica filtros simples no select/update/delete.
    """
    if not filtros:
        return query

    for coluna, valor in filtros.items():
        if valor is None:
            query = query.is_(coluna, "null")
        else:
            query = query.eq(coluna, valor)

    return query


def _quebrar_em_lotes(
    registros: List[Dict[str, Any]],
    tamanho_lote: int = 500
) -> List[List[Dict[str, Any]]]:
    """
    Divide a lista em lotes menores.
    """
    return [
        registros[i:i + tamanho_lote]
        for i in range(0, len(registros), tamanho_lote)
    ]


def _retorno_para_dataframe_ou_lista(
    dados: List[Dict[str, Any]],
    as_dataframe: bool = True
):
    """
    Retorna DataFrame por padrão, mantendo compatibilidade com o sistema.
    """
    if as_dataframe:
        if not dados:
            return pd.DataFrame()
        return pd.DataFrame(dados)

    return dados


# ==========================================================
# SELECT COM PAGINAÇÃO REAL
# ==========================================================
def select(
    tabela: str,
    filtros: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    ascending: bool = True,
    page_size: int = 1000,
    as_dataframe: bool = True
):
    """
    Busca TODOS os registros da tabela usando paginação.
    Isso corrige o problema de trazer só 300 / 1000 registros.
    """
    todos_registros: List[Dict[str, Any]] = []
    inicio = 0

    while True:
        query = supabase.table(tabela).select("*")
        query = _aplicar_filtros(query, filtros)

        if order_by:
            query = query.order(order_by, desc=not ascending)

        fim = inicio + page_size - 1
        resposta = query.range(inicio, fim).execute()

        lote = resposta.data or []

        if not lote:
            break

        todos_registros.extend(lote)

        # Comentário: se veio menos que o page_size, acabou
        if len(lote) < page_size:
            break

        inicio += page_size

    return _retorno_para_dataframe_ou_lista(todos_registros, as_dataframe=as_dataframe)


# ==========================================================
# INSERT COM LOTE
# ==========================================================
def insert(
    tabela: str,
    dados: Union[Dict[str, Any], List[Dict[str, Any]]],
    batch_size: int = 500
):
    """
    Insere 1 registro ou vários registros em lotes.
    """
    if isinstance(dados, dict):
        resposta = supabase.table(tabela).insert(dados).execute()
        return resposta.data

    if not isinstance(dados, list):
        raise ValueError("O parâmetro 'dados' deve ser dict ou list[dict].")

    if not dados:
        return []

    retorno_total = []
    lotes = _quebrar_em_lotes(dados, tamanho_lote=batch_size)

    for lote in lotes:
        resposta = supabase.table(tabela).insert(lote).execute()
        retorno_total.extend(resposta.data or [])

    return retorno_total


# ==========================================================
# UPDATE
# ==========================================================
def update(
    tabela: str,
    dados: Dict[str, Any],
    filtros: Dict[str, Any]
):
    """
    Atualiza registros conforme filtros.
    """
    if not filtros:
        raise ValueError("Update exige filtros para segurança.")

    query = supabase.table(tabela).update(dados)
    query = _aplicar_filtros(query, filtros)
    resposta = query.execute()
    return resposta.data


# ==========================================================
# DELETE
# ==========================================================
def delete(
    tabela: str,
    filtros: Dict[str, Any]
):
    """
    Exclui registros conforme filtros.
    """
    if not filtros:
        raise ValueError("Delete exige filtros para segurança.")

    query = supabase.table(tabela).delete()
    query = _aplicar_filtros(query, filtros)
    resposta = query.execute()
    return resposta.data


# ==========================================================
# UPSERT OPCIONAL
# ==========================================================
def upsert(
    tabela: str,
    dados: Union[Dict[str, Any], List[Dict[str, Any]]],
    on_conflict: str,
    batch_size: int = 500
):
    """
    Faz upsert por coluna única, ex: codigo.
    """
    if isinstance(dados, dict):
        resposta = supabase.table(tabela).upsert(
            dados,
            on_conflict=on_conflict
        ).execute()
        return resposta.data

    if not isinstance(dados, list):
        raise ValueError("O parâmetro 'dados' deve ser dict ou list[dict].")

    if not dados:
        return []

    retorno_total = []
    lotes = _quebrar_em_lotes(dados, tamanho_lote=batch_size)

    for lote in lotes:
        resposta = supabase.table(tabela).upsert(
            lote,
            on_conflict=on_conflict
        ).execute()
        retorno_total.extend(resposta.data or [])

    return retorno_total