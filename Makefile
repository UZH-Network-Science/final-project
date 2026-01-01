.PHONY: install setup clean hydrate docs

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Checking for Python 3.14 compatibility issues..."
	python3 scripts/patch_networkx.py
	@echo "Configuring pre-commit hooks (strips output & kernel metadata)..."
	pre-commit install
	@echo "Setup complete! Notebooks will be automatically stripped on commit."

setup: install


process:
	@echo "Running data processing pipelines..."
	python3 -m src.processing.run
	@echo "Data processing complete."

NOTEBOOKS := $(shell find docs -name "*.ipynb" -type f)

hydrate:
	@for notebook in $(NOTEBOOKS); do \
		echo "Hydrating $$notebook..."; \
		CI=true papermill "$$notebook" "$$notebook" --kernel python3 --cwd "$$(dirname $$notebook)"; \
	done

docs: hydrate
	@echo "Building docs..."
	mkdocs build
