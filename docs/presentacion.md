# Guion de sustentación — 15 minutos (demo en vivo, sin PowerPoint)

> Proyecto: **Carvajal Corpus** — sistema Q&A basado en RAG, con tres tareas de LLM
> (Resumen, FAQ y Q&A) y el pipeline de scraping visible en la interfaz.
> Regla del curso: **no se permiten presentaciones de PowerPoint**. La sustentación se
> apoya en la demo funcional y en este documento.

## Preparación previa (5 minutos antes)

```bash
# 1. Entorno
uv sync

# 2. Embeddings locales (Ollama)
ollama serve
ollama pull nomic-embed-text

# 3. LLM vía DeepSeek (PowerShell)
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "<clave>"
$env:DEEPSEEK_MODEL = "deepseek-chat"

# 4. Verificar y abrir la interfaz ANTES de empezar
uv run carvajal status          # 24 documentos · 18 oficiales / 6 terceros
make app                        # http://localhost:8501
```

Checklist antes de exponer:

- [ ] La app ya está abierta y con la pestaña **Pipeline** cargada (Streamlit tarda ~40 s
      en el primer arranque en este equipo).
- [ ] El índice está al día: si la app avisa «índice desactualizado», no preguntes hasta
      que termine (puede tardar minutos).
- [ ] `docs/resumen.md`, `docs/faq.md` y `docs/resultados.md` están generados (plan B).
- [ ] Una pregunta de prueba respondió en menos de ~10 s.

> La **capa extendida** del corpus de un compañero está integrada pero **desactivada por
> defecto** (`ENABLE_EXTENDED_LAYER`). Si preguntan: está disponible, requiere precalcular
> el índice y no se usa en la demo para no arriesgar tiempos.

## Guion minuto a minuto

| Tiempo | Bloque | Qué decir / mostrar |
|---|---|---|
| 0:00–2:00 | **Problema y solución** | La información de Carvajal está dispersa: historia, sectores, cifras financieras y avisos. Se necesita un canal automatizado y preciso. Solución: Q&A con RAG como núcleo de un futuro chatbot, con respuestas **citadas** y que reconozcan lo que no saben. |
| 2:00–5:00 | **Datos** | Pestaña *Pipeline*: 24 semillas (18 oficiales + 6 de prensa), `robots.txt`, rate limit de 1 s, capas bronze/silver/gold y deduplicación por SHA-256. La corrección clave: de **2.45 MB a ~93 KB** de texto limpio. *Chunking* 1000/200 y FAISS `k=5`. |
| 5:00–8:00 | **Modelado y prompts** | Embeddings `nomic-embed-text` (Ollama); LLM DeepSeek por API (configurable a Ollama/Claude); FAISS persistido con invalidación por hash. Los **tres prompts** comparten el corpus consolidado y cada uno añade sus reglas: estructura y «no consta» (Resumen), formato P/R/Fuente y temas ausentes (FAQ), grounding y citas (Q&A). Mencionar que se probaron variantes y se midieron (`docs/prompts.md`). |
| 8:00–13:00 | **Demo en vivo** | Ver la secuencia de demo (abajo). Mostrar las **tres tareas** en la interfaz. |
| 13:00–15:00 | **Resultados y cierre** | `docs/resultados.md`: **26/30** completas, 3 parciales, 1 abstención correcta. Limitaciones: corpus acotado (sin contacto ni sedes), sin memoria conversacional, evaluación manual. Siguientes pasos: PDFs, evaluación automática, capa extendida con índice precalculado. |

## Secuencia de demo (5 minutos)

1. **Pipeline** (1 min): poner el máximo de URLs en **2** y pulsar *Ejecutar captura*.
   Señalar el diagrama de bloques iluminándose, el rate limit y las métricas de la corrida
   (descubiertas, escritas, descartadas con motivo, tokens).
2. **Resumen** (1 min): pulsar *Generar resumen*. Señalar los cinco bloques y, sobre todo,
   que el EBITDA de 2024 dice **«no consta en el corpus»** en vez de inventarlo.
3. **FAQ** (1 min): pulsar *Generar FAQ*. Bajar hasta **«Temas sin información en el
   corpus»** y explicar que preferimos declarar el hueco a rellenarlo.
4. **Asistente** (2 min): tres preguntas.
   - *«¿En qué año y ciudad fue fundada Carvajal?»* → 1904 en Cali, con fuentes.
   - *«¿Cuál fue el EBITDA consolidado a septiembre de 2025?»* → `$351.631 millones`,
     atribuido a La República y marcado como **tercero**.
   - *«¿Cuál es el horario de atención y el teléfono de la sede?»* → **no lo sabe** y
     remite a los canales oficiales. Cerrar con esta: es la prueba de que no alucina.

> Si la red falla, el plan B es mostrar `docs/resumen.md`, `docs/faq.md` y
> `docs/resultados.md` — están generados con el mismo corpus y el mismo modelo.

## Preguntas que pueden hacerte

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué hay fuentes de prensa? | El sitio oficial publica los indicadores solo en PDFs o con contadores JS. Cada documento lleva `source_type` y el asistente distingue oficial de tercero al citar. |
| ¿Cómo evitas alucinaciones? | Tres capas: corpus consolidado en el prompt, instrucción explícita de decir «no lo sé», y temperatura 0. Se verificó con variantes (`docs/prompts.md`). |
| ¿Por qué no hay datos de contacto? | Carvajal no los publica en HTML (404 en `/contacto`, `/sedes`; solo formularios). Está documentado en `docs/alcance.md` y la FAQ lo declara. |
| ¿Escala? | 24 documentos y ~135 chunks: el índice se cachea y el arranque es de segundos. La capa extendida existe para crecer, con índice precalculado. |
| ¿Qué no hace? | No tiene memoria conversacional, no responde precios ni disponibilidad, y no cubre contenido autenticado ni PDFs completos. |

## Cierre (30 segundos)

> «El sistema responde con el corpus de la empresa, cita cada dato, distingue fuente oficial
> de prensa y prefiere decir que no sabe antes que inventar. El pipeline que alimenta ese
> corpus es reproducible y respeta `robots.txt`. El siguiente paso natural es ampliar el
> corpus con los estados financieros en PDF y automatizar la evaluación.»
