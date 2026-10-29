"""Interfaz web (Streamlit): pipeline de scraping visible y asistente RAG."""

from dataclasses import dataclass

import streamlit as st
from langchain_core.documents import Document

from carvajal.config import EXTERNAL_SEEDS, LLM_PROVIDER, SEEDS
from carvajal.fetching import WebClient
from carvajal.pipeline import CaptureEvent, CaptureReport, capture
from carvajal.rag import (
    ask_with_sources,
    build_retriever,
    build_system_prompt,
    index_is_fresh,
    load_gold_documents,
)

SCOPE_OPTIONS = {
    "Todo el corpus (21 URLs)": "todo",
    "Solo sitio oficial (15 URLs)": "oficial",
    "Solo fuentes de terceros (6 URLs)": "terceros",
}

STAGE_LABELS = {
    "descubrir": "1 · Descubrir semillas",
    "robots": "2 · Verificar robots.txt",
    "descargar": "3 · Descargar HTML",
    "extraer": "4 · Extraer Markdown",
    "deduplicar": "5 · Deduplicar",
    "enriquecer": "6 · Enriquecer metadatos",
    "indice": "7 · Escribir índice",
}


@dataclass(frozen=True)
class UiEvent:
    """Evento de progreso ya formateado para la interfaz."""

    stage: str
    detail: str


def scope_seeds(scope: str) -> tuple[str, ...]:
    """Devuelve las semillas según el alcance elegido en la interfaz."""

    if scope == "oficial":
        return SEEDS
    if scope == "terceros":
        return EXTERNAL_SEEDS
    return (*SEEDS, *EXTERNAL_SEEDS)


def format_event(event: CaptureEvent) -> UiEvent:
    """Traduce un evento del pipeline a una línea legible."""

    label = STAGE_LABELS.get(event.stage, event.stage)
    target = event.url.replace("https://", "") if event.url else ""
    detail = f" · {event.detail}" if event.detail else ""
    return UiEvent(stage=label, detail=f"{target}{detail}".strip(" ·"))


def report_metrics(report: CaptureReport) -> list[tuple[str, str]]:
    """Resume las métricas de la captura para mostrarlas como tarjetas."""

    return [
        ("Descubiertas", f"{report.discovered}"),
        ("Descargadas", f"{report.fetched}"),
        ("Escritas en Gold", f"{report.written}"),
        ("Descartadas", f"{report.discarded}"),
        ("Caracteres", f"{report.chars:,}"),
        ("Tokens (est.)", f"{report.tokens_estimate:,}"),
        ("Duración", f"{report.duration_seconds} s"),
    ]


def discarded_rows(report: CaptureReport) -> list[dict[str, str]]:
    """Lista las URLs descartadas con el motivo del descarte."""

    rows = [{"url": url, "motivo": "robots.txt"} for url in report.robots_denied]
    rows += [{"url": url, "motivo": "duplicada por hash"} for url in report.duplicates]
    rows += [{"url": error, "motivo": "error de descarga"} for error in report.errors]
    return rows


def corpus_metrics(documents: list[Document]) -> list[tuple[str, str]]:
    """Resume el corpus Gold cargado desde disco."""

    official = sum(1 for document in documents if document.metadata.get("source_type") == "oficial")
    chars = sum(len(document.page_content) for document in documents)
    return [
        ("Documentos", f"{len(documents)}"),
        ("Oficiales", f"{official}"),
        ("Terceros", f"{len(documents) - official}"),
        ("Caracteres", f"{chars:,}"),
        ("Tokens (est.)", f"{round(chars / 4):,}"),
    ]


def render_pipeline_tab(documents: list[Document]) -> None:
    """Dibuja la pestaña del pipeline con su ejecución y métricas."""

    st.subheader("Corpus actual")
    columns = st.columns(5)
    for column, (label, value) in zip(columns, corpus_metrics(documents), strict=True):
        column.metric(label, value)

    st.info(
        "El pipeline ejecuta siete etapas sobre las semillas configuradas: descubrir, "
        "verificar `robots.txt`, descargar, extraer, deduplicar, enriquecer e indexar. "
        "El rate limit es de 1 s por host."
    )

    with st.form("captura"):
        scope_label = st.selectbox("Alcance", list(SCOPE_OPTIONS))
        total_seeds = len(SEEDS) + len(EXTERNAL_SEEDS)
        limit = st.slider(
            "Máximo de URLs a procesar",
            min_value=1,
            max_value=total_seeds,
            value=min(5, total_seeds),
        )
        respect_robots = st.checkbox("Respetar robots.txt", value=True)
        submitted = st.form_submit_button("Ejecutar captura")

    if not submitted:
        st.caption("Las métricas se actualizan al ejecutar la captura.")
        return

    seeds = scope_seeds(SCOPE_OPTIONS[scope_label])[:limit]
    total_steps = 2 + len(seeds) * 6
    progress = st.progress(0.0)
    log = st.empty()
    lines: list[str] = []

    with st.status("Ejecutando pipeline…", expanded=True) as status:

        def on_event(event: CaptureEvent) -> None:
            formatted = format_event(event)
            lines.append(f"{formatted.stage}: {formatted.detail}")
            log.code("\n".join(lines[-12:]), language="text")
            progress.progress(min(len(lines) / total_steps, 1.0))

        report = capture(
            seeds,
            on_event=on_event,
            client=_client(respect_robots),
        )
        status.update(
            label=f"Captura completada en {report.duration_seconds} s",
            state="complete",
        )

    st.subheader("Métricas de la captura")
    columns = st.columns(len(report_metrics(report)))
    for column, (label, value) in zip(columns, report_metrics(report), strict=True):
        column.metric(label, value)

    discarded = discarded_rows(report)
    if discarded:
        st.warning(f"{len(discarded)} URL(s) descartadas")
        st.dataframe(discarded, width="stretch")
    else:
        st.success("Ninguna URL fue descartada: todas las semillas se capturaron.")

    if report.pages:
        st.subheader("Documentos escritos en data/gold/")
        st.dataframe(
            [
                {
                    "documento": page.slug,
                    "sección": page.section,
                    "caracteres": len(page.markdown),
                    "tokens (est.)": page.tokens_estimate,
                }
                for page in report.pages
            ],
            width="stretch",
        )


def _client(respect_robots: bool) -> WebClient:
    """Construye el cliente HTTP con la política elegida en la interfaz."""

    return WebClient(respect_robots=respect_robots)


def render_assistant_tab(documents: list[Document]) -> None:
    """Dibuja la pestaña del asistente (Q&A con fuentes citadas)."""

    if not index_is_fresh(documents):
        st.warning(
            "El índice vectorial no corresponde al corpus actual: la primera pregunta "
            "lo reconstruirá y puede tardar varios minutos."
        )

    question = st.text_area(
        "Pregunta",
        placeholder="Escribe tu pregunta sobre el corpus…",
        height=120,
    )
    if st.button("Responder"):
        if not question.strip():
            st.warning("Escribe una pregunta antes de responder.")
            return
        with st.spinner("Buscando en el corpus y consultando el modelo…"):
            answer, sources = _answer(question.strip(), documents)
        st.markdown(answer)
        with st.expander(f"Fuentes citadas ({len(sources)})"):
            for document in sources:
                domain = document.metadata.get("domain", "carvajal.com")
                kind = document.metadata.get("source_type", "oficial")
                st.markdown(f"**{domain}** · {kind}")
                st.caption(document.page_content[:400].replace("\n", " ") + "…")


def _answer(question: str, documents: list[Document]) -> tuple[str, list[Document]]:
    """Resuelve la pregunta usando el retriever cacheado en la sesión."""

    retriever = st.session_state.get("retriever")
    if retriever is None:
        with st.spinner("Preparando el índice por primera vez…"):
            retriever = build_retriever(documents)
        st.session_state["retriever"] = retriever

    system_prompt = st.session_state.get("system_prompt")
    if system_prompt is None:
        system_prompt = build_system_prompt(documents)
        st.session_state["system_prompt"] = system_prompt

    return ask_with_sources(question, retriever, system_prompt=system_prompt)


def main() -> None:
    """Punto de entrada de la interfaz Streamlit."""

    st.set_page_config(page_title="Carvajal — Corpus y asistente", layout="wide")
    st.title("Carvajal — Corpus web y asistente")
    st.caption(f"Scraping visible + RAG sobre el corpus · modelo: `{LLM_PROVIDER}`")

    documents = load_gold_documents()
    pipeline_tab, assistant_tab = st.tabs(["Pipeline de scraping", "Asistente"])
    with pipeline_tab:
        render_pipeline_tab(documents)
    with assistant_tab:
        render_assistant_tab(documents)


if __name__ == "__main__":
    main()
