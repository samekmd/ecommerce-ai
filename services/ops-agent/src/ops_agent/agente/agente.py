"""Agente de cadastro: frase -> Interpretacao (proposta ou pedido de esclarecimento).

O Agent e criado sem modelo: modelo, retries, settings e limites vem do
config a cada run. Importar este modulo nao exige .env, e os testes trocam
o modelo por FunctionModel.
"""

from functools import lru_cache

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.output import ToolOutput
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from ops_agent.agente.deps import DependenciasAgente, criar_dependencias
from ops_agent.agente.prompts.sistema import PROMPT_SISTEMA_PADRAO
from ops_agent.agente.tools import TOOLS
from ops_agent.config import obter_configuracao
from ops_agent.schemas.categoria import CategoriaProposta
from ops_agent.schemas.cupom import CupomProposta, normalizar_codigo
from ops_agent.schemas.fornecedor import FornecedorProposta
from ops_agent.schemas.interpretacao import Interpretacao, PedidoEsclarecimento
from ops_agent.schemas.produto import ProdutoProposta

# Tabela propria: strftime("%A") depende do locale do SO.
_DIAS_DA_SEMANA = (
    "segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado",
    "domingo",
)

# Uma output tool por tipo: o tipo escolhido e a intencao. Nomes em
# portugues ajudam modelos menores a escolher; texto livre fica desabilitado.
agente = Agent(
    output_type=[
        ToolOutput(ProdutoProposta, name="propor_produto", description="Propor cadastro de produto."),
        ToolOutput(
            FornecedorProposta, name="propor_fornecedor", description="Propor cadastro de fornecedor."
        ),
        ToolOutput(
            CategoriaProposta,
            name="propor_categoria",
            description="Propor cadastro de categoria nova (pedido explicito do usuario).",
        ),
        ToolOutput(
            CupomProposta, name="propor_cupom", description="Propor cadastro de cupom percentual."
        ),
        ToolOutput(
            PedidoEsclarecimento,
            name="pedir_esclarecimento",
            description="Quando nao for possivel propor: ambiguo, nao suportado ou fora do escopo.",
        ),
    ],
    deps_type=DependenciasAgente,
    tools=TOOLS,
    name="ops-agent",
)


# Registrada antes de data_de_hoje: as instrucoes seguem a ordem de registro.
@agente.instructions
def prompt_sistema(ctx: RunContext[DependenciasAgente]) -> str:
    """Versao do Langfuse escolhida para esta execucao (ou o texto embutido)."""
    return ctx.deps.prompt_sistema


@agente.instructions
def data_de_hoje(ctx: RunContext[DependenciasAgente]) -> str:
    hoje = ctx.deps.hoje
    return (
        f"Hoje e {_DIAS_DA_SEMANA[hoje.weekday()]}, {hoje:%d/%m/%Y} ({hoje.isoformat()}). "
        "Use esta data para datas relativas e como inicio padrao de cupom."
    )


def _checar_id(valor: int | None, vistos: set[int], campo: str, tool: str) -> None:
    """ModelRetry se o ID nao veio de nenhuma tool nesta execucao.

    Defesa contra ID alucinado: sem isso, um categoria_id inventado so
    seria pego no formulario, ou pior, apontaria para a categoria errada.
    """
    if valor is None or valor in vistos:
        return
    if not vistos:
        raise ModelRetry(
            f"{campo}={valor} nao veio de nenhuma ferramenta. Chame {tool} primeiro e use um "
            "ID devolvido por ela, ou deixe null com um aviso."
        )
    validos = ", ".join(str(i) for i in sorted(vistos))
    raise ModelRetry(
        f"{campo}={valor} nao foi devolvido por {tool}. IDs validos: {validos}. "
        "Use um deles ou deixe null com um aviso."
    )


@agente.output_validator
async def validar_saida(
    ctx: RunContext[DependenciasAgente], saida: Interpretacao
) -> Interpretacao:
    deps = ctx.deps

    if isinstance(saida, ProdutoProposta):
        _checar_id(saida.categoria_id, deps.categorias_vistas, "categoria_id", "listar_categorias")
        _checar_id(
            saida.fornecedor_id, deps.fornecedores_vistos, "fornecedor_id", "buscar_fornecedores"
        )

    elif isinstance(saida, CategoriaProposta):
        _checar_id(
            saida.categoria_pai_id, deps.categorias_vistas, "categoria_pai_id", "listar_categorias"
        )

    elif isinstance(saida, CupomProposta):
        # Regras deterministicas nao ficam a cargo do LLM.
        inicio = saida.validade_inicio or deps.hoje
        if saida.validade_fim is not None and saida.validade_fim < inicio:
            raise ModelRetry(
                f"validade_fim ({saida.validade_fim}) anterior a validade_inicio ({inicio}). "
                "Recalcule a partir da data de hoje."
            )
        codigo = normalizar_codigo(saida.codigo) if saida.codigo else None
        saida = saida.model_copy(update={"validade_inicio": inicio, "codigo": codigo})

    return saida


@lru_cache(maxsize=1)
def obter_modelo() -> Model:
    """Groq como principal; OpenRouter como fallback quando configurado.

    O FallbackModel so troca de provedor em erro de API (HTTP 4xx/5xx,
    conexao, timeout). Tool call invalida nao e erro de API: continua nos
    retries do mesmo modelo, que e onde o validador de saida atua.
    Chaves passadas explicitamente: sem elas os providers leriam
    GROQ_API_KEY/OPENROUTER_API_KEY do ambiente, e config.py deixaria de
    ser o unico leitor.
    """
    configuracao = obter_configuracao()
    principal = GroqModel(
        configuracao.ops_modelo_groq,
        provider=GroqProvider(api_key=configuracao.groq_api_key.get_secret_value()),
    )
    if configuracao.ops_modelo_openrouter is None:
        return principal
    reserva = OpenRouterModel(
        configuracao.ops_modelo_openrouter,
        provider=OpenRouterProvider(api_key=configuracao.openrouter_api_key.get_secret_value()),
    )
    return FallbackModel(principal, reserva)


async def interpretar(
    mensagem: str, usuario: str, prompt_sistema: str = PROMPT_SISTEMA_PADRAO
) -> Interpretacao:
    """Uma frase, uma proposta. Stateless: deps novas a cada chamada.

    Excecoes do Pydantic AI (retries esgotados, limite de uso) e de rede
    sobem para a camada api/, que audita e decide o status HTTP.
    """
    configuracao = obter_configuracao()
    resultado = await agente.run(
        mensagem,
        deps=criar_dependencias(usuario, prompt_sistema),
        model=obter_modelo(),
        model_settings=ModelSettings(
            temperature=configuracao.ops_temperatura,
            max_tokens=configuracao.ops_max_tokens,
            timeout=configuracao.ops_timeout_llm_segundos,
        ),
        retries=configuracao.ops_retries_saida,
        usage_limits=UsageLimits(request_limit=configuracao.ops_limite_requisicoes),
    )
    return resultado.output
