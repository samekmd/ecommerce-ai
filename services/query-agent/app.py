"""Interface Streamlit de teste manual do agente Text-to-SQL.

So para testes exploratorios - tool calls aparecem em blocos st.status
colapsaveis, e sem tratamento de multiplos usuarios concorrentes alem
do isolamento natural por thread_id.
"""

import uuid

import streamlit as st
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from src.config import FORMATO_CHAVE_CONEXAO, configuracao
from src.database.database import sessao_app
from src.graph import PromptNaoConfigurado, grafo
from src.logging_config import configurar_logging
from src.repositories import banco_repository
from src.tools.contexto import ContextoInvalido

configurar_logging()

st.set_page_config(page_title="Agente Text-to-SQL (teste)", page_icon="🧪")


def _listar_bancos() -> list:
    with sessao_app() as sessao:
        return list(banco_repository.listar_ativos(sessao))


def _cadastrar_banco(nome: str, chave_conexao: str) -> str | None:
    """Cria o banco; devolve mensagem de erro ou None se deu certo."""
    if not nome.strip():
        return "Nome nao pode ser vazio."
    if not FORMATO_CHAVE_CONEXAO.match(chave_conexao.strip()):
        return "chave_conexao deve casar com TARGET_DB_[A-Z0-9_]+ (maiusculas)."
    with sessao_app() as sessao:
        banco_repository.criar(sessao, nome=nome.strip(), chave_conexao=chave_conexao.strip())
    return None


def _renderizar_tool_call(tool_call: dict) -> object:
    """Abre um st.status para uma chamada de tool; devolve o status para
    ser fechado depois com o resultado."""
    rotulo = f"🔧 {tool_call['name']}({tool_call['args']})"
    return st.status(rotulo, state="running")


def _renderizar_resultado_tool(status: object, tool_message: ToolMessage, tool_call: dict) -> None:
    status.update(label=f"🔧 {tool_call['name']}", state="complete")
    with status:
        st.code(tool_message.content, language=None)


def _renderizar_historico(config: dict) -> None:
    """Redesenha a conversa inteira a partir do checkpoint - incluindo
    tool calls e seus resultados, sem filtro."""
    mensagens = grafo.get_state(config).values.get("messages", [])
    tool_calls_pendentes: dict[str, dict] = {}
    status_por_id: dict[str, object] = {}

    for m in mensagens:
        if isinstance(m, HumanMessage):
            st.chat_message("user").write(m.content)
        elif isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                tool_calls_pendentes[tc["id"]] = tc
                status_por_id[tc["id"]] = _renderizar_tool_call(tc)
        elif isinstance(m, ToolMessage):
            tc = tool_calls_pendentes.get(m.tool_call_id)
            status = status_por_id.get(m.tool_call_id)
            if tc and status:
                _renderizar_resultado_tool(status, m, tc)
        elif isinstance(m, AIMessage):
            st.chat_message("assistant").write(m.content)


# --- estado de sessao ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# --- sidebar ---
with st.sidebar:
    st.subheader("Banco alvo")
    bancos = _listar_bancos()

    if bancos:
        opcoes = {f"{b.nome} ({b.chave_conexao})": b.id for b in bancos}
        escolha = st.selectbox("Banco cadastrado", list(opcoes.keys()))
        st.session_state.banco_id = opcoes[escolha]
    else:
        st.session_state.banco_id = None
        st.info("Nenhum banco cadastrado ainda.")

    with st.expander("Cadastrar novo banco", expanded=not bancos):
        nome = st.text_input("Nome")
        chave = st.text_input("chave_conexao", placeholder="TARGET_DB_LOJA")
        if st.button("Cadastrar"):
            erro = _cadastrar_banco(nome, chave)
            if erro:
                st.error(erro)
            else:
                st.success("Banco cadastrado.")
                st.rerun()

    st.divider()
    st.caption(f"thread_id: {st.session_state.thread_id}")
    if st.button("Nova conversa"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption("Diagnostico")
    st.caption(f"ambiente: {configuracao.ambiente}")
    st.caption(f"modelo: {configuracao.groq_model}")
    st.caption(f"GROQ_API_KEY definida: {'sim' if configuracao.groq_api_key else 'nao'}")

# --- area principal ---
st.title("Agente Text-to-SQL (teste)")

config = {
    "configurable": {
        "thread_id": st.session_state.thread_id,
        "banco_id": st.session_state.banco_id,
    }
}

if st.session_state.banco_id is not None:
    _renderizar_historico(config)

pergunta = st.chat_input(
    "Pergunte algo sobre o banco selecionado...",
    disabled=st.session_state.banco_id is None,
)

if pergunta:
    st.chat_message("user").write(pergunta)

    status_por_id: dict[str, object] = {}
    tool_calls_por_id: dict[str, dict] = {}
    placeholder_texto = None
    buffer_texto = ""
    id_rodada_atual = None

    try:
        for chunk, _metadata in grafo.stream(
            {"messages": [HumanMessage(pergunta)]}, config=config, stream_mode="messages"
        ):
            if isinstance(chunk, ToolMessage):
                tc = tool_calls_por_id.get(chunk.tool_call_id)
                status = status_por_id.get(chunk.tool_call_id)
                if tc and status:
                    _renderizar_resultado_tool(status, chunk, tc)
                continue

            if isinstance(chunk, AIMessageChunk) and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    tool_calls_por_id[tc["id"]] = tc
                    status_por_id[tc["id"]] = _renderizar_tool_call(tc)
                continue

            if isinstance(chunk, AIMessageChunk) and chunk.content:
                if chunk.id != id_rodada_atual:
                    id_rodada_atual = chunk.id
                    buffer_texto = ""
                    placeholder_texto = st.chat_message("assistant").empty()
                buffer_texto += chunk.content
                placeholder_texto.markdown(buffer_texto)

    except PromptNaoConfigurado:
        st.error(
            "Nenhum prompt de sistema ativo. Rode "
            "`python scripts/seed_prompt.py` antes de usar o agente."
        )
    except ContextoInvalido as erro:
        st.error(f"Erro de configuracao interna: {erro}")
    except Exception as erro:  # ex.: erro de rede/API do Groq
        st.error(f"Erro ao chamar o agente: {erro}")
