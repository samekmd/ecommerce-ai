"""Configuracao central de logging, console/stdout apenas.

Chamada uma unica vez por processo (app.py, scripts/). Nenhum modulo de
tools/services/repositories/database chama isso - eles so pedem
logging.getLogger(__name__) e assumem que o processo ja configurou.
"""

import logging

from src.config import configuracao


def configurar_logging() -> None:
    logging.basicConfig(
        level=configuracao.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # vence handler que uma dependencia (Streamlit) ja tenha anexado ao root
    )
