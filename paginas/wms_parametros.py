# -*- coding: utf-8 -*-
import io
import pandas as pd
import streamlit as st

from funcoes_compartilhadas import conversa_banco
from funcoes_compartilhadas.controle_acesso import usuario_admin


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
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


def _to_str(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _to_bool(valor):
    if isinstance(valor, bool):
        return valor

    if valor is None:
        return False

    txt = str(valor).strip().lower()
    return txt in ["true", "1", "sim", "s", "yes", "verdadeiro"]


def _codigo_embalagem_existe(codigo: str, df_embalagens: pd.DataFrame) -> bool:
    if not codigo or df_embalagens.empty or "codigo" not in df_embalagens.columns:
        return False

    codigo = str(codigo).strip().upper()
    base = df_embalagens["codigo"].fillna("").astype(str).str.strip().str.upper()

    return codigo in base.tolist()


def _ler_csv_upload(arquivo) -> pd.DataFrame:
    """
    Lê CSV aceitando UTF-8 ou latin1.
    """
    conteudo = arquivo.getvalue()

    for encoding in ["utf-8", "latin1", "cp1252"]:
        try:
            return pd.read_csv(
                io.BytesIO(conteudo),
                dtype=str,
                sep=None,
                engine="python",
                encoding=encoding
            )
        except Exception:
            continue

    raise ValueError("Não foi possível ler o CSV. Verifique a codificação do arquivo.")


def importar_embalagens_csv(arquivo_csv):
    """
    Importa embalagens a partir de CSV com layout:
    codigo,peso_embalagem,ativo
    """
    df_csv = _ler_csv_upload(arquivo_csv)

    if df_csv.empty:
        raise ValueError("O arquivo CSV está vazio.")

    df_csv.columns = [str(col).strip().lower() for col in df_csv.columns]

    cabecalho_obrigatorio = ["codigo", "peso_embalagem", "ativo"]
    cabecalho_inicio = df_csv.columns[:3].tolist()

    if cabecalho_inicio != cabecalho_obrigatorio:
        raise ValueError(
            "Cabeçalho inválido. O início do CSV deve ser exatamente: codigo,peso_embalagem,ativo"
        )

    df_csv = df_csv.copy()
    df_csv["codigo"] = df_csv["codigo"].fillna("").astype(str).str.strip().str.upper()
    df_csv["peso_embalagem"] = df_csv["peso_embalagem"].apply(_to_float)
    df_csv["ativo"] = df_csv["ativo"].apply(_to_bool)

    df_csv = df_csv[df_csv["codigo"] != ""].copy()

    if df_csv.empty:
        raise ValueError("Nenhuma linha válida encontrada no CSV.")

    df_csv = df_csv.drop_duplicates(subset=["codigo"], keep="last").reset_index(drop=True)

    df_base = conversa_banco.select("embalagens", order_by="codigo")
    if df_base.empty:
        df_base = pd.DataFrame(columns=["id", "codigo", "peso_embalagem", "ativo"])

    if "codigo" not in df_base.columns:
        df_base["codigo"] = ""

    df_base["codigo"] = df_base["codigo"].fillna("").astype(str).str.strip().str.upper()

    inseridos = 0
    atualizados = 0

    for _, row in df_csv.iterrows():
        codigo = row["codigo"]
        peso_embalagem = _to_float(row["peso_embalagem"])
        ativo = _to_bool(row["ativo"])

        existente = df_base[df_base["codigo"] == codigo]

        if existente.empty:
            conversa_banco.insert(
                "embalagens",
                {
                    "codigo": codigo,
                    "peso_embalagem": peso_embalagem,
                    "ativo": ativo,
                }
            )
            inseridos += 1
        else:
            embalagem_id = int(existente.iloc[0]["id"])
            conversa_banco.update(
                "embalagens",
                {
                    "codigo": codigo,
                    "peso_embalagem": peso_embalagem,
                    "ativo": ativo,
                },
                {"id": embalagem_id}
            )
            atualizados += 1

    return {
        "mensagem": "Importação concluída com sucesso.",
        "inseridos": inseridos,
        "atualizados": atualizados,
        "total_linhas_validas": len(df_csv),
    }


def excluir_registros(tabela, df, nome_item="registro"):
    """
    Exclusão com:
    - selecionar todos
    - excluir selecionados
    - excluir todos com confirmação
    """
    if df.empty or "id" not in df.columns:
        return

    chave_confirmacao = f"confirmar_excluir_todos_{tabela}"
    chave_selecionar_todos = f"selecionar_todos_{tabela}"
    chave_snapshot = f"selecionar_todos_snapshot_{tabela}"

    if chave_confirmacao not in st.session_state:
        st.session_state[chave_confirmacao] = False

    if chave_selecionar_todos not in st.session_state:
        st.session_state[chave_selecionar_todos] = False

    if chave_snapshot not in st.session_state:
        st.session_state[chave_snapshot] = False

    st.write("### Exclusão")

    ids = df["id"].astype(int).tolist()

    # Comentário: checkbox mestre para marcar ou desmarcar todos
    selecionar_todos = st.checkbox(
        "Selecionar todos",
        key=chave_selecionar_todos
    )

    if selecionar_todos != st.session_state[chave_snapshot]:
        for item_id in ids:
            st.session_state[f"excluir_{tabela}_{item_id}"] = selecionar_todos

        st.session_state[chave_snapshot] = selecionar_todos
        st.rerun()

    selecionados = []

    for item_id in ids:
        marcado = st.checkbox(
            f"ID {item_id}",
            key=f"excluir_{tabela}_{item_id}"
        )
        if marcado:
            selecionados.append(item_id)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Excluir Selecionados", use_container_width=True, key=f"btn_excluir_sel_{tabela}"):
            if not selecionados:
                st.warning("Nenhum registro selecionado.")
            else:
                try:
                    for item_id in selecionados:
                        conversa_banco.delete(tabela, {"id": int(item_id)})

                        chave_item = f"excluir_{tabela}_{item_id}"
                        if chave_item in st.session_state:
                            del st.session_state[chave_item]

                    st.session_state[chave_selecionar_todos] = False
                    st.session_state[chave_snapshot] = False

                    st.success("Registros excluídos com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")

    with col2:
        if st.button("Excluir TODOS", use_container_width=True, key=f"btn_excluir_todos_{tabela}"):
            st.session_state[chave_confirmacao] = True
            st.rerun()

    if st.session_state[chave_confirmacao]:
        st.error(f"Tem certeza que deseja excluir TODOS os {nome_item}s? Essa ação não pode ser desfeita.")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Sim, excluir tudo", use_container_width=True, key=f"btn_confirma_excluir_todos_{tabela}"):
                try:
                    for item_id in ids:
                        conversa_banco.delete(tabela, {"id": int(item_id)})

                        chave_item = f"excluir_{tabela}_{item_id}"
                        if chave_item in st.session_state:
                            del st.session_state[chave_item]

                    st.session_state[chave_confirmacao] = False
                    st.session_state[chave_selecionar_todos] = False
                    st.session_state[chave_snapshot] = False

                    st.success("Todos os registros foram excluídos.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir tudo: {e}")

        with c2:
            if st.button("Não, cancelar", use_container_width=True, key=f"btn_cancela_excluir_todos_{tabela}"):
                st.session_state[chave_confirmacao] = False
                st.info("Exclusão cancelada.")
                st.rerun()


def salvar_edicoes_embalagens(df_base_banco: pd.DataFrame, df_tela_editado: pd.DataFrame):
    if df_base_banco.empty or df_tela_editado.empty:
        return

    if "id" not in df_base_banco.columns or "id" not in df_tela_editado.columns:
        st.error("A coluna 'id' é obrigatória para salvar alterações.")
        return

    base = df_base_banco.copy().reset_index(drop=True)
    editado = df_tela_editado.copy().reset_index(drop=True)

    colunas_editaveis = [
        "codigo",
        "peso_embalagem",
        "ativo",
    ]

    alteracoes = []

    for _, linha_editada in editado.iterrows():
        item_id = int(linha_editada["id"])

        linha_base = base[base["id"].astype(int) == item_id]
        if linha_base.empty:
            continue

        linha_base = linha_base.iloc[0]
        dados_update = {}

        for coluna in colunas_editaveis:
            valor_base = linha_base.get(coluna)
            valor_editado = linha_editada.get(coluna)

            if coluna == "peso_embalagem":
                valor_base = _to_float(valor_base)
                valor_editado = _to_float(valor_editado)

            elif coluna == "ativo":
                valor_base = _to_bool(valor_base)
                valor_editado = _to_bool(valor_editado)

            else:
                valor_base = _to_str(valor_base).upper()
                valor_editado = _to_str(valor_editado).upper()

            if valor_base != valor_editado:
                dados_update[coluna] = valor_editado

        if dados_update:
            alteracoes.append({
                "id": item_id,
                "dados": dados_update,
            })

    if not alteracoes:
        st.info("Nenhuma alteração detectada.")
        return

    if st.button("💾 Salvar Alterações", use_container_width=True, key="btn_salvar_edicoes_embalagens"):
        try:
            total_ok = 0

            for item in alteracoes:
                conversa_banco.update(
                    "embalagens",
                    item["dados"],
                    {"id": item["id"]}
                )
                total_ok += 1

            if "editor_embalagens" in st.session_state:
                del st.session_state["editor_embalagens"]

            st.session_state["mensagem_sucesso_embalagem"] = (
                f"{total_ok} embalagem(ns) atualizada(s) no banco com sucesso."
            )
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar alterações no banco: {e}")


# ==========================================================
# APP
# ==========================================================
def app():
    if not usuario_admin():
        st.error("Acesso restrito")
        st.stop()

    st.title("⚙️ Parâmetros")

    if "limpar_form_embalagem" not in st.session_state:
        st.session_state["limpar_form_embalagem"] = False

    if "mensagem_sucesso_embalagem" not in st.session_state:
        st.session_state["mensagem_sucesso_embalagem"] = ""

    if "embalagem_codigo_validacao" not in st.session_state:
        st.session_state["embalagem_codigo_validacao"] = ""

    if "codigo_embalagem_form" not in st.session_state:
        st.session_state["codigo_embalagem_form"] = ""

    if "peso_embalagem_form" not in st.session_state:
        st.session_state["peso_embalagem_form"] = "0"

    if st.session_state["limpar_form_embalagem"]:
        st.session_state["embalagem_codigo_validacao"] = ""
        st.session_state["codigo_embalagem_form"] = ""
        st.session_state["peso_embalagem_form"] = "0"
        st.session_state["limpar_form_embalagem"] = False

    st.subheader("Cadastro Manual de Embalagens")

    if st.session_state["mensagem_sucesso_embalagem"]:
        st.success(st.session_state["mensagem_sucesso_embalagem"])
        st.session_state["mensagem_sucesso_embalagem"] = ""

    df_emb = conversa_banco.select("embalagens", order_by="codigo")

    codigo_validacao = st.text_input(
        "Digite o Código da Embalagem para validar",
        key="embalagem_codigo_validacao"
    )

    if codigo_validacao.strip():
        codigo_validado = codigo_validacao.strip().upper()

        if _codigo_embalagem_existe(codigo_validado, df_emb):
            st.error(f"O código {codigo_validado} já existe na tabela.")
        else:
            st.success(f"O código {codigo_validado} está disponível.")

            if st.session_state["codigo_embalagem_form"] != codigo_validado:
                st.session_state["codigo_embalagem_form"] = codigo_validado

    with st.form("form_embalagem", enter_to_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            codigo = st.text_input(
                "Código da Embalagem",
                key="codigo_embalagem_form"
            )

        with col2:
            peso_embalagem = st.text_input(
                "Peso da Embalagem",
                key="peso_embalagem_form"
            )

        salvar = st.form_submit_button("Salvar Embalagem")

        if salvar:
            codigo_normalizado = codigo.strip().upper()
            peso_embalagem_texto = str(peso_embalagem).strip()
            peso_embalagem_float = _to_float(peso_embalagem)

            erros = []

            if not codigo_normalizado:
                erros.append("Informe o Código da Embalagem.")

            if not peso_embalagem_texto:
                erros.append("Informe o Peso da Embalagem.")

            if erros:
                for erro in erros:
                    st.error(erro)

            elif _codigo_embalagem_existe(codigo_normalizado, df_emb):
                st.error(f"Não foi possível salvar. O código {codigo_normalizado} já existe.")

            else:
                try:
                    conversa_banco.insert(
                        "embalagens",
                        {
                            "codigo": codigo_normalizado,
                            "peso_embalagem": peso_embalagem_float,
                            "ativo": True,
                        }
                    )

                    st.session_state["mensagem_sucesso_embalagem"] = (
                        f"Embalagem {codigo_normalizado} cadastrada com sucesso."
                    )
                    st.session_state["limpar_form_embalagem"] = True
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao salvar embalagem: {e}")

    st.write("---")
    st.subheader("Importar CSV de Embalagens")

    st.info(
        "Formato obrigatório do início do CSV de embalagens:\n\n"
        "codigo,peso_embalagem,ativo\n\n"
        "Colunas extras depois disso são permitidas.\n"
        "Se o início do cabeçalho não bater, nada será importado."
    )

    arquivo_embalagens = st.file_uploader(
        "CSV de embalagens",
        type=["csv"],
        key="csv_embalagens"
    )

    if st.button("Importar Embalagens", key="btn_importar_embalagens"):
        if not arquivo_embalagens:
            st.error("Selecione um arquivo CSV de embalagens.")
        else:
            try:
                resultado = importar_embalagens_csv(arquivo_embalagens)
                st.session_state["mensagem_sucesso_embalagem"] = (
                    f"{resultado['mensagem']} Inseridos: {resultado['inseridos']} | "
                    f"Atualizados: {resultado['atualizados']} | "
                    f"Linhas válidas no arquivo: {resultado['total_linhas_validas']}"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Erro na importação: {e}")

    st.write("---")
    st.subheader("Lista de Embalagens")

    df = conversa_banco.select("embalagens", order_by="codigo")

    if not df.empty:
        for col in ["codigo", "peso_embalagem", "ativo"]:
            if col not in df.columns:
                if col == "peso_embalagem":
                    df[col] = 0.0
                elif col == "ativo":
                    df[col] = True
                else:
                    df[col] = ""

        df["codigo"] = df["codigo"].fillna("").astype(str).str.upper()
        df["peso_embalagem"] = pd.to_numeric(df["peso_embalagem"], errors="coerce").fillna(0.0)
        df["ativo"] = df["ativo"].apply(_to_bool)
        df = df.sort_values(by="codigo").reset_index(drop=True)

        busca_codigo = st.text_input("Buscar código da embalagem", key="busca_embalagem")

        df_f = df.copy()

        if busca_codigo.strip():
            termo = busca_codigo.strip().upper()
            df_f = df_f[df_f["codigo"].str.contains(termo, case=False, na=False)]

        colunas_editor = [
            "id",
            "codigo",
            "peso_embalagem",
            "ativo",
        ]

        df_editor = df_f[colunas_editor].copy()

        st.caption("Edite a tabela e clique em salvar. A alteração já vai para o banco.")

        df_editado = st.data_editor(
            df_editor,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_embalagens",
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "codigo": st.column_config.TextColumn("Código"),
                "peso_embalagem": st.column_config.NumberColumn("Peso da Embalagem", format="%.3f"),
                "ativo": st.column_config.CheckboxColumn("Ativo"),
            }
        )

        salvar_edicoes_embalagens(df_editor, df_editado)

        st.write("---")
        excluir_registros("embalagens", df_f, nome_item="cadastro de embalagem")

    else:
        st.warning("Sem embalagens cadastradas.")