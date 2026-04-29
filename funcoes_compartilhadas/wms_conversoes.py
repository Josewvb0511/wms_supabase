# -*- coding: utf-8 -*-
import pandas as pd

from funcoes_compartilhadas import conversa_banco


def _garantir_coluna(df: pd.DataFrame, coluna: str, valor_padrao="") -> pd.DataFrame:
    if coluna not in df.columns:
        df[coluna] = valor_padrao
    return df


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


def carregar_produtos_para_conversao() -> pd.DataFrame:
    """
    Comentário:
    Busca o cadastro de produtos para enriquecer extrato e saldo
    com descrição, unidade, densidade e peso líquido.
    """
    try:
        df_prod = conversa_banco.select("produtos", filtros={"ativo": True}, order_by="codigo")
    except Exception:
        df_prod = conversa_banco.select("produtos")

    if df_prod is None or df_prod.empty:
        return pd.DataFrame(
            columns=[
                "produto_codigo_merge",
                "descricao_cadastro",
                "unidade_cadastro",
                "densidade_cadastro",
                "peso_liquido_cadastro",
            ]
        )

    df_prod = df_prod.copy()

    for coluna in ["codigo", "descricao", "unidade"]:
        df_prod = _garantir_coluna(df_prod, coluna, "")
        df_prod[coluna] = df_prod[coluna].fillna("").astype(str).str.strip()

    for coluna in ["densidade", "peso_liquido"]:
        df_prod = _garantir_coluna(df_prod, coluna, 0)
        df_prod[coluna] = pd.to_numeric(df_prod[coluna], errors="coerce").fillna(0.0)

    df_prod = df_prod.rename(
        columns={
            "codigo": "produto_codigo_merge",
            "descricao": "descricao_cadastro",
            "unidade": "unidade_cadastro",
            "densidade": "densidade_cadastro",
            "peso_liquido": "peso_liquido_cadastro",
        }
    )

    return df_prod[
        [
            "produto_codigo_merge",
            "descricao_cadastro",
            "unidade_cadastro",
            "densidade_cadastro",
            "peso_liquido_cadastro",
        ]
    ].copy()


def enriquecer_movimentacoes_com_conversoes(df_mov: pd.DataFrame, df_prod: pd.DataFrame) -> pd.DataFrame:
    """
    Comentário:
    Regra unificada para Extrato e Saldos.

    Campos gerados:
    - quantidade_embalagem_ajustada
    - peso_calculado
    - peso_convertido
    - unidade_normal
    - unidade_convertida

    Regras:
    1) Produto com unidade L
       - peso_calculado = sempre em KG
       - se embalagem = GR -> usa quantidade gravada
       - se embalagem != GR -> quantidade_emb * peso_liquido
       - peso_convertido = peso_calculado / densidade  -> L
       - unidade_normal = KG
       - unidade_convertida = L

    2) Produto com outras unidades
       - peso_calculado = quantidade gravada
       - peso_convertido = mesmo valor
       - unidade_normal = unidade do cadastro
       - unidade_convertida = unidade do cadastro

    3) Regras da coluna quantidade_embalagem_ajustada
       - ENTRADA GR conta 1 embalagem
       - SAIDA GR conta 0 embalagem
       - MOVIMENTACAO GR conta 0 embalagem
       - Embalagens fechadas usam a quantidade_embalagem gravada
    """
    if df_mov is None or df_mov.empty:
        return pd.DataFrame()

    df = df_mov.copy()

    colunas_mov = [
        "id",
        "data_movimento",
        "data_hora",
        "usuario",
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
        "unidade",
        "observacao",
    ]

    for coluna in colunas_mov:
        df = _garantir_coluna(df, coluna, "")

    for coluna in [
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
        "unidade",
        "tipo",
        "usuario",
        "observacao",
    ]:
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna in ["quantidade", "quantidade_embalagem", "peso_calculado"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    if df_prod is not None and not df_prod.empty:
        df = df.merge(
            df_prod,
            how="left",
            left_on="produto_codigo",
            right_on="produto_codigo_merge"
        )
    else:
        df["descricao_cadastro"] = ""
        df["unidade_cadastro"] = ""
        df["densidade_cadastro"] = 0.0
        df["peso_liquido_cadastro"] = 0.0

    for coluna in ["descricao_cadastro", "unidade_cadastro"]:
        df = _garantir_coluna(df, coluna, "")
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna in ["densidade_cadastro", "peso_liquido_cadastro"]:
        df = _garantir_coluna(df, coluna, 0)
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    df["unidade_base"] = df["unidade_cadastro"].fillna("").astype(str).str.strip().str.upper()
    df["embalagem_base"] = df["embalagem"].fillna("").astype(str).str.strip().str.upper()
    df["tipo_base"] = df["tipo"].fillna("").astype(str).str.strip().str.upper()
    df["densidade"] = df["densidade_cadastro"]
    df["peso_liquido"] = df["peso_liquido_cadastro"]

    def _corrigir_quantidade_embalagem(row):
        embalagem = str(row.get("embalagem_base", "")).upper()
        tipo = str(row.get("tipo_base", "")).upper()

        # Comentário:
        # GR na entrada conta 1 embalagem.
        if embalagem == "GR" and tipo == "ENTRADA":
            return 1.0

        # Comentário:
        # GR em saída e movimentação não baixa embalagem.
        if embalagem == "GR" and tipo in ["SAIDA", "MOVIMENTACAO"]:
            return 0.0

        qtd_emb = _to_float(row.get("quantidade_embalagem", 0))
        if qtd_emb > 0:
            return qtd_emb

        return 0.0

    df["quantidade_embalagem_ajustada"] = df.apply(_corrigir_quantidade_embalagem, axis=1)

    def _calcular_peso_normal(row):
        unidade = str(row.get("unidade_base", "")).upper()
        embalagem = str(row.get("embalagem_base", "")).upper()

        quantidade = _to_float(row.get("quantidade", 0))
        qtd_emb = _to_float(row.get("quantidade_embalagem_ajustada", 0))
        peso_liquido = _to_float(row.get("peso_liquido", 0))

        if unidade == "L":
            if embalagem == "GR":
                return quantidade
            return qtd_emb * peso_liquido

        return quantidade

    df["peso_calculado"] = df.apply(_calcular_peso_normal, axis=1)

    def _calcular_peso_convertido(row):
        unidade = str(row.get("unidade_base", "")).upper()
        densidade = _to_float(row.get("densidade", 0))
        peso_normal = _to_float(row.get("peso_calculado", 0))

        if unidade == "L" and densidade > 0:
            return peso_normal / densidade

        return peso_normal

    df["peso_convertido"] = df.apply(_calcular_peso_convertido, axis=1)

    def _definir_unidade_normal(row):
        unidade = str(row.get("unidade_base", "")).upper()

        if unidade == "L":
            return "KG"

        return unidade if unidade else "UN"

    df["unidade_normal"] = df.apply(_definir_unidade_normal, axis=1)

    def _definir_unidade_convertida(row):
        unidade = str(row.get("unidade_base", "")).upper()

        if unidade == "L":
            return "L"

        return unidade if unidade else "UN"

    df["unidade_convertida"] = df.apply(_definir_unidade_convertida, axis=1)

    for coluna in [
        "quantidade",
        "quantidade_embalagem",
        "quantidade_embalagem_ajustada",
        "peso_liquido",
        "densidade",
        "peso_calculado",
        "peso_convertido",
    ]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    return df