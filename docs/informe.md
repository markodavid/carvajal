# Informe — Asistente Q&A del corpus Carvajal

> Proyecto: **Carvajal Corpus** · Repositorio: <https://github.com/markodavid/carvajal>
> Fase: captura del corpus + asistente RAG con interfaz de pruebas.

---

## 1. Descripción del problema

Carvajal es una empresa multilatina con más de 120 años de historia y presencia en
10 países. Su información institucional está distribuida en un sitio web con decenas
de páginas: historia, propósito superior, sectores de negocio, sostenibilidad,
gobierno corporativo, compromiso ético, inversionistas y noticias.

**Necesidad:** un canal de comunicación automatizado y preciso que permita a
colaboradores, inversionistas y público general resolver preguntas sobre la empresa
sin navegar manualmente el sitio, y sin el riesgo de respuestas inventadas que
desinformen.

## 2. Planteamiento de la solución

Se construyó un **sistema Q&A basado en RAG** (*Retrieval-Augmented Generation*) como
núcleo de un futuro chatbot institucional:

```text
Sitio web de Carvajal
        │  scraping (requests + BeautifulSoup/lxml)
        ▼
data/gold/*.md  ──►  chunking (1000/200)  ──►  embeddings (Ollama: nomic-embed-text)
                                                        │
Pregunta del usuario ──► retriever FAISS (k=5) ─────────┘
        │
        ▼
Prompt de sistema (corpus consolidado + reglas anti-alucinación)
        │
        ▼
LLM (Claude vía API) ──► Respuesta basada únicamente en el corpus
        │
        ▼
Interfaz Streamlit (campo de pregunta + área de respuesta)
```

Decisiones técnicas:

| Componente | Elección | Motivo |
|---|---|---|
| Framework de LLM | **LangChain** | Recomendado por el curso; integra Ollama y Anthropic |
| Modelo (módulo 2) | **DeepSeek vía API** (`deepseek-chat`, configurable) | API compatible con OpenAI, bajo costo y buen rendimiento en español |
| Alternativa local | **Ollama** (`llama3.2`) | Permite demo sin API mediante `LLM_PROVIDER=ollama` |
| Embeddings | **Ollama `nomic-embed-text`** | Open source, local y sin costo |
| Base vectorial | **FAISS** (índice en disco) | Suficiente para 21 documentos; cero infraestructura |
| Interfaz | **Streamlit** | Campo de pregunta y área de respuesta en minutos |

## 3. Preparación de los datos

### 3.1 Scraping

- Semillas explícitas en `src/carvajal/config.py`: **15 URLs** del sitio oficial
  (`config.SEEDS`) y **6 fuentes de terceros** (`config.EXTERNAL_SEEDS`).
- Cliente HTTP `requests` con sesión única, `User-Agent` identificable y `timeout`
  de 30 s; **se consulta `robots.txt`** por host (incluido `Crawl-delay`, si existe) y
  se espera **1 s entre peticiones** al mismo host.
- Se descartan del alcance vídeos, PDFs y páginas autenticadas.

**Por qué fuentes de terceros.** Los indicadores financieros no están en el HTML de
`carvajal.com`: la página *Cifras relevantes* los pinta con contadores JavaScript (el
HTML entrega `USD 0`) y las cifras completas viven en los ~76 PDFs de
*Información financiera*. La prensa económica publica esos mismos resultados en texto
plano, así que se incorporaron seis notas de `larepublica.co`, `elpais.com.co` y
`caliescribe.com` (ingresos, EBITDA, márgenes, utilidad neta, activos, pasivos,
patrimonio y empleo). Cada documento registra su procedencia en el *front matter*
(`domain`, `source_type: oficial|tercero`) y el asistente está instruido para atribuir
cada cifra a su medio y fecha.

### 3.2 Limpieza

Pipeline Medallion: **bronze** (`data/raw/*.html`, HTML crudo) → **silver**
(`data/processed/*.md`, Markdown limpio) → **gold** (`data/gold/*.md`, Markdown +
*front matter*) más el índice `data/gold/index.jsonl`. El entregable versionado es
`data/gold/`; bronze y silver se regeneran con `carvajal capture`.

El pipeline aplica, en orden: `robots.txt` (con `Crawl-delay`), *rate limit* de 1 s por
host, `User-Agent` propio y timeout de 30 s; después extrae el Markdown, deduplica por
huella SHA-256 del contenido, y enriquece cada documento con `section`, `domain`,
`source_type`, `hash` y `chars`.

El extractor (`src/carvajal/extracting.py`) recorre el DOM y conserva encabezados,
párrafos, listas y tablas, descartando subárboles de navegación (`nav`, `header`,
`footer`, formularios, modales y contenedores con clases de menú). Se colapsan
espacios y se eliminan bloques duplicados.

**Corrección clave:** la primera versión del extractor emitía el texto de cada
elemento padre *y* de sus hijos, duplicando el menú decenas de veces: el corpus pesaba
**2.45 MB** y contaminaba la recuperación. Tras corregirlo (y excluir las plantillas
`header`/`footer` de Elementor), el corpus quedó en **64.5 KB de texto editorial
limpio** (≈ 15 000 tokens), apto para consolidarse en el prompt de sistema.

Con las seis fuentes de terceros el corpus pasó a **21 documentos (~89 KB, ≈ 22 000
tokens)**, todavía por debajo del límite de 100 000 caracteres del prompt de sistema.

### 3.3 Chunking

- `RecursiveCharacterTextSplitter` con `chunk_size=1000` y `chunk_overlap=200`.
- Recuperación de los **5 fragmentos** más similares por pregunta (`k=5`).
- Los metadatos de cada fragmento conservan la fuente (`slug` del documento).

### 3.4 Corpus extendido (capa de recuperación)

El núcleo de 21 documentos cubre el sitio matriz, pero deja fuera productos, filiales y
fundaciones. Para cerrar esa brecha se importó el corpus de un compañero (rama
`modulo_1`, captura `corpus-2026-10-23`) como **capa extendida**:

- `carvajal import` lee su catálogo (`scraping_todos.jsonl`), filtra por categoría,
  presupuesto de caracteres y páginas, y **vuelve a extraer el HTML con el extractor
  propio**; los PDF se toman página por página de su texto Silver.
- Deduplica por URL normalizada y hash del texto, y escribe
  `data/external/<fuente>/{silver,gold,manifest.json}`.
- La importación por defecto trae 485 documentos (≈1,45 M caracteres) de
  identidad, gobierno, negocio, sostenibilidad, tecnología y noticias.
- La capa extendida **no entra al prompt**: se recupera con FAISS y se cita con URL,
  categoría y página. Así el prompt conserva su límite de 100 000 caracteres.

## 4. Modelado

### 4.1 Embeddings

`nomic-embed-text` servido por Ollama. Es open source, se ejecuta localmente y no
requiere claves ni cuotas de API.

### 4.2 LLM

- **DeepSeek vía API** (`ChatOpenAI` apuntando a `https://api.deepseek.com/v1`) como
  opción principal del módulo 2, con modelo `deepseek-chat`.
- Alternativas configurables: Ollama (`llama3.2`) y Anthropic Claude.
- Configuración por entorno: `LLM_PROVIDER=deepseek|ollama|claude`, `DEEPSEEK_API_KEY`,
  `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` (y `ANTHROPIC_API_KEY` / `CLAUDE_MODEL`).
- Temperatura `0` para respuestas deterministas y fieles al corpus.

### 4.3 Base de datos vectorial

**FAISS** con índice persistido en `data/index/`. El índice se construye una vez y se
reutiliza mientras el corpus no cambie (huella SHA-256 de los chunks), de modo que la
aplicación arranca en segundos; la primera construcción tarda varios minutos porque los
embeddings se calculan en CPU con Ollama. Es adecuado para el tamaño actual del corpus
(21 documentos, ~89 KB). Para producción se recomendaría una base vectorial dedicada
(Chroma, pgvector o Qdrant).

### 4.4 Diseño del prompt

El *system prompt* es la **memoria completa del asistente**: consolida todo el texto
limpio del corpus (cada documento con su fuente) y fija reglas estrictas:

- Responder **únicamente** con información del contexto/corpus.
- Si la respuesta no está en el corpus, decirlo explícitamente ("no lo sé").
- No inventar datos ni usar conocimiento externo.
- Indicar las fuentes consultadas.

El mensaje del usuario incluye, además, los **fragmentos recuperados** por FAISS
para enfocar la respuesta. El enfoque es *zero-shot*: no se usan ejemplos few-shot;
la robustez se logra con instrucciones explícitas, delimitadores del corpus y
temperatura 0.

### 4.5 Interfaz de prueba

`uv run streamlit run app.py` levanta una aplicación de dos pestañas:

- **Pipeline de scraping**: ejecuta la captura y muestra en pantalla las siete etapas
  (descubrir, `robots.txt`, descargar, extraer, deduplicar, enriquecer, indexar), el log
  por URL y las métricas de la corrida: descubiertas, descargadas, escritas, descartadas
  con su motivo, caracteres, tokens estimados y duración. Un **diagrama de bloques**
  ilumina cada etapa al avanzar el proceso (gris = pendiente, color = activa, ✓ = hecha).
- **Asistente**: pregunta → respuesta con **fuentes citadas** (dominio, tipo de fuente,
  capa núcleo/extendida, categoría y fragmento recuperado). Advierte si el índice
  vectorial está desactualizado.

La captura es idempotente: si el contenido no cambia, el `hash` se repite y el índice
FAISS no se invalida, de modo que la demostración puede ejecutarse sin esperar la
reconstrucción de embeddings.

## 5. Resultados

### 5.1 Metodología

- **25 preguntas** de prueba en `data/questions.json`, cubriendo los sectores,
  historia, propósito, sostenibilidad, gobierno corporativo, inversionistas y
  contacto, más preguntas fuera del alcance para verificar la abstención.
- Ejecución reproducible: `make eval` (o `uv run carvajal eval`), que genera
  [`docs/resultados.md`](resultados.md) con pregunta + respuesta.
- Configuración de la corrida: `LLM_PROVIDER=deepseek` (`deepseek-chat`), embeddings
  `nomic-embed-text` (Ollama), `k=5` y temperatura 0.
- Criterios de evaluación: **exactitud** (¿la respuesta coincide con el corpus?),
  **coherencia** (¿es clara y completa?), **fidelidad** (¿cita fuentes y evita
  alucinaciones?) y **abstención** (¿reconoce lo que no sabe?).

### 5.2 Resumen de la evaluación

| Resultado | Preguntas |
|---|---|
| Respuestas completas y correctas | **21 / 25** |
| Respuestas parciales (señalan información faltante) | **3 / 25** (Bioform, LiquidezYa, sostenibilidad) |
| Abstención correcta | **1 / 25** (datos de contacto) |

> Evaluación cualitativa del equipo sobre las respuestas generadas con DeepSeek
> (`deepseek-chat`) el 2026-10-28. El detalle completo está en `docs/resultados.md`.

### 5.3 Ejemplos representativos

| # | Pregunta | Respuesta (resumen) | Evaluación |
|---|---|---|---|
| 2 | ¿En qué año y ciudad fue fundada Carvajal? | 1904 en Cali, Colombia, con la impresión del semanario *El Día*; cita `historia` y `quienes_somos`. | Correcta |
| 4 | ¿Cuáles son los cuatro sectores? | Impresión y Escritura; Papel y Empaques; Tecnología y Servicios; Inmobiliario. | Correcta |
| 17 | ¿Qué noticias recientes publica? | Lista 12 titulares con sus fechas a partir de `noticias`. | Correcta |
| 18 | ¿Cuál es la historia desde su fundación? | Cronología completa 1904–2024 organizada por etapas, citando `historia`. | Correcta |
| 21 | ¿Cómo contactar a Carvajal? | "No dispongo de esa información": el corpus no incluye datos de contacto generales. | Abstención correcta |

### 5.4 Análisis y limitaciones

- **Fidelidad:** las respuestas citan las fuentes del corpus y no se detectaron
  datos inventados; cuando falta información, el modelo lo declara.
- **Cobertura:** preguntas de síntesis (historia completa, noticias, valores)
  se responden con listas y cronologías completas gracias al corpus consolidado
  en el prompt.
- **Abstención:** la pregunta de contacto se rechaza correctamente porque el pie
  de página (con enlaces de contacto) se excluye a propósito del corpus.
- **Página vacía:** `sostenibilidad.md` quedó sin texto (contenido dinámico o
  basado en imágenes); la respuesta se construyó con menciones de otras fuentes
  y se señaló la ausencia.
- **Noticias:** solo se capturan titulares y fechas, no el cuerpo de cada noticia.
- **Recuperación:** `k=5` sobre chunks de 1000/200; el índice FAISS se cachea en
  `data/index/` y solo se reconstruye si cambia el corpus.
- **Sin memoria conversacional:** una pregunta por turno.
- **Evaluación cualitativa y manual:** no se implementó un *benchmark* automático.
- **Capa extendida:** sus fechas son heterogéneas (`date_status`) y muchas fuentes no
  tienen fecha de publicación; las respuestas deben atribuir la captura y no tratarla
  como histórico. Los PDF quedan fuera por defecto para no desbordar el presupuesto.

## 6. Presentación

Sustentación en vivo de **15 minutos** con demostración funcional en Streamlit.
El guion detallado está en [`docs/presentacion.md`](presentacion.md).

> **No se realizan presentaciones de PowerPoint.**

## Anexos

### Comandos

```bash
uv sync                    # entorno
uv run carvajal capture    # regenerar el corpus Gold
uv run carvajal ask "..."  # pregunta por CLI
make app                   # interfaz Streamlit
make eval                  # 25 preguntas -> docs/resultados.md
make check                 # lint + formato + tipos + pruebas
```

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `LLM_PROVIDER` | `ollama`, `deepseek` o `claude` | `ollama` |
| `DEEPSEEK_API_KEY` | Clave API de DeepSeek | `""` |
| `DEEPSEEK_MODEL` | Modelo DeepSeek | `deepseek-chat` |
| `DEEPSEEK_BASE_URL` | Endpoint compatible con OpenAI | `https://api.deepseek.com/v1` |
| `ANTHROPIC_API_KEY` | Clave API de Anthropic | `""` |
| `CLAUDE_MODEL` | Modelo Claude | `claude-sonnet-4-5` |
