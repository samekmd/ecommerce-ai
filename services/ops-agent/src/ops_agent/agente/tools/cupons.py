import re

from pydantic_ai import RunContext

from ops_agent.agente.deps import DependenciasAgente
from ops_agent.repositories import cupom as cupom_repository
from ops_agent.schemas.cupom import PADRAO_CODIGO_CUPOM, VerificacaoCodigoCupom, normalizar_codigo


async def verificar_codigo_cupom(
    ctx: RunContext[DependenciasAgente], codigo: str
) -> VerificacaoCodigoCupom:
    """Normaliza o codigo do cupom (maiusculas) e verifica formato e se ja existe.

    Use sempre que a frase trouxer um codigo de cupom. Proponha o codigo normalizado.
    existe=true: avise que o codigo ja esta em uso e peca outro. formato_valido=false:
    avise que o codigo deve ter de 3 a 30 caracteres entre letras, numeros, "-" e "_".

    Args:
        codigo: Codigo do cupom como citado pelo usuario (ex.: "black10").
    """
    normalizado = str(normalizar_codigo(codigo))
    if not re.fullmatch(PADRAO_CODIGO_CUPOM, normalizado):
        # Formato invalido nunca sera gravado: nao ha por que consultar o banco.
        return VerificacaoCodigoCupom(codigo=normalizado, formato_valido=False, existe=False)

    async with ctx.deps.abrir_sessao() as sessao:
        existe = await cupom_repository.existe_codigo(sessao, normalizado)
    return VerificacaoCodigoCupom(codigo=normalizado, formato_valido=True, existe=existe)
