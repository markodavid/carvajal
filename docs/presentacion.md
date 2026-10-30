# Guion de sustentación — 15 minutos (demo en vivo, sin PowerPoint)

> Proyecto: **Carvajal Corpus** — sistema Q&A basado en RAG.
> Regla del curso: **no se permiten presentaciones de PowerPoint**. La sustentación
> se apoya en la demo funcional y, si se necesita apoyo visual, en este documento
> y el repositorio.

## Preparación previa (5 minutos antes)

```bash
# 1. Dependencias y entorno
uv sync

# 2. Embeddings locales (Ollama)
ollama serve
ollama pull nomic-embed-text

# 3. LLM vía DeepSeek (PowerShell)
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "<clave>"
$env:DEEPSEEK_MODEL = "deepseek-chat"

# 4. Verificar el corpus y lanzar la interfaz
uv run carvajal status
make app
```

Checklist:

- [ ] La app abre en `http://localhost:8501`.
- [ ] Una pregunta de prueba responde en menos de ~30 s.
- [ ] Una pregunta fuera de alcance responde "no lo sé".
- [ ] `docs/resultados.md` ya generado con `make eval` (plan B si falla la red).

## Guion minuto a minuto

| Tiempo | Bloque | Qué decir / mostrar |
|---|---|---|
| 0:00–2:00 | **Problema y solución** | La información de Carvajal está dispersa en su sitio; se necesita un canal automatizado y preciso. Solución: Q&A con RAG como núcleo de un futuro chatbot. |
| 2:00–5:00 | **Datos** | Scraping respetuoso (21 semillas, `robots.txt`), capas bronze/silver/gold, extractor DOM propio y la corrección clave: de 2.45 MB a 89 KB de texto limpio. *Chunking* 1000/200 y FAISS k=5. |
| 5:00–8:00 | **Modelado** | Embeddings `nomic-embed-text` (Ollama), LLM DeepSeek vía API (configurable a Ollama/Claude), FAISS persistido y diseño del prompt: núcleo consolidado + reglas anti-alucinación + temperatura 0. Mencionar la capa extendida (485 documentos del corpus del compañero) que solo se recupera y se cita. |
| 8:00–13:00 | **Demo en vivo** | Streamlit: 6 preguntas (ver abajo). Mostrar también el comando `uv run carvajal ask "..."` como respaldo. |
| 13:00–15:00 | **Resultados y cierre** | Tabla de `docs/resultados.md`, calidad de respuestas, limitaciones (corpus acotado, sin memoria conversacional, evaluación manual) y siguientes pasos (más fuentes, evaluación automática). |

## Preguntas sugeridas para la demo

1. **Del alcance:** "¿En qué año y ciudad fue fundada Carvajal?"
2. **Específica de negocio:** "¿Qué es Bioform y a qué industria está dirigido?"
3. **De estructura:** "¿Cuáles son los cuatro sectores en los que opera Carvajal?"
4. **De sostenibilidad:** "¿Qué iniciativas de sostenibilidad adelanta Carvajal?"
5. **De la capa extendida:** "¿Qué productos ofrece Carvajal Empaques en México?"
   → debe citar el dominio y marcar la fuente como colaborador.
6. **Fuera de alcance (abstención):** "¿Cuál es la capital de Francia?"
   → debe responder que no lo sabe o que no está en el corpus.

## Preguntas esperadas del jurado

| Pregunta | Respuesta breve |
|---|---|
| ¿Por qué RAG y no *fine-tuning*? | RAG no requiere reentrenar, es auditable (cita fuentes) y se actualiza regenerando el corpus. |
| ¿Por qué FAISS y no una base vectorial? | El tamaño actual (≈2.100 fragmentos) cabe en un índice local sin infraestructura; para producción se migra a Chroma/pgvector/Qdrant. |
| ¿Cómo evitan alucinaciones? | Prompt estricto (solo contexto), temperatura 0, fallback explícito "no lo sé" y núcleo consolidado en el sistema. |
| ¿Qué pasa si el corpus crece? | Se mantiene RAG con recuperación (k=5): el núcleo entra al prompt y la capa extendida solo se recupera; no se mete todo el corpus en el contexto. |
| ¿Cómo evaluaron la calidad? | 25 preguntas en `data/questions.json`, ejecutadas con `make eval`; criterios de exactitud, coherencia, fidelidad y abstención. |
| ¿Funciona sin internet/API? | Sí, con Ollama (`LLM_PROVIDER=ollama`, `llama3.2`), aunque los embeddings también requieren Ollama local. |

## Plan B (si falla la demo en vivo)

- Mostrar `docs/resultados.md` (resultados ya generados).
- Ejecutar por CLI: `uv run carvajal ask "..."` con la misma configuración.
- Si no hay red, cambiar a `LLM_PROVIDER=ollama` y usar el modelo local.
