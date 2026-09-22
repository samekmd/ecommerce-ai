"""Pagina Streamlit: visualizacao da tabela de logs do app_db.

So para diagnostico - somente leitura (logs sao append-only, log_repository
nao tem nenhuma funcao de escrita alem de registrar).
"""

import pandas as pd
import streamlit as st

from src.database.database import sessao_app
from src.logging_config import configurar_logging
from src.repositories import log_repository

configurar_logging()
st.set_page_config(page_title="Logs do agente", page_icon="📋")
st.title("Logs do agente")


def _carregar_logs(limite: int) -> pd.DataFrame:
    with sessao_app() as sessao:
        logs = log_repository.listar_recentes(sessao, limite=limite)
    return pd.DataFrame([
        {
            "id": log.id,
            "criado_em": log.criado_em,
            "thread_id": log.thread_id,
            "tool_name": log.tool_name,
            "sucesso": log.sucesso,
            "duracao_ms": log.duracao_ms,
            "linhas_retornadas": log.linhas_retornadas,
            "pergunta": log.pergunta,
            "erro": log.erro,
            "query_executada": log.query_executada,
            "argumentos": log.argumentos,
        }
        for log in logs
    ])


with st.sidebar:
    st.subheader("Filtros")
    limite = st.number_input(
        "Buscar as N mais recentes", min_value=10, max_value=5000, value=500, step=50
    )
    if st.button("Atualizar"):
        st.rerun()

df = _carregar_logs(limite)

if df.empty:
    st.info("Nenhum log encontrado ainda.")
else:
    with st.sidebar:
        tools = sorted(df["tool_name"].dropna().unique())
        tools_selecionadas = st.multiselect("Tool", tools, default=tools)
        so_falhas = st.checkbox("So falhas")
        thread_busca = st.text_input("thread_id contem")
        texto_busca = st.text_input("Buscar em pergunta/erro/query")

    filtrado = df[df["tool_name"].isin(tools_selecionadas)]
    if so_falhas:
        filtrado = filtrado[~filtrado["sucesso"]]
    if thread_busca:
        filtrado = filtrado[filtrado["thread_id"].str.contains(thread_busca, case=False, na=False)]
    if texto_busca:
        mascara = (
            filtrado["pergunta"].str.contains(texto_busca, case=False, na=False)
            | filtrado["erro"].str.contains(texto_busca, case=False, na=False)
            | filtrado["query_executada"].str.contains(texto_busca, case=False, na=False)
        )
        filtrado = filtrado[mascara]

    st.caption(f"{len(filtrado)} de {len(df)} logs carregados (limite de busca: {limite})")
    st.dataframe(filtrado, width="stretch", hide_index=True)
