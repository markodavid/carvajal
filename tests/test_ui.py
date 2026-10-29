"""Pruebas de los helpers de la interfaz (sin levantar Streamlit)."""

from carvajal.config import EXTERNAL_SEEDS, SEEDS
from carvajal.pipeline import CaptureEvent, CaptureReport
from carvajal.ui import (
    STAGE_LABELS,
    corpus_metrics,
    discarded_rows,
    format_event,
    report_metrics,
    scope_seeds,
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
    assert metrics["Oficiales"] == "1"
    assert metrics["Terceros"] == "1"


def _document(url: str, source_type: str):
    """Construye un documento LangChain con metadatos mínimos."""

    from langchain_core.documents import Document

    return Document(page_content="contenido", metadata={"url": url, "source_type": source_type})
