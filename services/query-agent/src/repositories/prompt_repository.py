"""Consultas e escritas sobre prompts versionados do agente."""

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.models.prompt import Prompt
from src.log_stdout import logar_chamada


@logar_chamada
def buscar_ativo(sessao: Session, chave: str) -> Prompt | None:
    # O indice unico parcial uq_prompts_um_ativo_por_chave garante no
    # maximo uma linha ativa por chave.
    return sessao.scalars(
        select(Prompt).where(Prompt.chave == chave, Prompt.ativo.is_(True))
    ).one_or_none()


@logar_chamada
def buscar_por_chave_e_versao(sessao: Session, chave: str, versao: int) -> Prompt | None:
    return sessao.scalars(
        select(Prompt).where(Prompt.chave == chave, Prompt.versao == versao)
    ).one_or_none()


@logar_chamada
def listar_versoes(sessao: Session, chave: str) -> Sequence[Prompt]:
    return sessao.scalars(
        select(Prompt).where(Prompt.chave == chave).order_by(Prompt.versao.desc())
    ).all()


@logar_chamada
def listar_chaves_ativas(sessao: Session) -> Sequence[Prompt]:
    return sessao.scalars(
        select(Prompt).where(Prompt.ativo.is_(True)).order_by(Prompt.chave)
    ).all()


@logar_chamada
def criar_versao(
    sessao: Session, chave: str, conteudo: str, descricao: str | None = None
) -> Prompt:
    # versao = max(versao existente) + 1, ou 1 se a chave e nova.
    # Sempre nasce inativa: precisa de ativar_versao() explicito.
    ultima_versao = sessao.scalar(
        select(func.max(Prompt.versao)).where(Prompt.chave == chave)
    )
    prompt = Prompt(
        chave=chave,
        conteudo=conteudo,
        descricao=descricao,
        versao=(ultima_versao or 0) + 1,
        ativo=False,
    )
    sessao.add(prompt)
    # flush: o uso tipico encadeia criar_versao() + ativar_versao() na
    # mesma transacao, ao promover um prompt novo direto para producao.
    sessao.flush()
    return prompt


@logar_chamada
def ativar_versao(sessao: Session, chave: str, versao: int) -> Prompt:
    """Troca a versao ativa de uma chave.

    Atomicidade vem de quem chama envolver esta funcao em sessao_app(),
    nao de controle de transacao aqui dentro.

    Atencao: com expire_on_commit=False e autoflush=False, se uma
    instancia de Prompt da mesma chave ja estiver carregada na sessao
    antes desta chamada (ex.: buscar_ativo() chamado antes no mesmo
    escopo), o UPDATE em massa abaixo nao atualiza o atributo .ativo em
    memoria dessa instancia - ela fica obsoleta ate um sessao.refresh()
    ou sessao.expire(). Evite chamar buscar_ativo() e ativar_versao() na
    mesma sessao sem um refresh() entre eles.
    """
    # UPDATE em massa: desativa a(s) linha(s) atualmente ativa(s) da
    # chave sem carrega-las em memoria.
    sessao.execute(
        update(Prompt)
        .where(Prompt.chave == chave, Prompt.ativo.is_(True))
        .values(ativo=False)
    )
    prompt = sessao.scalars(
        select(Prompt).where(Prompt.chave == chave, Prompt.versao == versao)
    ).one()
    prompt.ativo = True
    sessao.flush()
    return prompt
