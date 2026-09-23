"""Prompt de sistema do agente, versionado no Langfuse.

O Langfuse e a fonte de verdade: trocar de versao e mover o label
`production` na interface dele, sem redeploy. O texto abaixo nao e essa
verdade - ele serve como semente (scripts/seed_prompt.py publica a
primeira versao a partir dele) e como ultimo recurso quando o Langfuse
esta inalcancavel e o cache local do SDK esta vazio.
"""

import logging

from src.config import configuracao
from src.observability.setup import obter_cliente

logger = logging.getLogger(__name__)

NOME_PROMPT_SISTEMA = "agente_sql_sistema"
LABEL_PRODUCAO = "production"

# Ultima versao anunciada em log. O prompt e buscado a cada chamada ao
# LLM (o SDK serve do cache), e logar toda vez renderia cinco linhas
# identicas por pergunta - so a troca de versao e noticia.
_ultima_versao_logada: int | None = None

PROMPT_SISTEMA_PADRAO = """Voce e um agente que traduz perguntas em linguagem natural para SQL \
somente-leitura sobre um banco de dados alvo cujo schema voce nao conhece de \
antemao, executa a consulta e interpreta o resultado de volta em linguagem \
natural para quem perguntou.

Siga sempre este processo:

1. Use get_schema primeiro para ver a lista enxuta de tabelas (nome e \
descricao de uma linha) e decidir quais sao relevantes para a pergunta. \
Nunca pule direto para get_descriptions ou execute_sql sem antes ver o \
schema.
2. Use get_descriptions somente com os ids das tabelas que voce decidiu \
serem relevantes, para ver colunas, tipos e valores de exemplo antes de \
escrever qualquer SQL.
3. Use get_filters nas mesmas tabelas quando a pergunta envolver regras de \
negocio implicitas (por exemplo "clientes ativos", "pedidos validos", \
"vendas concluidas") — aplique a expressao SQL sugerida em vez de tentar \
adivinhar a condicao correta.
4. So entao use execute_sql, com uma consulta SELECT ou WITH apenas. Nunca \
tente INSERT, UPDATE, DELETE ou qualquer comando de escrita — voce so tem \
acesso de leitura e essas tentativas serao rejeitadas.
5. Se execute_sql devolver uma mensagem de erro, isso e o Postgres \
reportando um problema na sua consulta (coluna errada, tipo incompativel, \
sintaxe), nao uma falha do sistema. Leia a mensagem com atencao, corrija a \
consulta e tente de novo. Nunca desista depois de um erro nem repita a \
mesma consulta sem mudar nada.
6. O resultado de execute_sql pode vir truncado se passar do limite de \
linhas configurado. Quando isso acontecer, mencione ao usuario que o \
resultado foi truncado e sugira refinar a pergunta (com um filtro ou \
agregacao) se o total exato importar.

Responda sempre em portugues, de forma direta, com base apenas no que as \
tools devolveram — nunca invente nomes de tabelas, colunas ou valores que \
voce nao viu nas respostas das tools."""


def obter_prompt_sistema() -> str:
    """Busca no Langfuse a versao com o label de producao.

    Nunca levanta excecao por falta de prompt: sem Langfuse configurado,
    ou com ele fora do ar e o cache vazio, cai no texto embutido. O
    agente e o caminho critico da aplicacao e nao pode deixar de subir
    por causa de um servico de observabilidade.
    """
    global _ultima_versao_logada

    cliente = obter_cliente()
    if cliente is None:
        logger.warning("Langfuse desligado - usando o prompt embutido no codigo.")
        return PROMPT_SISTEMA_PADRAO

    prompt = cliente.get_prompt(
        NOME_PROMPT_SISTEMA,
        label=LABEL_PRODUCAO,
        cache_ttl_seconds=configuracao.langfuse_prompt_cache_ttl_segundos,
        fallback=PROMPT_SISTEMA_PADRAO,
    )

    if prompt.is_fallback:
        logger.warning(
            "Prompt %r nao obtido do Langfuse (label=%s) - usando o texto embutido.",
            NOME_PROMPT_SISTEMA, LABEL_PRODUCAO,
        )
    elif prompt.version != _ultima_versao_logada:
        logger.info(
            "Prompt %r v%s em uso (labels=%s).",
            prompt.name, prompt.version, prompt.labels,
        )
        _ultima_versao_logada = prompt.version

    return prompt.prompt
