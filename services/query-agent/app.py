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
from src.database.executor import FalhaDeInfraestrutura
from src.graph import PromptNaoConfigurado, grafo
from src.logging_config import configurar_logging
from src.observability import tracing
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


def _fechar_tool_calls_sem_resultado(
    status_por_id: dict[str, object],
    tool_calls_por_id: dict[str, dict],
    resolvidos: set[str],
) -> None:
    """Marca como nao executada toda tool call que nao recebeu ToolMessage.

    O LLM transmite o tool call pelo stream antes de o grafo decidir o
    que fazer com ele; se o grafo o descarta (teto de iteracoes) ou uma
    excecao interrompe o turno, o st.status ficaria girando para sempre,
    dando a impressao de query eternamente em processamento.
    """
    for id_tool_call, status in status_por_id.items():
        if id_tool_call in resolvidos:
            continue
        nome = tool_calls_por_id.get(id_tool_call, {}).get("name", "tool")
        status.update(label=f"🔧 {nome} - nao executada", state="error")


def _renderizar_historico(config: dict) -> None:
    """Redesenha a conversa inteira a partir do checkpoint - incluindo
    tool calls e seus resultados, sem filtro."""
    mensagens = grafo.get_state(config).values.get("messages", [])
    tool_calls_pendentes: dict[str, dict] = {}
    status_por_id: dict[str, object] = {}
    resolvidos: set[str] = set()

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
                resolvidos.add(m.tool_call_id)
        elif isinstance(m, AIMessage):
            st.chat_message("assistant").write(m.content)

    _fechar_tool_calls_sem_resultado(status_por_id, tool_calls_pendentes, resolvidos)


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

config = tracing.config_do_grafo(st.session_state.thread_id, st.session_state.banco_id)

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
    resolvidos: set[str] = set()
    placeholder_texto = None
    buffer_texto = ""
    id_rodada_atual = None
    # dict de 1 posicao em vez de variavel solta: script Streamlit roda no
    # escopo de modulo, onde "nonlocal" nao se aplica dentro da funcao
    # auxiliar abaixo - mutar uma chave de dict evita esse problema.
    acumulador = {"chunk": None}

    def _finalizar_tool_calls_pendentes() -> None:
        # Alguns modelos (ex.: cohere/north-mini-code) transmitem os
        # argumentos do tool call fatiados em varios chunks (JSON parcial
        # por chunk; chunk.tool_calls so fica correto depois de mesclar
        # todos os chunks da mesma rodada com o operador +). Renderizar
        # cada chunk individualmente cria tool calls fantasmas com
        # nome/id vazios - so renderiza quando a rodada termina.
        chunk_acumulado = acumulador["chunk"]
        if chunk_acumulado is not None:
            for tc in chunk_acumulado.tool_calls:
                if tc.get("id"):
                    tool_calls_por_id[tc["id"]] = tc
                    status_por_id[tc["id"]] = _renderizar_tool_call(tc)
        acumulador["chunk"] = None

    try:
        with st.spinner("Processando pergunta..."):
            for chunk, _metadata in grafo.stream(
                {"messages": [HumanMessage(pergunta)]}, config=config, stream_mode="messages"
            ):
                if isinstance(chunk, ToolMessage):
                    _finalizar_tool_calls_pendentes()
                    tc = tool_calls_por_id.get(chunk.tool_call_id)
                    status = status_por_id.get(chunk.tool_call_id)
                    if tc and status:
                        _renderizar_resultado_tool(status, chunk, tc)
                        resolvidos.add(chunk.tool_call_id)
                    continue

                if not isinstance(chunk, AIMessageChunk):
                    continue

                if chunk.id != id_rodada_atual:
                    _finalizar_tool_calls_pendentes()
                    id_rodada_atual = chunk.id
                    acumulador["chunk"] = chunk
                    buffer_texto = ""
                    placeholder_texto = None
                else:
                    acumulador["chunk"] = acumulador["chunk"] + chunk

                if chunk.content:
                    if placeholder_texto is None:
                        placeholder_texto = st.chat_message("assistant").empty()
                    buffer_texto += chunk.content
                    placeholder_texto.markdown(buffer_texto)

            _finalizar_tool_calls_pendentes()  # seguranca: fecha rodada pendente ao fim do stream

        # A mensagem que o grafo monta no lugar de uma resposta com
        # tool_calls descartados nao vem de chamada ao modelo, entao nao
        # passa pelo stream. Sem isto o turno termina sem texto nenhum.
        if not buffer_texto:
            mensagens = grafo.get_state(config).values.get("messages", [])
            if mensagens and isinstance(mensagens[-1], AIMessage) and mensagens[-1].content:
                st.chat_message("assistant").write(mensagens[-1].content)

    except PromptNaoConfigurado:
        st.error(
            "Nenhum prompt de sistema ativo. Rode "
            "`python scripts/seed_prompt.py` antes de usar o agente."
        )
    except ContextoInvalido as erro:
        st.error(f"Erro de configuracao interna: {erro}")
    except FalhaDeInfraestrutura as erro:
        st.error(
            f"Falha de infraestrutura no banco alvo: {erro}\n\n"
            "O agente nao tem como corrigir isso reescrevendo a consulta. "
            "Veja o log do terminal para o estado do pool de conexoes."
        )
    except Exception as erro:  # ex.: erro de rede/API do provedor de LLM
        st.error(f"Erro ao chamar o agente: {erro}")
    finally:
        _fechar_tool_calls_sem_resultado(status_por_id, tool_calls_por_id, resolvidos)
