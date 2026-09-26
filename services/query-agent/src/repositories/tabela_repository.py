"""Consultas e escritas sobre o catalogo de tabelas do banco alvo."""

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.models.tabela import Tabela
from src.log_stdout import logar_chamada


@logar_chamada
def buscar_por_id(sessao: Session, tabela_id: int) -> Tabela | None:
    return sessao.scalars(select(Tabela).where(Tabela.id == tabela_id)).one_or_none()


@logar_chamada
def buscar_por_identidade(
    sessao: Session, banco_id: int, schema_name: str, nome: str
) -> Tabela | None:
    # Usa a unique constraint (banco_id, schema_name, nome): upsert
    # idempotente ao popular o catalogo.
    return sessao.scalars(
        select(Tabela).where(
            Tabela.banco_id == banco_id,
            Tabela.schema_name == schema_name,
            Tabela.nome == nome,
        )
    ).one_or_none()


@logar_chamada
def listar_resumo_por_banco(
    sessao: Session, banco_id: int, dominio: str | None = None
) -> Sequence[Tabela]:
    # Leitura leve para get_schema: so o suficiente pro agente decidir
    # relevancia, sem carregar colunas/filtros.
    consulta = select(Tabela).where(Tabela.banco_id == banco_id, Tabela.ativo.is_(True))
    if dominio is not None:
        consulta = consulta.where(Tabela.dominio == dominio)
    return sessao.scalars(consulta.order_by(Tabela.nome)).all()


@logar_chamada
def listar_detalhada_por_ids(sessao: Session, tabela_ids: list[int]) -> Sequence[Tabela]:
    # Leitura pesada para get_descriptions. Sem eager loading de
    # colunas: o service busca com coluna_repository.listar_ativas_por_tabelas
    # a parte, para nao acoplar este repository a criterio ad-hoc de
    # relationship.
    return sessao.scalars(
        select(Tabela).where(Tabela.id.in_(tabela_ids), Tabela.ativo.is_(True))
    ).all()


@logar_chamada
def criar(
    sessao: Session,
    banco_id: int,
    nome: str,
    schema_name: str,
    descricao: str,
    dominio: str | None = None,
) -> Tabela:
    tabela = Tabela(
        banco_id=banco_id,
        nome=nome,
        schema_name=schema_name,
        descricao=descricao,
        dominio=dominio,
    )
    sessao.add(tabela)
    # flush: colunas/filtros filhos sao criados na sequencia, mesma transacao.
    sessao.flush()
    return tabela


@logar_chamada
def atualizar_descricao(sessao: Session, tabela_id: int, descricao: str) -> Tabela | None:
    tabela = buscar_por_id(sessao, tabela_id)
    if tabela is None:
        return None
    tabela.descricao = descricao
    return tabela


@logar_chamada
def atualizar_dominio(sessao: Session, tabela_id: int, dominio: str | None) -> Tabela | None:
    # Setter dedicado: dominio e anulavel, None aqui e valor valido.
    tabela = buscar_por_id(sessao, tabela_id)
    if tabela is None:
        return None
    tabela.dominio = dominio
    return tabela


@logar_chamada
def desativar_ausentes(
    sessao: Session, banco_id: int, nomes_qualificados_presentes: list[str]
) -> None:
    # UPDATE em massa (sem carregar linhas): marca ativo=False nas
    # tabelas do banco cujo "schema.nome" nao esta mais no schema real,
    # ao ressincronizar o catalogo. Concatena no SQL para nao precisar
    # trazer as linhas so pra comparar nome_qualificado em Python.
    qualificado = func.concat(Tabela.schema_name, ".", Tabela.nome)
    sessao.execute(
        update(Tabela)
        .where(
            Tabela.banco_id == banco_id,
            Tabela.ativo.is_(True),
            qualificado.not_in(nomes_qualificados_presentes),
        )
        .values(ativo=False)
    )


@logar_chamada
def ativar(sessao: Session, tabela_id: int) -> None:
    sessao.execute(update(Tabela).where(Tabela.id == tabela_id).values(ativo=True))


@logar_chamada
def desativar(sessao: Session, tabela_id: int) -> None:
    sessao.execute(update(Tabela).where(Tabela.id == tabela_id).values(ativo=False))
