# -*- coding: utf-8 -*-
"""
Importação de CSV para cadastros do WMS.

Regras:
- Lê CSV com detecção automática de separador
- Limpa BOM invisível do Excel
- Valida se o INÍCIO do cabeçalho bate com o esperado
- Colunas extras depois do padrão são ignoradas
- Se o começo do cabeçalho não bater, não importa nada
- Faz UPSERT lógico:
    - se encontrar registro pela chave, atualiza
    - se não encontrar, insere
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import Callable, Dict, List, Tuple

import pandas as pd


# ==========================================================
# LEITURA SEGURA DO CSV
# ==========================================================
def ler_csv_upload(arquivo_csv) -> pd.DataFrame:
    """
    Lê o arquivo CSV enviado no Streamlit.

    Tenta:
    - UTF-8
    - UTF-8 com BOM
    - latin-1

    Detecta separador automaticamente.
    """
    bruto = arquivo_csv.getvalue()

    erros: List[str] = []

    for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            texto = bruto.decode(encoding)
            df = pd.read_csv(StringIO(texto), sep=None, engine="python")
            return df
        except Exception as e:
            erros.append(f"{encoding}: {e}")

    raise ValueError(
        "Não foi possível ler o CSV. Verifique encoding e separador. "
        + " | ".join(erros)
    )


# ==========================================================
# NORMALIZA CABEÇALHO
# ==========================================================
def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove espaços nas pontas, limpa BOM invisível e força cabeçalho em minúsculo.
    """
    df = df.copy()
    df.columns = [
        str(col)
        .replace("\ufeff", "")
        .replace("﻿", "")
        .strip()
        .lower()
        for col in df.columns
    ]
    return df


# ==========================================================
# VALIDA INÍCIO DO CABEÇALHO
# ==========================================================
def validar_inicio_cabecalho(df: pd.DataFrame, colunas_esperadas: List[str]) -> Tuple[bool, str]:
    """
    Exige que o início do cabeçalho bata com o padrão esperado.
    Colunas extras depois disso são permitidas e ignoradas.
    """
    colunas_recebidas = [str(col).strip().lower() for col in df.columns]
    colunas_esperadas = [str(col).strip().lower() for col in colunas_esperadas]

    if len(colunas_recebidas) < len(colunas_esperadas):
        return (
            False,
            f"Colunas insuficientes. Esperado no início: {colunas_esperadas} | Recebido: {colunas_recebidas}"
        )

    inicio_recebido = colunas_recebidas[:len(colunas_esperadas)]

    if inicio_recebido != colunas_esperadas:
        return (
            False,
            f"Cabeçalho inválido. O início precisa ser: {colunas_esperadas} | Recebido: {colunas_recebidas}"
        )

    return True, ""


# ==========================================================
# MANTÉM SÓ COLUNAS NECESSÁRIAS
# ==========================================================
def manter_apenas_colunas_necessarias(df: pd.DataFrame, colunas_necessarias: List[str]) -> pd.DataFrame:
    """
    Mantém somente as colunas obrigatórias e ignora o resto.
    """
    df = df.copy()
    return df[colunas_necessarias]


# ==========================================================
# FUNÇÕES DE APOIO
# ==========================================================
def texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def texto_upper(valor) -> str:
    return texto(valor).upper()


def bool_ativo(valor) -> bool:
    """
    Converte valores comuns para booleano.
    """
    v = texto_upper(valor)

    if v in ["TRUE", "1", "SIM", "S", "ATIVO", "VERDADEIRO"]:
        return True

    if v in ["FALSE", "0", "NAO", "NÃO", "N", "INATIVO", "FALSO"]:
        return False

    return False


# ==========================================================
# IMPORTAÇÃO DE PRODUTOS
# ==========================================================
def importar_produtos_csv(
    arquivo_csv,
    fn_select: Callable,
    fn_insert: Callable,
    fn_update: Callable,
) -> Dict[str, int | str]:
    """
    Início obrigatório do CSV:
    codigo,descricao,ativo

    Colunas extras depois disso são ignoradas.
    """
    df = ler_csv_upload(arquivo_csv)
    df = normalizar_colunas(df)

    colunas_base = ["codigo", "descricao", "ativo"]

    ok, msg = validar_inicio_cabecalho(df, colunas_base)
    if not ok:
        raise ValueError(msg)

    df = manter_apenas_colunas_necessarias(df, colunas_base)

    if df.empty:
        raise ValueError("O CSV de produtos está vazio.")

    df_existente = fn_select("produtos", order_by="codigo")
    if df_existente.empty:
        df_existente = pd.DataFrame(columns=["id", "codigo"])

    inseridos = 0
    atualizados = 0

    for _, row in df.iterrows():
        codigo = texto_upper(row["codigo"])
        descricao = texto(row["descricao"])
        ativo = bool_ativo(row["ativo"])

        if not codigo:
            raise ValueError("Existe linha com 'codigo' vazio no CSV de produtos.")

        encontrado = df_existente[
            df_existente["codigo"].astype(str).str.upper() == codigo
        ]

        dados = {
            "codigo": codigo,
            "descricao": descricao,
            "ativo": ativo,
        }

        if encontrado.empty:
            fn_insert("produtos", dados)
            inseridos += 1
        else:
            fn_update("produtos", dados, {"id": int(encontrado.iloc[0]["id"])})
            atualizados += 1

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "mensagem": "Importação de produtos concluída com sucesso.",
    }


# ==========================================================
# IMPORTAÇÃO DE LOCALIZAÇÕES
# ==========================================================
def importar_localizacoes_csv(
    arquivo_csv,
    fn_select: Callable,
    fn_insert: Callable,
    fn_update: Callable,
) -> Dict[str, int | str]:
    """
    Início obrigatório do CSV:
    setor,codigo,local,ativo

    Colunas extras depois disso são ignoradas.
    """
    df = ler_csv_upload(arquivo_csv)
    df = normalizar_colunas(df)

    colunas_base = ["setor", "codigo", "local", "ativo"]

    ok, msg = validar_inicio_cabecalho(df, colunas_base)
    if not ok:
        raise ValueError(msg)

    df = manter_apenas_colunas_necessarias(df, colunas_base)

    if df.empty:
        raise ValueError("O CSV de localizações está vazio.")

    df_existente = fn_select("localizacoes", order_by="setor")
    if df_existente.empty:
        df_existente = pd.DataFrame(columns=["id", "setor", "codigo", "local"])

    inseridos = 0
    atualizados = 0

    for _, row in df.iterrows():
        setor = texto_upper(row["setor"])
        codigo = texto_upper(row["codigo"])
        local = texto_upper(row["local"])
        ativo = bool_ativo(row["ativo"])

        if not setor or not codigo or not local:
            raise ValueError("Existe linha com 'setor', 'codigo' ou 'local' vazio no CSV de localizações.")

        encontrado = df_existente[
            (df_existente["setor"].astype(str).str.upper() == setor) &
            (df_existente["codigo"].astype(str).str.upper() == codigo) &
            (df_existente["local"].astype(str).str.upper() == local)
        ]

        dados = {
            "setor": setor,
            "codigo": codigo,
            "local": local,
            "ativo": ativo,
        }

        if encontrado.empty:
            dados["data_hora_cadastro"] = datetime.now().isoformat()
            fn_insert("localizacoes", dados)
            inseridos += 1
        else:
            fn_update("localizacoes", dados, {"id": int(encontrado.iloc[0]["id"])})
            atualizados += 1

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "mensagem": "Importação de localizações concluída com sucesso.",
    }


# ==========================================================
# IMPORTAÇÃO DE USUÁRIOS
# ==========================================================
def importar_usuarios_csv(
    arquivo_csv,
    fn_select: Callable,
    fn_insert: Callable,
    fn_update: Callable,
    fn_hash_senha: Callable,
) -> Dict[str, int | str]:
    """
    Início obrigatório do CSV:
    nome,email,senha,perfil,ativo

    Colunas extras depois disso são ignoradas.
    """
    df = ler_csv_upload(arquivo_csv)
    df = normalizar_colunas(df)

    colunas_base = ["nome", "email", "senha", "perfil", "ativo"]

    ok, msg = validar_inicio_cabecalho(df, colunas_base)
    if not ok:
        raise ValueError(msg)

    df = manter_apenas_colunas_necessarias(df, colunas_base)

    if df.empty:
        raise ValueError("O CSV de usuários está vazio.")

    df_existente = fn_select("usuarios", order_by="nome")
    if df_existente.empty:
        df_existente = pd.DataFrame(columns=["id", "nome"])

    inseridos = 0
    atualizados = 0

    for _, row in df.iterrows():
        nome = texto(row["nome"])
        email = texto(row["email"]).lower()
        senha = texto(row["senha"])
        perfil = texto_upper(row["perfil"])
        ativo = bool_ativo(row["ativo"])

        if not nome or not email or not senha:
            raise ValueError("Existe linha com 'nome', 'email' ou 'senha' vazio no CSV de usuários.")

        if perfil not in ["USUARIO", "ADMINISTRADOR"]:
            raise ValueError(f"Perfil inválido no CSV de usuários: {perfil}")

        encontrado = df_existente[
            df_existente["nome"].astype(str).str.lower() == nome.lower()
        ]

        dados = {
            "nome": nome,
            "email": email,
            "senha": fn_hash_senha(senha),
            "perfil": perfil,
            "ativo": ativo,
        }

        if encontrado.empty:
            fn_insert("usuarios", dados)
            inseridos += 1
        else:
            fn_update("usuarios", dados, {"id": int(encontrado.iloc[0]["id"])})
            atualizados += 1

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "mensagem": "Importação de usuários concluída com sucesso.",
    }