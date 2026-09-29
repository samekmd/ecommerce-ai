.PHONY: api

# Porta padrao 8001: a 8000 e da api do query-agent.
PORTA ?= 8001

# Sobe a API do ops-agent com reload. --factory porque main.py nao cria
# app no import: criar_app() carrega e valida o config na subida.
#
# Uso:
#   make api              # http://localhost:8001 (docs em /docs)
#   make api PORTA=8010
api:
	uv run --package ops-agent uvicorn ops_agent.main:criar_app --factory --reload --port $(PORTA)
