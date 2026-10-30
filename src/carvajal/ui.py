"""Interfaz web (Streamlit): pipeline visible con identidad de Carvajal y asistente RAG."""

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import streamlit as st
from langchain_core.documents import Document

from carvajal.config import EXTERNAL_SEEDS, LAYER_EXTENDED, LLM_PROVIDER, SEEDS
from carvajal.corpus import load_gold_documents
from carvajal.fetching import WebClient
from carvajal.pipeline import CaptureEvent, CaptureReport, capture

LOGO_PATH = Path("assets") / "carvajal-logo.svg"

# Paleta tomada del sitio oficial (tokens de Elementor y colores del logo).
BRAND = {
    "cian": "#00B5E5",
    "oliva": "#80A41B",
    "naranja": "#ED7004",
    "morado": "#62358C",
    "morado_oscuro": "#61368C",
    "azul": "#003A5D",
    "azul_profundo": "#004568",
    "verde": "#015625",
    "verde_medio": "#188D40",
    "rojo": "#D7510C",
    "error": "#B3261E",
}

SCOPE_OPTIONS = {
    f"Todo el corpus ({len(SEEDS) + len(EXTERNAL_SEEDS)} URLs)": "todo",
    f"Solo sitio oficial ({len(SEEDS)} URLs)": "oficial",
    f"Solo fuentes de terceros ({len(EXTERNAL_SEEDS)} URLs)": "terceros",
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

STAGE_SEQUENCE = tuple(STAGE_LABELS)

STAGE_COLORS = {
    "descubrir": BRAND["cian"],
    "robots": BRAND["oliva"],
    "descargar": BRAND["azul"],
    "extraer": BRAND["morado"],
    "deduplicar": BRAND["naranja"],
    "enriquecer": BRAND["verde"],
    "indice": BRAND["rojo"],
}

STAGE_ICONS = {"pendiente": "○", "activo": "◐", "listo": "✓", "error": "!"}


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    """Devuelve el logo de Carvajal embebido como ``data:`` URI."""

    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def brand_header() -> None:
    """Dibuja el encabezado con el logo y la paleta de Carvajal."""

    logo = logo_data_uri()
    st.markdown(
        f"""
        <div class="cv-header">
          <img class="cv-logo" src="{logo}" alt="Carvajal" />
          <div class="cv-titles">
            <h1>Corpus web y asistente</h1>
            <p>Scraping visible por etapas · RAG con fuentes citadas ·
               modelo <code>{LLM_PROVIDER}</code></p>
          </div>
        </div>
        <div class="cv-bands">
          <span style="background:{BRAND["cian"]}"></span>
          <span style="background:{BRAND["oliva"]}"></span>
          <span style="background:{BRAND["naranja"]}"></span>
          <span style="background:{BRAND["morado"]}"></span>
          <span style="background:{BRAND["azul"]}"></span>
          <span style="background:{BRAND["verde"]}"></span>
          <span style="background:{BRAND["rojo"]}"></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def brand_css() -> None:
    """Inyecta los estilos de la marca y del diagrama de bloques."""

    st.markdown(
        f"""
        <style>
        .cv-header {{ display:flex; align-items:center; gap:22px; padding:4px 0 10px; }}
        .cv-logo {{ height:52px; width:auto; }}
        .cv-titles h1 {{ font-size:1.65rem; margin:0; color:{BRAND["azul"]}; }}
        .cv-titles p {{ margin:2px 0 0; color:#5B6B7F; font-size:0.86rem; }}
        .cv-bands {{ display:flex; gap:4px; margin-bottom:14px; }}
        .cv-bands span {{ height:5px; flex:1; border-radius:3px; }}
        .cv-diagram {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin:6px 0; }}
        .cv-stage {{ flex:1 1 118px; min-width:112px; border-radius:10px; padding:9px 8px;
                     text-align:center; font-size:0.78rem; font-weight:600; line-height:1.25; }}
        .cv-stage .cv-idx {{ display:block; font-size:0.64rem; opacity:0.75; }}
        .cv-stage .cv-ic {{ display:block; font-size:0.9rem; margin-top:2px; }}
        .cv-arrow {{ color:#B9C4D2; font-size:0.9rem; }}
        .cv-caption {{ font-size:0.75rem; color:#5B6B7F; margin-top:2px; }}
        @keyframes cv-pulse {{ 0%{{opacity:1;}} 50%{{opacity:0.72;}} 100%{{opacity:1;}} }}
        .cv-stage-activo {{ animation:cv-pulse 1.1s ease-in-out infinite; }}
        div[data-testid="stMetricValue"] {{ color:{BRAND["azul"]}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def advance_stage(states: dict[str, str], stage: str) -> dict[str, str]:
    """Marca la etapa como activa y la anterior como completada.

    Args:
        states: Estado actual por etapa (``pendiente``, ``activo``, ``listo`` o ``error``).
        stage: Etapa que acaba de emitir un evento.

    Returns:
        El mismo diccionario, actualizado.
    """

    if stage not in STAGE_SEQUENCE:
        return states
    position = STAGE_SEQUENCE.index(stage)
    for earlier in STAGE_SEQUENCE[:position]:
        if states.get(earlier) == "activo":
            states[earlier] = "listo"
    states[stage] = "activo"
    return states


def render_diagram(states: dict[str, str], caption: str = "") -> str:
    """Construye el HTML del diagrama de bloques del pipeline.

    Args:
        states: Estado por etapa.
        caption: Texto de apoyo bajo el diagrama.

    Returns:
        HTML listo para ``st.markdown``.
    """

    blocks: list[str] = []
    for position, stage in enumerate(STAGE_SEQUENCE, start=1):
        status = states.get(stage, "pendiente")
        color = STAGE_COLORS[stage]
        if status == "pendiente":
            style = "background:#FFFFFF;color:#8A94A6;border:1px dashed #C9D2DE;"
            css_class = ""
        elif status == "error":
            style = f"background:{BRAND['error']};color:#FFFFFF;border:1px solid {BRAND['error']};"
            css_class = ""
        else:
            style = f"background:{color};color:#FFFFFF;border:1px solid {color};"
            css_class = " cv-stage-activo" if status == "activo" else ""
        label = STAGE_LABELS[stage].split(" · ")[-1]
        blocks.append(
            f'<div class="cv-stage{css_class}" style="{style}">'
            f'<span class="cv-idx">{position}</span>{label}'
            f'<span class="cv-ic">{STAGE_ICONS[status]}</span></div>'
        )
        if position < len(STAGE_SEQUENCE):
            blocks.append('<span class="cv-arrow">▸</span>')

    caption_html = f'<div class="cv-caption">{caption}</div>' if caption else ""
    return f'<div class="cv-diagram">{"".join(blocks)}</div>{caption_html}'


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
    """Resume el corpus cargado: núcleo, capa extendida y tamaño."""

    core = [
        document
        for document in documents
        if document.metadata.get("layer", "core") != LAYER_EXTENDED
    ]
    official = sum(1 for document in core if document.metadata.get("source_type") == "oficial")
    chars = sum(len(document.page_content) for document in documents)
    return [
        ("Documentos", f"{len(documents)}"),
        ("Núcleo", f"{len(core)}"),
        ("Extendidos", f"{len(documents) - len(core)}"),
        ("Oficiales", f"{official}"),
        ("Terceros", f"{len(core) - official}"),
        ("Caracteres", f"{chars:,}"),
        ("Tokens (est.)", f"{round(chars / 4):,}"),
    ]


def render_pipeline_tab(documents: list[Document]) -> None:
    """Dibuja la pestaña del pipeline con su ejecución y métricas."""

    st.subheader("Corpus actual")
    metrics = corpus_metrics(documents)
    for column, (label, value) in zip(st.columns(len(metrics)), metrics, strict=True):
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

    diagram = st.empty()
    diagram.markdown(
        render_diagram({}, "Las etapas se iluminan a medida que avanza la captura."),
        unsafe_allow_html=True,
    )

    if not submitted:
        st.caption("Las métricas se actualizan al ejecutar la captura.")
        return

    seeds = scope_seeds(SCOPE_OPTIONS[scope_label])[:limit]
    total_steps = 2 + len(seeds) * 6
    progress = st.progress(0.0)
    log = st.empty()
    lines: list[str] = []
    states: dict[str, str] = {}
    processed = 0

    with st.status("Ejecutando pipeline…", expanded=True) as status:

        def on_event(event: CaptureEvent) -> None:
            nonlocal processed
            formatted = format_event(event)
            lines.append(f"{formatted.stage}: {formatted.detail}")
            log.code("\n".join(lines[-10:]), language="text")
            advance_stage(states, event.stage)
            if event.stage == "enriquecer":
                processed += 1
            caption = f"Etapa {STAGE_SEQUENCE.index(event.stage) + 1} de 7"
            if event.url:
                caption += f" · {event.url.replace('https://', '')}"
            if processed:
                caption += f" · {processed} página(s) procesadas"
            diagram.markdown(render_diagram(states, caption), unsafe_allow_html=True)
            progress.progress(min(len(lines) / total_steps, 1.0))

        report = capture(seeds, on_event=on_event, client=_client(respect_robots))
        for stage in STAGE_SEQUENCE:
            states[stage] = "listo"
        diagram.markdown(
            render_diagram(
                states,
                f"Captura completada: {report.written} documento(s) en {report.duration_seconds} s",
            ),
            unsafe_allow_html=True,
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


def render_summary_tab(documents: list[Document]) -> None:
    """Dibuja la tarea «Resumen»: síntesis del corpus con cifras y fuentes."""

    st.subheader("Resumen ejecutivo del corpus")
    st.caption(
        "Tarea de LLM: sintetiza el corpus completo (empresa, sectores, cifras clave, "
        "historia y presencia geográfica) citando la fuente de cada dato."
    )
    focus = st.text_input(
        "Enfocar en (opcional)",
        placeholder="por ejemplo: sector de empaques",
    )
    if st.button("Generar resumen"):
        with st.spinner("Redactando el resumen con el corpus completo…"):
            st.session_state["resumen"] = _rag().summarize(documents, focus=focus or None)

    content = st.session_state.get("resumen")
    if content:
        st.markdown(content)
        st.download_button(
            "Descargar resumen.md",
            data=content,
            file_name="resumen.md",
            mime="text/markdown",
        )
    else:
        st.info("Genera el resumen para verlo aquí.")


def render_faq_tab(documents: list[Document]) -> None:
    """Dibuja la tarea «FAQ»: preguntas frecuentes de un cliente primerizo."""

    st.subheader("FAQ para un cliente que contacta por primera vez")
    st.caption(
        "Tarea de LLM: genera entre 10 y 12 preguntas con respuesta y fuente, agrupadas "
        "por tema, y declara los temas que el corpus no cubre."
    )
    if st.button("Generar FAQ"):
        with st.spinner("Redactando la FAQ con el corpus completo…"):
            st.session_state["faq"] = _rag().generate_faq(documents)

    content = st.session_state.get("faq")
    if content:
        st.markdown(content)
        st.download_button(
            "Descargar faq.md",
            data=content,
            file_name="faq.md",
            mime="text/markdown",
        )
    else:
        st.info("Genera la FAQ para verla aquí.")


def source_label(document: Document) -> str:
    """Describe una fuente recuperada con su procedencia y capa."""

    metadata = document.metadata
    layer = "extendido" if metadata.get("layer") == LAYER_EXTENDED else "núcleo"
    parts = [
        str(metadata.get("domain", "carvajal.com")),
        str(metadata.get("source_type", "oficial")),
        layer,
    ]
    category = str(metadata.get("category", ""))
    if category:
        parts.append(category)
    page = metadata.get("page")
    if page:
        parts.append(f"p. {page}")
    return " · ".join(parts)


def render_assistant_tab(documents: list[Document]) -> None:
    """Dibuja la pestaña del asistente (Q&A con fuentes citadas)."""

    if not _rag().index_is_fresh(documents):
        st.warning(
            "El índice vectorial no corresponde al corpus actual: la primera pregunta "
            "lo reconstruirá y puede tardar varios minutos."
        )

    st.caption(
        "El prompt consolida el núcleo y la recuperación consulta el núcleo y la capa "
        "extendida; cada respuesta muestra de dónde viene cada fragmento."
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
        st.session_state["qa"] = {
            "question": question.strip(),
            "answer": answer,
            "sources": sources,
        }

    saved = st.session_state.get("qa")
    if not saved:
        return
    st.markdown(saved["answer"])
    with st.expander(f"Fuentes citadas ({len(saved['sources'])})"):
        for document in saved["sources"]:
            st.markdown(f"**{source_label(document)}**")
            url = str(document.metadata.get("url", ""))
            if url:
                st.caption(url)
            st.caption(document.page_content[:400].replace("\n", " ") + "…")


def _rag() -> ModuleType:
    """Importa el stack RAG solo cuando se usa.

    ``langchain``, ``faiss`` y los clientes de LLM tardan decenas de segundos en importarse
    en este equipo, así que mantenerlos fuera del arranque deja la pestaña del pipeline
    disponible de inmediato.
    """

    from carvajal import rag

    return rag


def _answer(question: str, documents: list[Document]) -> tuple[str, list[Document]]:
    """Resuelve la pregunta usando el retriever cacheado en la sesión."""

    rag = _rag()
    retriever = st.session_state.get("retriever")
    if retriever is None:
        with st.spinner("Preparando el índice por primera vez…"):
            retriever = rag.build_retriever(documents)
        st.session_state["retriever"] = retriever

    system_prompt = st.session_state.get("system_prompt")
    if system_prompt is None:
        system_prompt = rag.build_system_prompt(documents)
        st.session_state["system_prompt"] = system_prompt

    return rag.ask_with_sources(question, retriever, system_prompt=system_prompt)


def main() -> None:
    """Punto de entrada de la interfaz Streamlit."""

    st.set_page_config(
        page_title="Carvajal — Corpus y asistente",
        page_icon="🟢",
        layout="wide",
    )
    brand_css()
    brand_header()

    documents = load_gold_documents()
    pipeline_tab, summary_tab, faq_tab, assistant_tab = st.tabs(
        ["Pipeline de scraping", "Resumen", "FAQ", "Asistente"]
    )
    with pipeline_tab:
        render_pipeline_tab(documents)
    with summary_tab:
        render_summary_tab(documents)
    with faq_tab:
        render_faq_tab(documents)
    with assistant_tab:
        render_assistant_tab(documents)


if __name__ == "__main__":
    main()
