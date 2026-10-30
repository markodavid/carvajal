# Prompt engineering: prompts finales y experimentación

> Los tres prompts del asistente (Resumen, FAQ y Q&A), las variantes que se probaron
> sobre el corpus real y qué se decidió con cada resultado.
> Reproducible con `uv run python scripts/experimentos_prompts.py`.

## 1. Metodología

| Elemento | Valor |
|---|---|
| Modelo | `deepseek-chat` (API), temperatura `0` |
| Contexto | Corpus Gold completo: 24 documentos, 95 072 caracteres (≈ 24 000 tokens) |
| Ejecuciones | Una por variante, con el mismo corpus y la misma petición |
| Métricas objetivas | caracteres, slugs de fuente citados, cifras en `$`, mención explícita de ausencia |
| Revisión cualitativa | estructura, utilidad para un cliente primerizo y tono |

Limitación honesta: **una sola corrida por variante** (temperatura 0 reduce la varianza,
pero no la elimina). Las conclusiones son indicios consistentes, no significación
estadística. El script permite repetir y ampliar.

## 2. Prompt de Resumen (tarea «Resumen»)

### Prompt final

```text
Eres el asistente del corpus Carvajal. Redacta un RESUMEN EJECUTIVO del corpus usando
solo la información disponible en él. Estructura obligatoria, en este orden:
(1) Qué es la empresa; (2) Sectores y empresas del grupo; (3) Cifras clave (ingresos,
EBITDA, utilidad y empleo) indicando año y fuente; (4) Tres hitos de la historia;
(5) Presencia geográfica. Reglas: no inventes cifras; si un dato no consta, escribe
«no consta en el corpus»; cita el slug de la fuente entre paréntesis tras cada cifra;
máximo 400 palabras; español de Colombia.

=== CORPUS CARVAJAL ===
### Fuente: <slug> · <dominio> (oficial|tercero)
<cuerpo>
…
```

### Variantes y resultados

| Variante | Caracteres | Slugs citados | ¿Declara datos ausentes? |
|---|---|---|---|
| **R1 · estructurado con reglas (elegida)** | 2 254 | **13** | **Sí** |
| R2 · «resume en 200 palabras» sin estructura | 1 440 | 1 | No |
| R3 · estructurado, sin la regla «no consta» | 2 259 | 10 | No |

### Qué se observó

- **R2** produce un texto correcto y legible, pero **pierde la trazabilidad**: cita una sola
  fuente para ocho cifras. Mezcla datos de 2024 con cifras de septiembre de 2025 sin
  aclarar el corte temporal («presencia en 10-17 países», «a septiembre de 2024 fueron
  $2,8 billones»). Sin estructura, el resumen es más ameno y menos auditable.
- **R3** mantiene la estructura y cita más fuentes, pero **no advierte** que el EBITDA de
  2024 no está en el corpus: simplemente omite el bloque. La regla «no consta» es la que
  convierte una omisión silenciosa en información útil.
- **R1** es la más citable: 13 slugs, cifras con año y una declaración explícita de lo que
  falta. Es la que se usa en `docs/resumen.md`.

**Decisión:** estructura fija + cita por cifra + declaración de ausencia.

## 3. Prompt de FAQ (tarea «FAQ»)

### Prompt final

```text
Eres el asistente del corpus Carvajal. Genera una FAQ para un cliente que contacta a la
empresa por primera vez. Incluye entre 10 y 12 preguntas agrupadas en: Empresa,
Productos y sectores, Historia, Inversión y Contacto. Formato de cada entrada:
**P:** pregunta
**R:** respuesta breve (máximo 3 líneas)
_Fuente:_ slug
Cada entrada lleva exactamente una línea **P:** y una **R:**; no agregues notas,
aclaraciones sueltas ni líneas R vacías. Reglas: responde solo con el corpus y cita el
slug; si un tema esperable no está (por ejemplo horarios, sedes o línea de atención),
agrégalo al final en la sección 'Temas sin información en el corpus' explicando qué
falta; no inventes datos.

=== CORPUS CARVAJAL ===
…
```

### Variantes y resultados

| Variante | Caracteres | Slugs citados | ¿Sección de temas ausentes? |
|---|---|---|---|
| **F1 · actual (elegida)** | 3 485 | **12** | **Sí** (6 temas) |
| F2 · sin la sección de temas ausentes | 2 793 | 12 | **No** |
| F3 · respuestas de máximo 2 líneas | 3 016 | 11 | Sí |

### Qué se observó

- **F2** no inventa, pero **tapa el hueco**: ante «¿cómo contacto a Carvajal?» responde
  «consulte el sitio oficial carvajal.com» citando `noticias`, sin advertir que el corpus
  no tiene teléfono, sedes ni horarios. Es el caso más peligroso: una respuesta que *parece*
  completa.
- **F3** acorta las respuestas (bueno para un cliente) pero **pierde 1 fuente** y algunos
  matices (el cargo del presidente queda sin la fecha «desde 2020»).
- **F1** mantiene 12 fuentes y añade el bloque de seis temas ausentes, que es justo lo que
  la rúbrica valora como transparencia del alcance.

**Decisión:** conservar la sección obligatoria de temas ausentes y el formato P/R/Fuente;
no imponer un límite más corto que 3 líneas.

## 4. Prompt de Q&A (tarea «Asistente»)

### Prompt final

```text
Eres el asistente del corpus Carvajal. Tu fuente es el CORPUS CARVAJAL incluido en este
mensaje de sistema, complementado con los fragmentos recuperados que se adjuntan.
Responde únicamente con esa información. Sé completo: si la pregunta pide una lista,
cronología o explicación, incluye todos los elementos relevantes del corpus. Si la
respuesta no está en el corpus, di claramente que no lo sabes; si solo hay información
parcial, responde con lo disponible e indica qué falta. No inventes datos ni uses
conocimiento externo. Cita las fuentes consultadas. Distingue siempre entre fuentes
oficiales (carvajal.com) y de terceros (prensa, analistas): si una cifra proviene de un
tercero, dilo y menciona el medio y la fecha.

=== CORPUS CARVAJAL ===
…
```

Pregunta de prueba, deliberadamente **fuera del alcance**: *«¿Cuál es el horario de atención
y el teléfono de la sede principal?»*.

| Variante | Caracteres | Slugs | ¿Declara que no lo sabe? | ¿Usa conocimiento externo? |
|---|---|---|---|---|
| **Q1 · actual (elegida)** | 699 | 2 | **Sí** («No lo sé») | No |
| Q2 · sin reglas anti-alucinación | 841 | 1 | No explícito | No |
| Q3 · solo fragmentos recuperados | 100 | 0 | Parcial («el contexto no lo incluye») | No |
| Q4 · sin corpus, solo el modelo | 784 | 0 | No | **Sí** (nombra divisiones del grupo) |

### Qué se observó

- **Q1** responde en una línea que no lo sabe, explica qué cubre el corpus y remite a los
  canales oficiales. Es la respuesta que queremos.
- **Q2** tampoco inventa un teléfono, pero **no dice «no lo sé»**: da una lista de
  recomendaciones genéricas. Menos claro para el usuario y sin anclaje explícito.
- **Q3** demuestra el valor de consolidar el corpus en el sistema: con solo 5 fragmentos,
  el modelo se limita a decir que el contexto no alcanza (100 caracteres). El corpus
  completo es lo que permite explicar *por qué* falta el dato.
- **Q4** es el caso que justifica las reglas: sin corpus, el modelo **usa conocimiento
  externo** (enumera divisiones del grupo) sin citar nada. En esta prueba acertó, pero es
  exactamente el comportamiento que no se puede auditar.

**Decisión:** mantener «responde solo con el corpus», la instrucción explícita de decir que
no lo sabe y la cita de fuente con distinción oficial/tercero.

## 5. Reglas anti-alucinación y su función

| Regla | Qué evita | Dónde se ve |
|---|---|---|
| «Responde únicamente con esa información» | Conocimiento externo no auditable | Q4 frente a Q1 |
| «Si la respuesta no está, di que no lo sabes» | Respuestas plausibles pero vacías | Q2 frente a Q1 |
| «No inventes datos ni cifras» | Cifras sin respaldo | R1 declara EBITDA 2024 ausente |
| «Cita el slug / medio y fecha» | Respuestas no verificables | R1 cita 13 fuentes; R2 solo 1 |
| «Temas sin información en el corpus» | Huecos de cobertura invisibles | F1 frente a F2 |
| Temperatura `0` | Variación entre corridas | Todas las ejecuciones |

## 6. Prompts descartados y por qué

- **«Resume en 200 palabras»**: más legible, pero sin estructura ni trazabilidad (R2).
- **FAQ sin declaración de ausencias**: oculta los huecos de contacto y sedes (F2).
- **Respuestas de 2 líneas**: pierde matices y una fuente (F3).
- **Solo fragmentos recuperados**: el asistente no puede explicar el alcance (Q3).
- **Modelo sin corpus**: responde con conocimiento externo (Q4).

## 7. Reproducir los experimentos

```bash
uv run python scripts/experimentos_prompts.py              # las tres tareas
uv run python scripts/experimentos_prompts.py --solo qa    # solo Q&A
```

El script imprime, por variante: tiempo, caracteres, slugs citados, cifras y si declara
ausencia, además del inicio y el cierre de la respuesta.
