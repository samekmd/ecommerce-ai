from datetime import date

import pytest

from ops_agent.agente.deps import DependenciasAgente
from tests.conftest import rodar  # noqa: F401  (reexportado para os testes do agente)


@pytest.fixture
def deps() -> DependenciasAgente:
    return DependenciasAgente(usuario="teste", hoje=date(2026, 9, 28), max_fornecedores=3)
