import asyncio
import time

from fastapi import APIRouter

from ops_agent.agente import agente
from ops_agent.agente.prompts.sistema import obter_prompt_sistema
from ops_agent.api.dependencias import UsuarioAtual
from ops_agent.config import obter_configuracao
from ops_agent.observabilidade.tracing import rastrear_interpretacao
from ops_agent.schemas.interpretacao import (
    RequisicaoInterpretar,
    RespostaInterpretar,
    tipo_da_interpretacao,
)
from ops_agent.services import auditoria

router = APIRouter(tags=["interpretacao"])


@router.post("/interpretar", response_model=RespostaInterpretar)
async def interpretar(requisicao: RequisicaoInterpretar, usuario: UsuarioAtual) -> RespostaInterpretar:
    """Frase -> proposta para o formulario. Nada e gravado no banco de negocio."""
    inicio = time.perf_counter()
    # get_prompt do SDK e sincrono: num cache miss faria I/O de rede dentro
    # do event loop.
    prompt = await asyncio.to_thread(obter_prompt_sistema)

    async with rastrear_interpretacao(usuario, requisicao.mensagem, prompt) as rastro:
        registro = {
            "usuario": usuario,
            "mensagem": requisicao.mensagem,
            "modelo": obter_configuracao().ops_modelo,
            "trace_id": rastro.trace_id,
            "prompt_versao": prompt.versao,
        }
        try:
            saida = await agente.interpretar(requisicao.mensagem, usuario, prompt.texto)
        except Exception as erro:
            # Falha tambem e metrica: frase que o agente nao consegue interpretar.
            rastro.registrar_erro(auditoria.categoria_do_erro(erro))
            await auditoria.registrar_interpretacao(
                **registro, saida=None, erro=erro, duracao_ms=_ms_desde(inicio)
            )
            raise
        rastro.registrar_saida(saida)

    interpretacao_id = await auditoria.registrar_interpretacao(
        **registro, saida=saida, erro=None, duracao_ms=_ms_desde(inicio)
    )
    return RespostaInterpretar(
        interpretacao_id=interpretacao_id,
        tipo=tipo_da_interpretacao(saida),
        proposta=saida,
        avisos=getattr(saida, "avisos", []),
    )


def _ms_desde(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)
