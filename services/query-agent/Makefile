.PHONY: run avaliar

run:
	uv run streamlit run app.py

# Roda o dataset de regressao contra o agente. O PYTHONPATH=. e obrigatorio:
# ao executar um arquivo dentro de scripts/, o Python coloca scripts/ no inicio
# do sys.path em vez da raiz, e os imports de src/ e scripts/ falham.
#
# Uso:
#   make avaliar                                     # os 9 itens, nome automatico
#   make avaliar ITENS=v0-contagem-categorias        # um item, poupa cota
#   make avaliar NOME="prompt v2"                    # nomeia o run
avaliar:
	PYTHONPATH=. uv run python scripts/rodar_experimento.py \
		$(if $(ITENS),--itens $(ITENS)) $(if $(NOME),--nome "$(NOME)")
