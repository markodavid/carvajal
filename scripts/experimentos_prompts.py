"""Experimentos de prompt engineering sobre el corpus real.

Ejecuta variantes de los tres prompts (Resumen, FAQ y Q&A) con el LLM configurado y
reporta métricas objetivas para compararlas: tamaño de la respuesta, slugs citados,
cifras en pesos y si declara la ausencia de datos.

Uso:
    uv run python scripts/experimentos_prompts.py [--solo resumen|faq|qa]
"""

import argparse
import re
import time

from langchain_core.prompts import ChatPromptTemplate

from carvajal.corpus import load_gold_documents
from carvajal.rag import (
    FAQ_INSTRUCTIONS,
    SUMMARY_INSTRUCTIONS,
    build_llm,
    build_retriever,
    build_system_prompt,
    build_task_prompt,
)


def preguntar(sistema: str, peticion: str, contexto: str = "") -> str:
    """Ejecuta una llamada con el prompt de sistema indicado."""

    humano = f"Contexto:\n{contexto}\n\n{peticion}" if contexto else peticion
    plantilla = ChatPromptTemplate.from_messages([("system", sistema), ("human", "{humano}")])
    mensajes = plantilla.format_messages(humano=humano)
    return str(build_llm().invoke(mensajes).content)


def metricas(texto: str, slugs: set[str]) -> str:
    """Resume de forma objetiva una respuesta del modelo."""

    citados = sorted(slug for slug in slugs if slug in texto)
    cifras = re.findall(r"\$\s?[\d.,]+", texto)
    ausencia = "sí" if re.search(r"no consta|no lo sé|no está en el corpus", texto, re.I) else "no"
    return (
        f"{len(texto):,} chars · {len(citados)} slugs citados · "
        f"{len(cifras)} cifras en $ · declara ausencia: {ausencia}"
    )


def mostrar(nombre: str, texto: str, slugs: set[str]) -> None:
    """Imprime el encabezado, las métricas, el inicio y el cierre de la respuesta."""

    print(f"\n{'=' * 78}\n### {nombre}\n{metricas(texto, slugs)}\n{'-' * 78}")
    print(texto[:900])
    if len(texto) > 1400:
        print("\n[…]\n" + texto[-500:])


def main() -> None:
    """Ejecuta las variantes seleccionadas."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", choices=("resumen", "faq", "qa"))
    args = parser.parse_args()

    documentos = load_gold_documents()
    slugs = {str(documento.metadata["slug"]) for documento in documentos}

    if args.solo in (None, "resumen"):
        peticion = "Redacta el resumen ejecutivo del corpus."
        variantes = {
            "R1 · estructurado con reglas (actual)": build_task_prompt(
                documentos, SUMMARY_INSTRUCTIONS
            ),
            "R2 · sin estructura pedida": build_task_prompt(
                documentos, "Resume en 200 palabras la información más relevante del corpus."
            ),
            "R3 · estructurado sin la regla «no consta»": build_task_prompt(
                documentos,
                SUMMARY_INSTRUCTIONS.replace(
                    "si un dato no consta, escribe «no consta en el corpus»; ", ""
                ),
            ),
        }
        for nombre, sistema in variantes.items():
            inicio = time.time()
            respuesta = preguntar(sistema, peticion)
            print(f"\n[{nombre}] {time.time() - inicio:.1f}s")
            mostrar(nombre, respuesta, slugs)

    if args.solo in (None, "faq"):
        peticion = "Genera la FAQ siguiendo el formato indicado."
        variantes_faq = {
            "F1 · actual (con temas ausentes)": FAQ_INSTRUCTIONS,
            "F2 · sin la sección de temas ausentes": FAQ_INSTRUCTIONS.replace(
                "; si un tema esperable no está (por ejemplo horarios, sedes o línea de "
                "atención), agrégalo al final en la sección 'Temas sin información en el "
                "corpus' explicando qué falta",
                "",
            ),
            "F3 · respuestas de máximo 2 líneas": FAQ_INSTRUCTIONS.replace(
                "respuesta breve (máximo 3 líneas)", "respuesta de máximo 2 líneas"
            ),
        }
        for nombre, instrucciones in variantes_faq.items():
            inicio = time.time()
            respuesta = preguntar(build_task_prompt(documentos, instrucciones), peticion)
            print(f"\n[{nombre}] {time.time() - inicio:.1f}s")
            mostrar(nombre, respuesta, slugs)

    if args.solo in (None, "qa"):
        pregunta = "¿Cuál es el horario de atención y el teléfono de la sede principal?"
        retriever = build_retriever(documentos)
        fragmentos = retriever.invoke(pregunta)
        contexto = "\n\n".join(documento.page_content for documento in fragmentos)
        sistema_actual = build_system_prompt(documentos)
        solo_corpus = sistema_actual.split("=== CORPUS CARVAJAL ===", 1)[1]
        variantes_qa = {
            "Q1 · actual (grounding + citas)": sistema_actual,
            "Q2 · sin reglas anti-alucinación": (
                "Eres un experto en Carvajal. Responde de forma útil y segura. "
                f"=== CORPUS CARVAJAL ==={solo_corpus}"
            ),
            "Q3 · solo fragmentos recuperados": "Responde solo con el contexto adjunto.",
            "Q4 · sin corpus (solo el modelo)": (
                "Eres un experto en Carvajal. Responde de forma útil y segura."
            ),
        }
        for nombre, sistema in variantes_qa.items():
            inicio = time.time()
            contexto_variante = "" if nombre.startswith("Q4") else contexto
            respuesta = preguntar(sistema, pregunta, contexto_variante)
            print(f"\n[{nombre}] {time.time() - inicio:.1f}s")
            mostrar(nombre, respuesta, slugs)


if __name__ == "__main__":
    main()
