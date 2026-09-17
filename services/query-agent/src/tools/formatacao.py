"""Traducao de ResultadoX (services) para texto legivel pelo LLM.

Nao chamado por services - so pelos arquivos de *_tool.py, depois que a
tool ja tem o dataclass de retorno em maos.
"""

from src.database.executor import ResultadoConsulta
from src.services.tipos import ResultadoDescricoes, ResultadoFiltros, ResultadoSchema


def _aviso_nao_encontrados(ids: list[int]) -> str:
    if not ids:
        return ""
    lista = ", ".join(str(i) for i in ids)
    return f"\nAtencao: os ids [{lista}] nao foram encontrados neste banco."


def formatar_schema(resultado: ResultadoSchema) -> str:
    if not resultado.sucesso:
        return f"Erro: {resultado.erro}"
    if not resultado.tabelas:
        return "Nenhuma tabela encontrada para este banco."
    linhas = [f"[{t.id}] {t.nome_qualificado} - {t.descricao}" for t in resultado.tabelas]
    return "Tabelas disponiveis:\n\n" + "\n".join(linhas)


def _formatar_coluna(coluna) -> str:
    partes = [coluna.tipo]
    if coluna.is_pk:
        partes.append("PK")
    if coluna.is_fk:
        partes.append(f"FK -> {coluna.referencia}" if coluna.referencia else "FK")
    if coluna.nullable:
        partes.append("aceita nulo")
    linha = f"  - {coluna.nome}: {', '.join(partes)}"
    if coluna.descricao:
        linha += f" - {coluna.descricao}"
    if coluna.valores_exemplo:
        linha += f" - exemplos: {', '.join(coluna.valores_exemplo)}"
    return linha


def formatar_descricoes(resultado: ResultadoDescricoes) -> str:
    if not resultado.sucesso:
        return f"Erro: {resultado.erro}"

    if not resultado.tabelas:
        base = "Nenhuma tabela encontrada."
    else:
        blocos = []
        for tabela in resultado.tabelas:
            cabecalho = f"Tabela [{tabela.id}] {tabela.nome_qualificado}"
            if tabela.dominio:
                cabecalho += f" (dominio: {tabela.dominio})"
            colunas_ordenadas = sorted(
                tabela.colunas, key=lambda c: (c.ordem is None, c.ordem)
            )
            linhas = [cabecalho, tabela.descricao, "Colunas:"]
            linhas.extend(_formatar_coluna(c) for c in colunas_ordenadas)
            blocos.append("\n".join(linhas))
        base = "\n\n".join(blocos)

    return base + _aviso_nao_encontrados(resultado.ids_nao_encontrados)


def formatar_filtros(resultado: ResultadoFiltros) -> str:
    if not resultado.sucesso:
        return f"Erro: {resultado.erro}"

    if not resultado.filtros:
        base = "Nenhum filtro encontrado para estas tabelas."
    else:
        blocos = [
            f"[{f.id}] {f.nome} (tabela {f.tabela_id})\n"
            f"  {f.descricao}\n"
            f"  SQL: {f.expressao_sql}\n"
            f"  Quando usar: {f.quando_usar}"
            for f in resultado.filtros
        ]
        base = "Filtros disponiveis:\n\n" + "\n\n".join(blocos)

    return base + _aviso_nao_encontrados(resultado.ids_nao_encontrados)


def formatar_consulta(resultado: ResultadoConsulta) -> str:
    if not resultado.sucesso:
        return f"Erro ao executar a consulta: {resultado.erro}\nSQL: {resultado.sql}"

    cabecalho = (
        f"Consulta executada com sucesso "
        f"({resultado.total_linhas} linhas, {resultado.duracao_ms}ms)."
    )
    if resultado.linhas:
        colunas = f"Colunas: {', '.join(resultado.colunas)}"
        linhas_texto = [
            f"{i}. " + ", ".join(f"{chave}={valor}" for chave, valor in linha.items())
            for i, linha in enumerate(resultado.linhas, start=1)
        ]
        texto = f"{cabecalho}\n{colunas}\n\n" + "\n".join(linhas_texto)
    else:
        texto = cabecalho

    if resultado.truncado:
        texto += (
            f"\n\nAviso: resultado truncado em {resultado.total_linhas} linhas; "
            "refine a consulta (WHERE/LIMIT) se precisar do total exato."
        )
    return texto
