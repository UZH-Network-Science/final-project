.PHONY: install setup clean

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Checking for Python 3.14 compatibility issues..."
	python3 scripts/patch_networkx.py
	@echo "Configuring notebook stripping..."
	nbstripout --install
	@echo "Setup complete! Notebooks will be automatically stripped on commit."

setup: install


