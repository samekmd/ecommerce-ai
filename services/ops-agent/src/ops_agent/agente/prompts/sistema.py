"""Prompt de sistema do ops-agent, versionado no Langfuse.

O Langfuse e a fonte de verdade: trocar de versao e mover o label
`production` na interface dele, sem redeploy (com o atraso do cache do
SDK). O texto abaixo nao e essa verdade: e a semente que
scripts/seed_prompt.py publica num projeto novo e o ultimo recurso quando o
Langfuse esta desligado, fora do ar ou com o cache vazio.

Nao repete os schemas: os campos e suas descricoes chegam pelas output
tools. A data de hoje entra por instrucao dinamica em agente.py.
"""

import logging
from dataclasses import dataclass
from typing import Any

from ops_agent.config import obter_configuracao
from ops_agent.observabilidade.setup import obter_cliente

logger = logging.getLogger(__name__)

NOME_PROMPT_SISTEMA = "ops_agente_sistema"
LABEL_PRODUCAO = "production"

# Busca rapida: um cache miss acontece no caminho da requisicao, e o
# fallback e melhor que deixar o usuario esperando o Langfuse.
_TIMEOUT_BUSCA_SEGUNDOS = 5

# Ultima versao anunciada em log: o prompt e buscado a cada interpretacao
# (o SDK serve do cache), e so a troca de versao e noticia.
_ultima_versao_logada: int | None = None


PROMPT_SISTEMA_PADRAO = """\
Voce e o assistente de cadastro de uma loja de e-commerce. Voce recebe uma frase em portugues \
e PROPOE um cadastro estruturado; o usuario revisa e confirma num formulario. Voce nunca grava \
nada.

Entidades: produto, fornecedor, categoria e cupom. Uma entidade por mensagem.

Ferramentas, antes de preencher qualquer ID:
- listar_categorias antes de categoria_id (produto) ou categoria_pai_id (categoria).
- buscar_fornecedores antes de fornecedor_id.
- verificar_codigo_cupom sempre que houver codigo de cupom.
Use somente IDs devolvidos por essas ferramentas nesta conversa. Sem ID adequado: null e um aviso.

Nunca invente: IDs, CNPJ, SKU (o sistema gera) nem imagem (o usuario anexa). Campo ausente na \
frase fica null, com aviso dizendo o que falta.

Produto: "5 camisas" significa estoque 5 de UM produto. Preco por extenso vira numero \
("cem reais" -> 100.00). Escolha a categoria mais especifica que encaixar; nunca crie categoria \
implicitamente.

Cupom: somente desconto percentual. Desconto em reais ("R$ 20 de desconto") nao e suportado: \
responda com pedir_esclarecimento (motivo nao_suportado), nunca converta para percentual. Datas \
relativas ("ate o fim do mes") sao calculadas a partir da data de hoje.

Responda com pedir_esclarecimento quando:
- faltar informacao para saber qual entidade cadastrar (motivo ambiguo);
- o pedido for editar, excluir ou desativar algo (motivo nao_suportado);
- o pedido citar mais de uma entidade para cadastrar (motivo nao_suportado);
- o assunto nao for cadastro de produto, fornecedor, categoria ou cupom, como clientes ou \
pedidos (motivo fora_do_escopo).

Avisos: frases curtas em portugues, uma por ponto que o usuario precisa conferir ou completar.
"""


@dataclass(frozen=True)
class PromptSistema:
    texto: str
    # None quando o texto e o embutido: nao ha versao no Langfuse a atribuir.
    versao: int | None = None
    # TextPromptClient do SDK, propagado ao trace para ligar a generation.
    cliente: Any | None = None


PROMPT_EMBUTIDO = PromptSistema(texto=PROMPT_SISTEMA_PADRAO)


def obter_prompt_sistema() -> PromptSistema:
    """Versao com o label de producao, ou o texto embutido.

    Nunca levanta: o agente nao pode deixar de responder por causa do
    servico de observabilidade. Sincrono (o SDK e sincrono); a rota chama
    em thread para nao bloquear o event loop num cache miss.
    """
    global _ultima_versao_logada

    cliente = obter_cliente()
    if cliente is None:
        return PROMPT_EMBUTIDO

    try:
        prompt = cliente.get_prompt(
            NOME_PROMPT_SISTEMA,
            label=LABEL_PRODUCAO,
            cache_ttl_seconds=obter_configuracao().langfuse_prompt_cache_ttl_segundos,
            fallback=PROMPT_SISTEMA_PADRAO,
            fetch_timeout_seconds=_TIMEOUT_BUSCA_SEGUNDOS,
            max_retries=1,
        )
    except Exception:
        logger.exception("Falha ao buscar o prompt %r; usando o texto embutido.", NOME_PROMPT_SISTEMA)
        return PROMPT_EMBUTIDO

    if prompt.is_fallback:
        logger.warning(
            "Prompt %r nao obtido do Langfuse (label=%s) - usando o texto embutido.",
            NOME_PROMPT_SISTEMA, LABEL_PRODUCAO,
        )
        return PROMPT_EMBUTIDO

    if prompt.version != _ultima_versao_logada:
        logger.info("Prompt %r v%s em uso (labels=%s).", prompt.name, prompt.version, prompt.labels)
        _ultima_versao_logada = prompt.version

    return PromptSistema(texto=prompt.prompt, versao=prompt.version, cliente=prompt)
