"""Contrato de saida das services: o que cada tool devolve ao LLM.

execute_sql nao ganha dataclass aqui: reaproveita
src.database.executor.ResultadoConsulta diretamente, para a tool tratar
banco invalido e SQL invalido com o mesmo shape.

Convencao: erro e reservado para falha de pre-condicao (banco, quantidade
de tabelas). Item individual ausente numa lista nunca vira erro, sempre
ids_nao_encontrados - o resto da resposta segue com sucesso=True.
"""

from dataclasses import dataclass, field


@dataclass
class TabelaResumo:
    id: int
    nome_qualificado: str
    descricao: str


@dataclass
class ResultadoSchema:
    sucesso: bool
    tabelas: list[TabelaResumo] = field(default_factory=list)
    erro: str | None = None


@dataclass
class ColunaDetalhe:
    id: int
    nome: str
    tipo: str
    descricao: str | None
    is_pk: bool
    is_fk: bool
    referencia: str | None
    valores_exemplo: list[str] | None
    nullable: bool
    ordem: int | None


@dataclass
class TabelaDetalhada:
    id: int
    nome_qualificado: str
    descricao: str
    dominio: str | None
    colunas: list[ColunaDetalhe] = field(default_factory=list)


@dataclass
class ResultadoDescricoes:
    sucesso: bool
    tabelas: list[TabelaDetalhada] = field(default_factory=list)
    ids_nao_encontrados: list[int] = field(default_factory=list)
    erro: str | None = None


@dataclass
class FiltroDetalhe:
    id: int
    tabela_id: int
    nome: str
    descricao: str
    expressao_sql: str
    quando_usar: str


@dataclass
class ResultadoFiltros:
    sucesso: bool
    filtros: list[FiltroDetalhe] = field(default_factory=list)
    ids_nao_encontrados: list[int] = field(default_factory=list)
    erro: str | None = None
