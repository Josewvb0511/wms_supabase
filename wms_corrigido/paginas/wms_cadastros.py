# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_admin, hash_senha
from funcoes_compartilhadas.contexto_empresa import filtrar_df_empresas, empresa_operacional_obrigatoria


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


def _to_bool(valor):
    if isinstance(valor, bool):
        return valor

    if valor is None:
        return False

    txt = str(valor).strip().lower()
    return txt in ["true", "1", "sim", "s", "yes", "ativo"]


def _select_seguro(tabela, filtros=None, order_by=None):
    try:
        return conversa_banco.select(tabela, filtros=filtros, order_by=order_by)
    except TypeError:
        try:
            return conversa_banco.select(tabela)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _atualizar_linha(tabela, row_original, row_editada, colunas):
    registro_id = row_original.get("id")

    if registro_id is None:
        return

    dados = {}

    for coluna in colunas:
        if coluna == "id":
            continue

        valor_original = row_original.get(coluna)
        valor_editado = row_editada.get(coluna)

        if str(valor_original) != str(valor_editado):
            dados[coluna] = valor_editado

    if dados:
        conversa_banco.update(tabela, dados, {"id": int(registro_id)})


def _salvar_edicoes(tabela, df_original, df_editado, colunas):
    if df_original.empty or df_editado.empty:
        return

    try:
        for idx in range(len(df_editado)):
            row_original = df_original.iloc[idx].to_dict()
            row_editada = df_editado.iloc[idx].to_dict()
            _atualizar_linha(tabela, row_original, row_editada, colunas)
    except Exception as e:
        st.error(f"Erro ao salvar alterações: {e}")


def _excluir_registros(tabela, df_base, nome_item):
    if df_base.empty or "id" not in df_base.columns:
        return

    st.write("---")
    st.subheader("Exclusão")

    ids = df_base["id"].dropna().astype(int).tolist()

    ids_selecionados = st.multiselect(
        f"Selecione os IDs para excluir de {nome_item}",
        options=ids,
        key=f"excluir_{tabela}"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"Excluir selecionados - {nome_item}", key=f"btn_excluir_{tabela}"):
            if not ids_selecionados:
                st.warning("Nenhum ID selecionado.")
            else:
                try:
                    for item_id in ids_selecionados:
                        conversa_banco.delete(tabela, {"id": int(item_id)})

                    st.success("Registros excluídos com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")

    with col2:
        st.caption("Exclua com cuidado. Essa ação altera o banco.")


def _normalizar_produtos(df):
    if df.empty:
        return df

    df = df.copy()

    colunas_padrao = {
        "id": 0,
        "codigo": "",
        "descricao": "",
        "tipo": "",
        "unidade": "",
        "peso_liquido": 0.0,
        "densidade": 1.0,
        "empresa": "",
        "emb": "GR",
        "empresa_id": 0,
        "custo_unitario": 0.0,
        "moeda_custo": "BRL",
        "empresa_id": 0,
        "ativo": True,
    }

    for coluna, padrao in colunas_padrao.items():
        if coluna not in df.columns:
            df[coluna] = padrao

    df["codigo"] = df["codigo"].fillna("").astype(str).str.strip().str.upper()
    df["descricao"] = df["descricao"].fillna("").astype(str).str.strip()
    df["tipo"] = df["tipo"].fillna("").astype(str).str.strip().str.upper()
    df["unidade"] = df["unidade"].fillna("").astype(str).str.strip().str.upper()
    df["empresa"] = df["empresa"].fillna("").astype(str).str.strip().str.upper()
    df["emb"] = df["emb"].fillna("GR").astype(str).str.strip().str.upper()
    df["peso_liquido"] = pd.to_numeric(df["peso_liquido"], errors="coerce").fillna(0.0)
    df["densidade"] = pd.to_numeric(df["densidade"], errors="coerce").fillna(1.0)
    df["ativo"] = df["ativo"].apply(_to_bool)
    if "empresa_id" in df.columns:
        df["empresa_id"] = pd.to_numeric(df["empresa_id"], errors="coerce").fillna(0).astype(int)
    if "custo_unitario" in df.columns:
        df["custo_unitario"] = pd.to_numeric(df["custo_unitario"], errors="coerce").fillna(0.0)
    if "moeda_custo" in df.columns:
        df["moeda_custo"] = df["moeda_custo"].fillna("BRL").astype(str).str.strip().str.upper()

    return df


def _normalizar_localizacoes(df):
    if df.empty:
        return df

    df = df.copy()

    colunas_padrao = {
        "id": 0,
        "setor": "",
        "codigo": "",
        "local": "",
        "ativo": True,
    }

    for coluna, padrao in colunas_padrao.items():
        if coluna not in df.columns:
            df[coluna] = padrao

    df["setor"] = df["setor"].fillna("").astype(str).str.strip().str.upper()
    df["codigo"] = df["codigo"].fillna("").astype(str).str.strip().str.upper()
    df["local"] = df["local"].fillna("").astype(str).str.strip().str.upper()
    df["ativo"] = df["ativo"].apply(_to_bool)
    if "empresa_id" in df.columns:
        df["empresa_id"] = pd.to_numeric(df["empresa_id"], errors="coerce").fillna(0).astype(int)

    return df


def _normalizar_usuarios(df):
    if df.empty:
        return df

    df = df.copy()

    colunas_padrao = {
        "id": 0,
        "nome": "",
        "email": "",
        "perfil": "USUARIO",
        "ativo": True,
    }

    for coluna, padrao in colunas_padrao.items():
        if coluna not in df.columns:
            df[coluna] = padrao

    df["nome"] = df["nome"].fillna("").astype(str).str.strip()
    df["email"] = df["email"].fillna("").astype(str).str.strip().str.lower()
    df["perfil"] = df["perfil"].fillna("USUARIO").astype(str).str.strip().str.upper()
    df["ativo"] = df["ativo"].apply(_to_bool)

    return df


def _aba_produtos():
    st.subheader("Cadastro de Produtos")

    with st.form("form_produto", enter_to_submit=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            codigo = st.text_input("Código")
            descricao = st.text_input("Descrição")
            tipo = st.selectbox("Tipo", ["PA", "MP", "PI", "MC", "ME", "OUTRO"])

        with col2:
            unidade = st.selectbox("Unidade", ["KG", "L", "UN", "M", "CX", "PC", "SC", "OUTRA"])
            peso_liquido = st.number_input("Peso Líquido", min_value=0.0, step=1.0, format="%.3f")
            densidade = st.number_input("Densidade", min_value=0.0, step=0.01, value=1.0, format="%.3f")

        with col3:
            empresa = st.text_input("Empresa", value="SIDERQUIMICA")
            emb = st.text_input("Embalagem", value="GR")
            custo_unitario = st.number_input("Custo unitário", min_value=0.0, step=0.01, format="%.6f")
            moeda_custo = st.selectbox("Moeda custo", ["BRL", "USD", "EUR"])
            ativo = st.checkbox("Ativo", value=True)

        salvar = st.form_submit_button("Salvar Produto")

        if salvar:
            if not codigo.strip() or not descricao.strip():
                st.error("Código e descrição são obrigatórios.")
            else:
                try:
                    conversa_banco.insert("produtos", {
                        "codigo": codigo.strip().upper(),
                        "descricao": descricao.strip(),
                        "tipo": tipo.strip().upper(),
                        "unidade": unidade.strip().upper(),
                        "peso_liquido": float(peso_liquido),
                        "densidade": float(densidade),
                        "empresa": empresa.strip().upper(),
                        "empresa_id": empresa_operacional_obrigatoria(),
                        "emb": emb.strip().upper() if emb.strip() else "GR",
                        "custo_unitario": float(custo_unitario),
                        "moeda_custo": moeda_custo,
                        "ativo": bool(ativo),
                    })

                    st.success("Produto salvo com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar produto: {e}")

    st.write("---")
    st.subheader("Lista de Produtos")

    df = filtrar_df_empresas(_normalizar_produtos(_select_seguro("produtos", order_by="codigo")))

    if df.empty:
        st.info("Nenhum produto cadastrado.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_tipo = st.selectbox("Tipo", ["TODOS"] + sorted(df["tipo"].dropna().unique().tolist()))

    with col2:
        filtro_unidade = st.selectbox("Unidade", ["TODOS"] + sorted(df["unidade"].dropna().unique().tolist()))

    with col3:
        busca = st.text_input("Buscar produto")

    df_f = df.copy()

    if filtro_tipo != "TODOS":
        df_f = df_f[df_f["tipo"] == filtro_tipo]

    if filtro_unidade != "TODOS":
        df_f = df_f[df_f["unidade"] == filtro_unidade]

    if busca.strip():
        termo = busca.strip()
        df_f = df_f[
            df_f["codigo"].str.contains(termo, case=False, na=False)
            | df_f["descricao"].str.contains(termo, case=False, na=False)
            | df_f["empresa"].str.contains(termo, case=False, na=False)
        ]

    colunas = [
        "id",
        "codigo",
        "descricao",
        "tipo",
        "unidade",
        "peso_liquido",
        "densidade",
        "empresa",
        "emb",
        "empresa_id",
        "custo_unitario",
        "moeda_custo",
        "ativo",
    ]

    df_editor = df_f[colunas].copy()

    df_editado = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_produtos",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "codigo": st.column_config.TextColumn("Código"),
            "descricao": st.column_config.TextColumn("Descrição"),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=["PA", "MP", "PI", "MC", "ME", "OUTRO"]),
            "unidade": st.column_config.SelectboxColumn("Unidade", options=["KG", "L", "UN", "M", "CX", "PC", "SC", "OUTRA"]),
            "peso_liquido": st.column_config.NumberColumn("Peso Líquido", format="%.3f"),
            "densidade": st.column_config.NumberColumn("Densidade", format="%.3f"),
            "empresa": st.column_config.TextColumn("Empresa"),
            "emb": st.column_config.TextColumn("Emb."),
            "empresa_id": st.column_config.NumberColumn("Empresa ID", disabled=True),
            "custo_unitario": st.column_config.NumberColumn("Custo unitário", format="%.6f"),
            "moeda_custo": st.column_config.SelectboxColumn("Moeda", options=["BRL", "USD", "EUR"]),
            "ativo": st.column_config.CheckboxColumn("Ativo"),
        }
    )

    if st.button("Salvar alterações de produtos"):
        try:
            _salvar_edicoes("produtos", df_editor, df_editado, colunas)
            st.success("Alterações salvas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar produtos: {e}")

    _excluir_registros("produtos", df_f, "produto")


def _aba_localizacoes():
    st.subheader("Cadastro de Localizações")

    st.info("Essas localizações são as mesmas que aparecem nas telas de Entrada, Saída, Movimentação, Saldos e Inventário.")

    with st.form("form_localizacao", enter_to_submit=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            setor = st.text_input("Setor", placeholder="Ex: EXPEDIÇÃO")

        with col2:
            codigo = st.text_input("Código", placeholder="Ex: A")

        with col3:
            local = st.text_input("Local", placeholder="Ex: 1")

        with col4:
            ativo = st.checkbox("Ativo", value=True)

        salvar = st.form_submit_button("Salvar Localização")

        if salvar:
            if not setor.strip() or not codigo.strip() or not local.strip():
                st.error("Setor, código e local são obrigatórios.")
            else:
                try:
                    conversa_banco.insert("localizacoes", {
                        "setor": setor.strip().upper(),
                        "codigo": codigo.strip().upper(),
                        "local": local.strip().upper(),
                        "empresa_id": empresa_operacional_obrigatoria(),
                        "ativo": bool(ativo),
                    })

                    st.success("Localização salva com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar localização: {e}")

    st.write("---")
    st.subheader("Lista de Localizações")

    df = filtrar_df_empresas(_normalizar_localizacoes(_select_seguro("localizacoes", order_by="setor")))

    if df.empty:
        st.info("Nenhuma localização cadastrada.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_setor = st.selectbox("Setor", ["TODOS"] + sorted(df["setor"].dropna().unique().tolist()))

    with col2:
        filtro_ativo = st.selectbox("Status", ["TODOS", "ATIVOS", "INATIVOS"])

    with col3:
        busca = st.text_input("Buscar localização")

    df_f = df.copy()

    if filtro_setor != "TODOS":
        df_f = df_f[df_f["setor"] == filtro_setor]

    if filtro_ativo == "ATIVOS":
        df_f = df_f[df_f["ativo"] == True]

    if filtro_ativo == "INATIVOS":
        df_f = df_f[df_f["ativo"] == False]

    if busca.strip():
        termo = busca.strip()
        df_f = df_f[
            df_f["setor"].str.contains(termo, case=False, na=False)
            | df_f["codigo"].str.contains(termo, case=False, na=False)
            | df_f["local"].str.contains(termo, case=False, na=False)
        ]

    df_f["visualizacao"] = (
        df_f["setor"].astype(str) + " | " +
        df_f["codigo"].astype(str) + " | " +
        df_f["local"].astype(str)
    )

    colunas = ["id", "empresa_id", "setor", "codigo", "local", "visualizacao", "ativo"]

    df_editor = df_f[colunas].copy()

    df_editado = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_localizacoes",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "empresa_id": st.column_config.NumberColumn("Empresa ID", disabled=True),
            "setor": st.column_config.TextColumn("Setor"),
            "codigo": st.column_config.TextColumn("Código"),
            "local": st.column_config.TextColumn("Local"),
            "visualizacao": st.column_config.TextColumn("Como aparece nas telas", disabled=True),
            "ativo": st.column_config.CheckboxColumn("Ativo"),
        }
    )

    if st.button("Salvar alterações de localizações"):
        try:
            df_original = df_editor.drop(columns=["visualizacao"]).copy()
            df_editado_limpo = df_editado.drop(columns=["visualizacao"]).copy()

            _salvar_edicoes(
                "localizacoes",
                df_original,
                df_editado_limpo,
                ["id", "empresa_id", "setor", "codigo", "local", "ativo"]
            )

            st.success("Alterações salvas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar localizações: {e}")

    _excluir_registros("localizacoes", df_f, "localização")


def _aba_usuarios():
    st.subheader("Cadastro de Usuários")

    with st.form("form_usuario", enter_to_submit=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            nome = st.text_input("Nome")

        with col2:
            email = st.text_input("Email")

        with col3:
            senha = st.text_input("Senha", type="password")

        with col4:
            perfil = st.selectbox("Perfil", ["USUARIO", "ADMINISTRADOR", "ADMIN"])

        salvar = st.form_submit_button("Salvar Usuário")

        if salvar:
            if not nome.strip() or not email.strip() or not senha.strip():
                st.error("Nome, email e senha são obrigatórios.")
            else:
                try:
                    conversa_banco.insert("usuarios", {
                        "nome": nome.strip(),
                        "email": email.strip().lower(),
                        "senha": hash_senha(senha.strip()),
                        "perfil": perfil.strip().upper(),
                        "ativo": True,
                    })

                    st.success("Usuário salvo com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar usuário: {e}")

    st.write("---")
    st.subheader("Lista de Usuários")

    df = _normalizar_usuarios(_select_seguro("usuarios", order_by="nome"))

    if df.empty:
        st.info("Nenhum usuário cadastrado.")
        return

    colunas = ["id", "nome", "email", "perfil", "ativo"]

    df_editor = df[colunas].copy()

    df_editado = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_usuarios",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "nome": st.column_config.TextColumn("Nome"),
            "email": st.column_config.TextColumn("Email"),
            "perfil": st.column_config.SelectboxColumn("Perfil", options=["USUARIO", "ADMINISTRADOR", "ADMIN"]),
            "ativo": st.column_config.CheckboxColumn("Ativo"),
        }
    )

    if st.button("Salvar alterações de usuários"):
        try:
            _salvar_edicoes("usuarios", df_editor, df_editado, colunas)
            st.success("Alterações salvas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar usuários: {e}")

    _excluir_registros("usuarios", df, "usuário")


def app():
    st.title("⚙️ Cadastros")

    if not usuario_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    aba1, aba2, aba3 = st.tabs([
        "Produtos",
        "Localizações",
        "Usuários",
    ])

    with aba1:
        _aba_produtos()

    with aba2:
        _aba_localizacoes()

    with aba3:
        _aba_usuarios()