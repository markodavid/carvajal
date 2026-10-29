# Carvajal — Corpus Web

[![CI](https://github.com/markodavid/carvajal/actions/workflows/ci.yml/badge.svg)](https://github.com/markodavid/carvajal/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Pipeline de captura y curaduría del corpus web de **Carvajal** para RAG.

## Descripción

Convertir las páginas públicas del sitio web de Carvajal en un corpus Markdown
citable, reproducible y listo para un pipeline de RAG, respetando `robots.txt` y
sin depender de una API del sitio.

## Stack

| Categoría | Tecnología |
|-----------|------------|
| **Lenguaje** | Python 3.13+ |
| **Gestor de paquetes y entorno** | [`uv`](https://docs.astral.sh/uv/) |
| **Build backend** | `uv_build` (src-layout) |
| **Paquete Python** | `carvajal` |
| **HTTP** | `requests` (sesión única, `User-Agent` identificable, `timeout`) |
| **Parseo HTML** | `beautifulsoup4` + `lxml` |
| **RAG** | LangChain + FAISS + embeddings |
| **LLM** | DeepSeek (`deepseek-chat`), Anthropic Claude u Ollama (`llama3.2`) |
| **Interfaz de pruebas** | Streamlit |
| **Tipado estático** | [`ty`](https://github.com/astral-sh/ty) |
| **Testing** | [`pytest`](https://docs.pytest.org/) |
| **Linting / Formato** | [Ruff](https://docs.astral.sh/ruff/) |
| **Pre-commit** | [pre-commit](https://pre-commit.com) |
| **CI/CD** | [GitHub Actions](.github/workflows/ci.yml) |
| **Dependencias automáticas** | [Dependabot](.github/dependabot.yml) |

## Fuentes del corpus

| Origen | Dominio | Aporte |
|---|---|---|
| Sitio oficial | `carvajal.com` | Misión, historia, sectores, gobierno corporativo, sostenibilidad |
| Prensa económica | `larepublica.co`, `elpais.com.co`, `caliescribe.com` | Ingresos, EBITDA, márgenes, utilidad neta, activos, pasivos, patrimonio, empleo |

Los documentos de terceros se marcan en el *front matter* con `source_type: tercero`, y
el asistente está instruido para atribuir cada cifra a su medio y fecha.

## Pipeline de captura

```text
semillas (21 URLs)
   │  robots.txt + rate limit (1 s/host) + User-Agent propio + timeout 30 s
   ▼
Bronze  data/raw/*.html          HTML crudo, tal como llegó
   ▼
Silver  data/processed/*.md      Markdown limpio (sin menús, header ni footer)
   ▼
Gold    data/gold/*.md           Markdown + front matter (url, title, section,
                                 domain, source_type, captured_at, hash, chars)
   ▼
Índice  data/gold/index.jsonl    una línea por documento (URL, sección, hash, tokens)
```

- **Deduplicación** por huella SHA-256 del contenido; las páginas casi vacías
  (< 200 caracteres) no se deduplican para no perder secciones distintas.
- **Enriquecimiento**: `section` se deriva de la URL del sitio oficial (`inversionistas`,
  `quienes-somos`…) y es `prensa` en las fuentes de terceros; `hash` y `chars` describen
  cada documento.
- **Métricas**: al terminar, `carvajal capture` reporta descubiertas, descargadas,
  escritas, descartadas (robots, duplicadas, errores), caracteres, tokens estimados y
  duración.

## 🗺️ Arquitectura

Diagrama interactivo autocontenido (generado con [Archify](https://github.com/tt-a1i/archify)):
pan/zoom, búsqueda de componentes, tema claro/oscuro y exportación. Ábrelo en el
navegador: [`docs/arquitectura.html`](docs/arquitectura.html). La fuente tipada y
versionada es [`docs/arquitectura.json`](docs/arquitectura.json), y la versión Mermaid
está en [`docs/arquitectura.md`](docs/arquitectura.md).

[![Arquitectura del proyecto (tema oscuro)](docs/arquitectura.visual-check.2048x1320.dark.png)](docs/arquitectura.html)

## Instalación

```bash
# Clonar el repositorio
git clone git@github.com:markodavid/carvajal.git
cd carvajal

# Sincronizar el entorno (crea .venv e instala dependencias)
uv sync
```

## Uso

```bash
# Capturar el sitio oficial y las fuentes de terceros
# (descubrir → extraer → limpiar → deduplicar → enriquecer)
uv run carvajal capture

# Solo el sitio oficial / solo fuentes de terceros
uv run carvajal capture --scope oficial
uv run carvajal capture --scope terceros

# Ajustar el rate limit o ignorar robots.txt (solo pruebas locales)
uv run carvajal capture --delay 2.0
uv run carvajal capture --ignore-robots

# Ver el estado del corpus (documentos, origen, tokens, índice)
uv run carvajal status

# Listar semillas
uv run carvajal list

# Preguntar al corpus (RAG)
uv run carvajal ask "¿En qué consiste el fondo de inversión de Carvajal?"

# Interfaz web de pruebas (Streamlit)
make app

# Evaluación: 25 preguntas de prueba -> docs/resultados.md
make eval
```

## Configuración del LLM

Copia el archivo de ejemplo y completa tu clave (`.env` está en `.gitignore`):

```bash
cp .env.example .env
```

```ini
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
```

También puedes configurar las variables en la terminal:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Proveedor LLM: `ollama`, `deepseek` o `claude`. | `ollama` |
| `DEEPSEEK_API_KEY` | Clave API de DeepSeek (solo si `LLM_PROVIDER=deepseek`). | `""` |
| `DEEPSEEK_MODEL` | Modelo DeepSeek a utilizar. | `deepseek-chat` |
| `DEEPSEEK_BASE_URL` | Endpoint compatible con OpenAI. | `https://api.deepseek.com/v1` |
| `ANTHROPIC_API_KEY` | Clave API de Anthropic (solo si `LLM_PROVIDER=claude`). | `""` |
| `CLAUDE_MODEL` | Modelo Claude a utilizar (p. ej. `claude-sonnet-4-5`). | `claude-sonnet-4-5` |

> Los embeddings se calculan localmente con Ollama (`nomic-embed-text`),
> independientemente del proveedor del LLM.

El índice vectorial FAISS se guarda en `data/index/` (ignorado por Git) y se reutiliza
mientras el corpus no cambie, de modo que la app arranca en segundos. La primera
ejecución calcula los embeddings desde cero (varios minutos en CPU). Para forzar el
recálculo, borra `data/index/`.

Ejemplo con DeepSeek vía API:

```bash
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "<tu-clave-de-deepseek>"
$env:DEEPSEEK_MODEL = "deepseek-chat"
uv run carvajal ask "¿Cuál es la misión de Carvajal?"
```

## Calidad

```bash
make install    # uv sync
make dev        # install + pre-commit install
make check      # lint + formato + tipos + pruebas
make lint       # Ruff (lint)
make format     # Ruff (formato)
make typecheck  # ty
make test       # pytest
make build      # uv build
make clean      # limpiar cachés y artefactos
```

## Estructura

```text
carvajal/
├── src/
│   └── carvajal/
├── tests/
├── data/
│   └── gold/       # entregable versionado (capa gold)
│                   # data/index/ se genera en local (caché FAISS, ignorada)
├── docs/
├── .github/
├── .opencode/
├── AGENTS.md
├── CONSTITUTION.md
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── Makefile
├── pyproject.toml
├── uv.lock
├── .python-version
└── .pre-commit-config.yaml
```

## Documentación

- [`docs/arquitectura.md`](docs/arquitectura.md) — diagramas Mermaid del pipeline y del stack.
- [`docs/arquitectura.html`](docs/arquitectura.html) — diagrama interactivo (Archify), fuente en `docs/arquitectura.json`.
- [`docs/informe.md`](docs/informe.md) — informe del proyecto (problema, solución, datos, modelado, resultados).
- [`docs/presentacion.md`](docs/presentacion.md) — guion de la sustentación (15 min, sin PowerPoint).
- [`CONSTITUTION.md`](CONSTITUTION.md) — verdad central del proyecto.

## Contribución

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) y la [`CONSTITUTION.md`](CONSTITUTION.md).

## Licencia

Distribuido bajo la licencia [MIT](LICENSE).
