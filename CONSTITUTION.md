# CONSTITUTION — Carvajal Corpus

> **Verdad central del proyecto.** Este documento define el propósito, el stack, la
> estructura, las convenciones y el flujo de trabajo de `Carvajal Corpus`. Si algo aquí
> contradice al código, el código manda **y este archivo se actualiza**.

> ⚠️ **Directiva de mantenimiento:** cada vez que se realicen cambios significativos
> (nuevas funcionalidades, cambios arquitectónicos, adición de clases/módulos o ajustes
> de tecnologías), **se debe actualizar este archivo en el mismo commit** para mantener
> la verdad central del proyecto bien documentada.

---

## 0. Identidad del proyecto

| Campo | Valor |
|-------|-------|
| **Nombre** | Carvajal Corpus |
| **Descripción** | Pipeline de captura y curaduría del corpus web de Carvajal para RAG. |
| **Repositorio** | https://github.com/markodavid/carvajal |
| **Autoría** | Marko David Garcia — markodavidgm@gmail.com |
| **Licencia** | MIT |
| **Rama principal** | `main` |
| **Estado** | Captura inicial en curso 🚧 |

## 1. Propósito y no-propósito

### Propósito

Convertir páginas públicas del sitio web de **Carvajal** en un corpus Markdown
citable, reproducible y listo para un pipeline de RAG, respetando `robots.txt` y
sin depender de una API del sitio.

### No-propósito

No es un *crawler* masivo del dominio completo, ni un motor de búsqueda, ni un
sistema que atraviese formularios, sesiones autenticadas o datos personales. Tampoco
es un generador de respuestas: el consumo del corpus (embeddings, recuperación,
agente) forma parte del proyecto del curso y se incorpora aquí en su fase de pruebas
con asistente RAG.

## 2. Alcance

### Dentro del alcance

- Capturar las landing y las páginas de contenido que de ella dependen: misión,
  historia, sostenibilidad, especialidades (empaques, educación, tecnología,
  comunicación, espacios), propiedades e inversiones, inversores, equipo y notas
  institucionales.
- Capturar **fuentes de terceros** (prensa económica y análisis) para cubrir los
  indicadores financieros que el sitio oficial solo publica dentro de PDFs. Cada
  documento de terceros se marca en el *front matter* con `domain` y
  `source_type: tercero`, y el asistente está obligado a distinguirlos de las fuentes
  oficiales.
- Respetar `robots.txt` (incluido `Crawl-delay`) y aplicar *rate limit* por host antes
  de cada petición.
- Mantener tres capas materializadas en disco: **bronze** (`data/raw/`, HTML crudo),
  **silver** (`data/processed/`, Markdown limpio) y **gold** (`data/gold/`, Markdown +
  *front matter* + `index.jsonl`).
- Extraer el cuerpo editorial descartando menús, formularios, modales y pie de página.
- Deduplicar por huella SHA-256 y enriquecer cada documento con sección, hash y tamaño.
- Versionar `data/gold/` como entregable del corpus (bronze y silver se regeneran).
- Importar corpus externos de terceros a una **capa extendida** (`data/external/`),
  solo para recuperación y citación, con manifiesto, deduplicación por URL/hash y
  procedencia explícita (`origin`, `category`, `entity`, `page`). Esa capa nunca se
  consolida en el prompt de sistema.
- Ofrecer una CLI y un Makefile como interfaz única del proyecto.

### Fuera del alcance (por ahora)

- Rastrear el `sitemap.xml` completo del dominio (podcast, noticias, especialistas).
- Vídeos, PDFs y transcripciones.
- Páginas tras autenticación o cualquier contenido no público.
- Evaluación automatizada y benchmarking del asistente (fuera de la interfaz de pruebas).

### Fases

| Fase | Estado | Entregable |
|------|--------|------------|
| 1. Captura inicial (landing + secciones) | ✅ Hecha | 15 documentos limpios en `data/gold/` (~64.5 KB) |
| 2. Ampliación de semillas | ✅ Hecha | 6 fuentes de terceros con indicadores financieros |
| 3. Enriquecimiento (PDFs, vídeo) | ⬜ Pendiente | Nuevas semillas y extractores |
| 4. Chunking y embeddings | ✅ Hecha | Chunking 1000/200 + FAISS con embeddings Ollama |
| 5. Asistente RAG (LLM + prompt + UI) | 🚧 En curso | LangChain + FAISS + Ollama/DeepSeek/Claude + Streamlit |
| 6. Corpus externo (capa extendida) | ✅ Hecha | `carvajal import` + manifiesto + recuperación citada |

## 3. Stack técnico

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

> ⚠️ **Regla dura:** toda gestión de dependencias y entornos pasa por `uv`. Está
> **prohibido** `pip` y `requirements.txt`.

> 📝 **Decisión sobre los extractores:** se evaluó y se descartó `trafilatura` como
> extractor principal. Es excelente con artículos de prensa, pero descarta las tarjetas
> y acordeones de las *landings* institucionales —justo el contenido que el RAG necesita—.
> El extractor propio recorre el DOM y conserva encabezados, listas, tablas y enlaces.

## 4. Estructura del repositorio

```text
carvajal/
├── src/carvajal/          # código del paquete (src-layout)
│   ├── config.py            # semillas, capas, política HTTP
│   ├── fetching.py          # cliente HTTP educado
│   ├── extracting.py        # HTML → Markdown
│   ├── gold.py              # front matter + índice JSONL
│   ├── pipeline.py          # orquestación de las tres capas
│   ├── models.py            # modelos del dominio
│   ├── importer.py          # importación del corpus externo (capa extendida)
│   ├── rag.py               # recuperación, prompt y generación (RAG)
│   ├── ui.py                # interfaz web de pruebas (Streamlit)
│   └── cli.py               # capture / import / ask / status / list
├── data/                    # capas Medallion (raw y processed ignoradas)
│   ├── raw/                 # bronze — HTML crudo
│   ├── processed/           # silver — Markdown limpio
│   ├── gold/                # gold — entregable versionado (núcleo)
│   ├── external/            # capa extendida importada (solo manifiesto en Git)
│   └── index/               # índice FAISS en caché (regenerable, ignorado por Git)
├── tests/                   # pruebas (pytest, patrón AAA)
├── app.py                   # entrada de la interfaz: streamlit run app.py
├── docs/                    # documentación, ADRs e investigación
│   ├── arquitectura.json    # fuente tipada del diagrama (Archify)
│   ├── arquitectura.html    # diagrama interactivo autocontenido
│   └── arquitectura.md      # versión Mermaid del mismo pipeline
├── .github/                 # gobernanza (PR/issue templates, CI, Dependabot, labels)
├── .opencode/rules/         # reglas para agentes (tgrep)
├── AGENTS.md                # contexto para agentes LLM
├── CONSTITUTION.md          # este archivo — verdad central
├── README.md                # puerta de entrada pública
├── CONTRIBUTING.md          # guía de contribución
├── CODE_OF_CONDUCT.md       # código de conducta
├── Makefile                 # automatización de tareas
├── pyproject.toml           # metadatos y dependencias (uv)
├── uv.lock                  # lockfile determinista (versionado)
├── .python-version          # versión de Python fijada
└── .pre-commit-config.yaml  # hooks de calidad
```

## 5. Convenciones de código

- **Estilo:** [PEP 8](https://peps.python.org/pep-0008/) y [PEP 257](https://peps.python.org/pep-0257/),
  impuesto por **Ruff** (`line-length = 100`, comillas dobles).
- **Tipado:** anotaciones en funciones y firmas públicas.
- **Nomenclatura:** `snake_case` (funciones/variables), `PascalCase` (clases),
  `UPPER_CASE` (constantes).
- **Docstrings:** en módulos, clases y funciones públicas.
- **Pruebas:** `pytest` con el patrón **AAA** (*Arrange · Act · Assert*).
- **Idioma:** UI, documentación y commits en español; identificadores de código en inglés.
- **Reglas propias:**
  - La extracción **nunca** depende de la red: `extracting` recibe HTML ya descargado.
  - El *front matter* es la única fuente de metadatos; no se duplica en el cuerpo.
  - `data/gold/` es el contrato con el proyecto consumidor: cambiarlo es un cambio
    incompatible y se documenta en esta constitución.
  - La capa extendida (`data/external/`) **solo** se recupera y se cita; nunca se
    consolida completa en el prompt ni se presenta como fuente oficial.
  - Toda importación deja `manifest.json` con su fuente, captura donante y conteos.

## 6. Calidad y automatización

| Herramienta | Rol | Comando |
|-------------|-----|---------|
| `uv` | Entornos y dependencias | `uv sync` |
| Ruff | Lint + formato | `make lint` / `make format` |
| `ty` | Verificación de tipos | `make typecheck` |
| `pytest` | Pruebas | `make test` |
| `pre-commit` | Hooks antes de cada commit | `make pre-commit` |
| GitHub Actions | CI (pre-commit + ty + pytest) | `.github/workflows/ci.yml` |

- Ningún commit se salta los hooks (`--no-verify` está prohibido salvo causa justificada y documentada).
- La **CI debe estar en verde** antes de fusionar un Pull Request.
- Toda dependencia nueva entra con `uv add` / `uv add --dev` (nunca editando `uv.lock` a mano).

## 7. Repositorio y Git

- **Remoto (SSH):** `git@github.com:markodavid/carvajal.git`
- **Rama principal:** `main`
- **Estrategia de ramas:** `feat/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...`, `chore/...`; integración vía Pull Request.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) —
  `feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`, `chore:`.
- **Identidad git:** Marko David Garcia <markodavidgm@gmail.com> (ver §11).

## 8. Flujo diario (commit + push)

```bash
# 1. Ver cambios
git status

# 2. Verificación completa (lint + formato + tipos + pruebas)
make check

# 3. Agregar y commitear (los hooks se ejecutan solos)
git add -A
git commit -m "tipo: mensaje descriptivo"

# 4. Subir a GitHub
git push
```

## 9. Historial de decisiones técnicas

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-10-21 | Adoptar `uv` como gestor único de entornos y dependencias | Reproducibilidad; prohibido `pip`/`requirements.txt` |
| 2026-10-21 | Adoptar Ruff (lint + formato) y pre-commit | Calidad automatizada antes de cada commit |
| 2026-10-21 | Adoptar Conventional Commits | Historial legible y automatizable |
| 2026-10-21 | Adoptar licencia MIT y `CONSTITUTION.md` como fuente única de verdad | Claridad legal y operativa |
| 2026-10-21 | Patrón Medallion (bronze/silver/gold) con `data/gold/` versionado | Permite reprocesar sin volver a la web; el entregable queda en Git |
| 2026-10-21 | Descartar `trafilatura` como extractor principal | Pierde tarjetas y acordeones de las *landings* institucionales |
| 2026-10-21 | Extractor propio basado en DOM | Control explícito de qué es contenido y qué es *chrome* |
| 2026-10-21 | Eliminar el pie de página institucional del corpus | Repite el mismo bloque en todas las páginas y contamina la recuperación |
| 2026-10-21 | Semillas explícitas en `config.SEEDS` en lugar de rastrear el sitemap | Alcance acotado y reproducible (ampliado el 2026-10-29 con `EXTERNAL_SEEDS`) |
| 2026-10-27 | Capturar las landing y secciones públicas de Carvajal (`config.SEEDS`) | Punto de partida verificable y reproducible del corpus |
| 2026-10-28 | Incorporar RAG con LangChain + FAISS y chunking | Recuperación de contexto sobre `data/gold/` antes de generar respuestas |
| 2026-10-28 | Añadir asistente RAG con LLM configurable (Ollama / Claude API) | El curso define dos opciones de modelo; se soportan ambas vía `LLM_PROVIDER` |
| 2026-10-28 | Corregir el extractor: eliminar duplicación de contenedores y *chrome* | El corpus pasó de 2.45 MB a 64.5 KB de texto editorial; mejora la recuperación y permite consolidarlo en el prompt |
| 2026-10-28 | Consolidar el corpus limpio en el prompt de sistema | El prompt es la "memoria" completa del asistente en esta fase |
| 2026-10-28 | Añadir DeepSeek como proveedor principal vía API compatible con OpenAI | El curso usa la API de DeepSeek; Ollama y Claude quedan como alternativas vía `LLM_PROVIDER` |
| 2026-10-28 | Persistir el índice FAISS en `data/index/` con huella del corpus | Los embeddings en CPU tardan minutos por arranque; con caché la app abre en segundos y se invalida sola al cambiar `data/gold/` |
| 2026-10-29 | Incorporar fuentes de terceros (`EXTERNAL_SEEDS`) al corpus | Los indicadores financieros no están en el HTML oficial (contadores JS y PDFs); la prensa económica los publica en texto y cada documento se marca con `source_type: tercero` |
| 2026-10-29 | Adoptar Archify para el diagrama de arquitectura (`docs/arquitectura.json` → `.html`) | Documentación viva validada: el JSON tipado es la fuente, el HTML autocontenido es el artefacto que se comparte y se enlaza desde el README |
| 2026-10-29 | Materializar las capas Bronze y Silver y añadir `index.jsonl` | El pipeline escribía solo Gold: el patrón Medallion era una promesa del informe, no del código. Ahora cada capa queda en disco y el índice JSONL permite auditar URL, sección, hash y tamaño |
| 2026-10-29 | Respetar `robots.txt` + `Crawl-delay` y aplicar rate limit de 1 s por host | El README lo afirmaba sin implementarlo; es requisito de captura responsable y de la rúbrica |
| 2026-10-29 | Deduplicar por SHA-256 y enriquecer con `section` y `hash` | Evita documentos repetidos al ampliar semillas y da trazabilidad por documento |
| 2026-10-29 | Interfaz Streamlit de dos pestañas con el pipeline visible | La evaluación exige ver las etapas y las métricas del scraping en pantalla, no solo el Q&A. El `CaptureReport` y los eventos de progreso son la fuente única de esas métricas |
| 2026-10-29 | Identidad visual de Carvajal (logo SVG oficial + paleta de marca) y diagrama de bloques en vivo | El diagrama ilumina cada etapa al avanzar la captura, lo que hace visible el proceso sin depender del log; la paleta se toma de los tokens del sitio oficial, no se inventa |
| 2026-10-29 | Importar el corpus de un compañero como **capa extendida** (`data/external/`) | Su corpus aporta ~2.100 fuentes (productos, filiales, fundaciones y PDF) que el núcleo de 21 documentos no cubre; se re-extrae con el extractor propio, se deduplica y solo se usa para recuperación porque 1,4 M de caracteres no caben en el prompt |

## 10. Notas y tareas pendientes

- [ ] Añadir extracción de PDFs (informes, memorias anuales).
- [ ] Añadir transcripciones de vídeo (`yt-dlp` / `youtube-transcript-api`).
- [ ] Enriquecer el *front matter* con `entidades` y `especialidades` detectadas.
- [ ] Evaluar *deduplicación* de *boilerplate* entre documentos por hash de bloque.
- [ ] Definir el contrato de *chunking* con el proyecto consumidor.
- [x] Ejecutar `make eval` con credenciales y anexar los resultados al informe.
- [x] Importar el corpus externo como capa extendida con manifiesto y deduplicación.
- [ ] Incorporar PDF prioritarios del corpus externo (estados financieros, informes anuales).
- [ ] Registrar decisiones de arquitectura (ADRs) en `docs/decisions/`.

## 11. Configuración local (no trackear)

> Configuración específica de la máquina local. **NO incluir en commits.**

Dentro de la carpeta de proyectos, `~/.gitconfig` aplica:

```ini
[includeIf "gitdir:C:/Users/marko/OneDrive/Documentos/Marko/UAO/Semestre 3/TAIAML/carvajal/"]
    path = C:/Users/marko/.gitconfig-personal
```

`~/.gitconfig-personal`:

```ini
[user]
    name = Marko David Garcia
    email = markodavidgm@gmail.com
[core]
    sshCommand = ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes
```

> Efecto: todo repositorio bajo la carpeta personal firma con la identidad personal y
> usa la llave `id_ed25519`, sin flags por proyecto.
