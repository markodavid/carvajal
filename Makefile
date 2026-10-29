# =============================================================================
# Carvajal — automatización de tareas
# =============================================================================

SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help install dev pre-commit-install pre-commit lint format format-check typecheck test check build app eval clean

help: ## Muestra esta ayuda
	@echo Uso: make [objetivo]
	@echo Objetivos disponibles:
	@echo   help               Muestra esta ayuda
	@echo   install            Sincroniza el entorno e instala dependencias
	@echo   dev                Prepara el entorno de desarrollo (sync + hooks)
	@echo   pre-commit-install Instala los hooks de pre-commit
	@echo   pre-commit         Ejecuta los hooks sobre todos los archivos
	@echo   lint               Ejecuta Ruff (lint)
	@echo   format             Formatea el código con Ruff
	@echo   format-check       Verifica el formato sin modificarlo
	@echo   typecheck          Verifica los tipos con ty (Astral)
	@echo   test               Ejecuta las pruebas
	@echo   check              Verificación completa (lint + formato + tipos + pruebas)
	@echo   build              Construye el paquete (sdist + wheel)
	@echo   app                Lanza la interfaz web de prueba (Streamlit)
	@echo   eval               Ejecuta las preguntas de prueba (genera docs/resultados.md)
	@echo   clean              Limpia cachés y artefactos

install: ## Sincroniza el entorno virtual e instala dependencias
	uv sync

dev: install pre-commit-install ## Prepara el entorno de desarrollo (sync + hooks)

pre-commit-install: ## Instala los hooks de pre-commit en el repositorio local
	uv run pre-commit install

pre-commit: ## Ejecuta todos los hooks de pre-commit sobre el repositorio
	uv run pre-commit run --all-files

lint: ## Ejecuta Ruff (lint)
	uv run ruff check .

format: ## Formatea el código con Ruff
	uv run ruff format .

format-check: ## Verifica el formato sin modificarlo
	uv run ruff format --check .

typecheck: ## Verifica los tipos con ty (Astral)
	uv run ty check

test: ## Ejecuta las pruebas
	uv run pytest

check: lint format-check typecheck test ## Verificación completa (lint + formato + tipos + pruebas)

build: ## Construye el paquete (sdist + wheel)
	uv build

app: ## Lanza la interfaz web de prueba (Streamlit)
	uv run streamlit run app.py

eval: ## Ejecuta las preguntas de prueba y genera docs/resultados.md
	uv run carvajal eval

clean: ## Limpia cachés y artefactos
	uv run python -c "import shutil; from pathlib import Path; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache', 'dist', 'build', 'htmlcov']]; [shutil.rmtree(p, ignore_errors=True) for p in Path('.').rglob('__pycache__')]; Path('.coverage').unlink(missing_ok=True)"
