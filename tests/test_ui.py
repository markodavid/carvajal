"""Pruebas de los helpers de la interfaz (sin levantar Streamlit)."""

from carvajal.config import EXTERNAL_SEEDS, SEEDS
from carvajal.pipeline import CaptureEvent, CaptureReport
from carvajal.ui import (
    STAGE_LABELS,
    STAGE_SEQUENCE,
    advance_stage,
    corpus_metrics,
    discarded_rows,
    format_event,
    render_diagram,
    report_metrics,
    scope_seeds,
    source_label,
)


def test_scope_seeds_selecciona_el_alcance() -> None:
    """Cada alcance devuelve exactamente sus semillas."""

    assert scope_seeds("oficial") == SEEDS
    assert scope_seeds("terceros") == EXTERNAL_SEEDS
    assert scope_seeds("todo") == (*SEEDS, *EXTERNAL_SEEDS)


def test_stage_labels_cubre_todas_las_etapas_del_pipeline() -> None:
    """Toda etapa emitida por el pipeline tiene etiqueta en la interfaz."""

    etapas = {"descubrir", "robots", "descargar", "extraer", "deduplicar", "enriquecer", "indice"}

    assert etapas <= set(STAGE_LABELS)


def test_format_event_quita_el_esquema_y_antepone_la_etapa() -> None:
    """El evento se presenta como 'etapa: url · detalle'."""

    event = CaptureEvent(
        stage="extraer", url="https://www.carvajal.com/historia/", detail="20 chars"
    )

    formatted = format_event(event)

    assert formatted.stage == STAGE_LABELS["extraer"]
    assert formatted.detail == "www.carvajal.com/historia/ · 20 chars"


def test_report_metrics_resume_la_captura() -> None:
    """Las métricas incluyen descartes, tokens y duración."""

    report = CaptureReport(
        discovered=5,
        fetched=3,
        written=3,
        robots_denied=["https://x/1"],
        duplicates=["https://x/2"],
        chars=1200,
        duration_seconds=4.5,
    )

    metrics = dict(report_metrics(report))

    assert metrics["Descubiertas"] == "5"
    assert metrics["Escritas en Gold"] == "3"
    assert metrics["Descartadas"] == "2"
    assert metrics["Tokens (est.)"] == "300"
    assert metrics["Duración"] == "4.5 s"


def test_discarded_rows_explica_el_motivo() -> None:
    """Cada URL descartada aparece con su motivo."""

    report = CaptureReport(
        robots_denied=["https://x/robots"],
        duplicates=["https://x/dup"],
        errors=["https://x/error: 404"],
    )

    rows = discarded_rows(report)

    assert {row["motivo"] for row in rows} == {
        "robots.txt",
        "duplicada por hash",
        "error de descarga",
    }
    assert len(rows) == 3


def test_corpus_metrics_cuenta_oficiales_y_terceros() -> None:
    """El resumen del corpus separa fuentes oficiales de terceros."""

    documents = [
        _document("https://www.carvajal.com/historia/", "oficial"),
        _document("https://www.larepublica.co/nota", "tercero"),
    ]

    metrics = dict(corpus_metrics(documents))

    assert metrics["Documentos"] == "2"
    assert metrics["Núcleo"] == "2"
    assert metrics["Extendidos"] == "0"
    assert metrics["Oficiales"] == "1"
    assert metrics["Terceros"] == "1"


def test_corpus_metrics_separa_la_capa_extendida() -> None:
    """Los documentos externos se cuentan aparte del núcleo."""

    core = _document("https://www.carvajal.com/historia/", "oficial")
    extended = _document("https://carvajalempaques.com/", "colaborador", layer="extended")

    metrics = dict(corpus_metrics([core, extended]))

    assert metrics["Documentos"] == "2"
    assert metrics["Núcleo"] == "1"
    assert metrics["Extendidos"] == "1"


def test_source_label_describe_procedencia_y_capa() -> None:
    """La fuente citada muestra dominio, tipo, capa y página."""

    document = _document("https://carvajalempaques.com/", "colaborador", layer="extended")
    document.metadata.update({"category": "business", "page": "7"})

    label = source_label(document)

    assert label == "carvajalempaques.com · colaborador · extendido · business · p. 7"


def _document(url: str, source_type: str, layer: str = "core"):
    """Construye un documento LangChain con metadatos mínimos."""

    from urllib.parse import urlparse

    from langchain_core.documents import Document

    domain = urlparse(url).netloc.removeprefix("www.")
    return Document(
        page_content="contenido",
        metadata={"url": url, "domain": domain, "source_type": source_type, "layer": layer},
    )


def test_render_diagram_marca_las_siete_etapas() -> None:
    """El diagrama siempre dibuja las siete etapas, en orden."""

    html = render_diagram({})

    assert html.count("cv-stage") >= 7
    for position, stage in enumerate(STAGE_SEQUENCE, start=1):
        assert STAGE_LABELS[stage].split(" · ")[-1] in html
        assert f'<span class="cv-idx">{position}</span>' in html


def test_render_diagram_refleja_el_estado() -> None:
    """Cada estado se ve distinto: pendiente, activo, listo y error."""

    pendiente = render_diagram({})
    assert "border:1px dashed #C9D2DE" in pendiente

    activo = render_diagram({"descargar": "activo"})
    assert "cv-stage-activo" in activo

    listo = render_diagram({"descargar": "listo"})
    assert "✓" in listo and "cv-stage-activo" not in listo

    error = render_diagram({"descargar": "error"})
    assert "#B3261E" in error


def test_advance_stage_cierra_la_etapa_anterior() -> None:
    """Al entrar en una etapa nueva, la anterior queda completada."""

    states: dict[str, str] = {}

    advance_stage(states, "descubrir")
    assert states["descubrir"] == "activo"

    advance_stage(states, "robots")
    assert states["descubrir"] == "listo"
    assert states["robots"] == "activo"


def test_advance_stage_ignora_etapas_desconocidas() -> None:
    """Un evento de una etapa que no está en el diagrama no rompe el estado."""

    states = {"descubrir": "activo"}

    advance_stage(states, "etapa-inexistente")

    assert states == {"descubrir": "activo"}
