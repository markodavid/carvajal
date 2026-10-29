"""Orquestación del pipeline: capas Bronze → Silver → Gold con reporte de métricas."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from carvajal.config import (
    GOLD_DIR,
    INDEX_FILE,
    MIN_DEDUPE_CHARS,
    PROCESSED_DIR,
    RAW_DIR,
)
from carvajal.extracting import html_title, html_to_markdown
from carvajal.fetching import Fetcher, FetchError, RobotsDenied, WebClient
from carvajal.gold import index_entry, write_bronze, write_gold, write_index, write_silver
from carvajal.models import CapturedPage


@dataclass(frozen=True)
class CaptureEvent:
    """Evento de progreso emitido durante la captura (lo consume la interfaz)."""

    stage: str
    url: str = ""
    detail: str = ""


ProgressHook = Callable[[CaptureEvent], None]


@dataclass
class CaptureReport:
    """Métricas de una ejecución del pipeline (se muestran en la CLI y en la UI)."""

    discovered: int = 0
    fetched: int = 0
    written: int = 0
    robots_denied: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    pages: list[CapturedPage] = field(default_factory=list)
    chars: int = 0
    duration_seconds: float = 0.0

    @property
    def tokens_estimate(self) -> int:
        """Estimación de tokens del corpus capturado (≈4 caracteres por token)."""

        return round(self.chars / 4)

    @property
    def discarded(self) -> int:
        """Total de URLs descartadas (robots, duplicadas o con error)."""

        return len(self.robots_denied) + len(self.duplicates) + len(self.errors)


def capture(
    seeds: tuple[str, ...] | list[str],
    client: Fetcher | None = None,
    gold_dir: Path | None = None,
    raw_dir: Path | None = None,
    processed_dir: Path | None = None,
    index_file: Path | None = None,
    on_event: ProgressHook | None = None,
) -> CaptureReport:
    """Ejecuta el ciclo descubrir → extraer → limpiar → deduplicar → enriquecer.

    Args:
        seeds: Semillas de URLs a capturar.
        client: Cliente HTTP (se reusa una sola sesión y su caché de robots).
        gold_dir: Directorio del entregable Gold (por defecto ``data/gold``).
        raw_dir: Directorio de la capa Bronze (por defecto ``data/raw``).
        processed_dir: Directorio de la capa Silver (por defecto ``data/processed``).
        index_file: Ruta del índice JSONL (por defecto ``data/gold/index.jsonl``).
        on_event: Gancho opcional que recibe cada evento de progreso por etapa.

    Returns:
        Reporte con las métricas de la ejecución y las páginas capturadas.
    """

    started = time.monotonic()
    web_client = client or WebClient()
    target_gold = gold_dir or GOLD_DIR
    target_raw = raw_dir or RAW_DIR
    target_processed = processed_dir or PROCESSED_DIR
    target_index = index_file or INDEX_FILE

    report = CaptureReport(discovered=len(seeds))
    seen_hashes: set[str] = set()
    entries: list[dict[str, str | int]] = []
    _emit(on_event, "descubrir", detail=f"{len(seeds)} semillas")

    for url in seeds:
        if not web_client.can_fetch(url):
            report.robots_denied.append(url)
            _emit(on_event, "robots", url, "bloqueada por robots.txt")
            continue
        _emit(on_event, "robots", url, "permitida")
        try:
            html = web_client.fetch(url)
        except RobotsDenied:
            report.robots_denied.append(url)
            _emit(on_event, "robots", url, "bloqueada por robots.txt")
            continue
        except FetchError as error:
            report.errors.append(f"{url}: {error}")
            _emit(on_event, "descargar", url, f"error: {error}")
            continue
        _emit(on_event, "descargar", url, f"{len(html):,} bytes")

        page = CapturedPage(url=url, html=html, markdown=html_to_markdown(html))
        _emit(on_event, "extraer", url, f"{len(page.markdown):,} caracteres")

        if len(page.markdown) >= MIN_DEDUPE_CHARS and page.content_hash in seen_hashes:
            report.duplicates.append(url)
            _emit(on_event, "deduplicar", url, "duplicada por hash")
            continue
        seen_hashes.add(page.content_hash)
        _emit(on_event, "deduplicar", url, "nueva")

        write_bronze(page, target_raw)
        write_silver(page, target_processed)
        title = _title_for(page)
        write_gold(page, title=title, gold_dir=target_gold)
        entries.append(index_entry(page, title))
        _emit(
            on_event, "enriquecer", url, f"sección {page.section} · {page.tokens_estimate} tokens"
        )

        report.pages.append(page)
        report.fetched += 1
        report.written += 1
        report.chars += len(page.markdown)

    write_index(entries, target_index)
    _emit(on_event, "indice", detail=f"{len(entries)} documentos indexados")
    report.duration_seconds = round(time.monotonic() - started, 2)
    return report


def _emit(hook: ProgressHook | None, stage: str, url: str = "", detail: str = "") -> None:
    """Notifica un evento de progreso si hay gancho registrado."""

    if hook is not None:
        hook(CaptureEvent(stage=stage, url=url, detail=detail))


def _title_for(page: CapturedPage) -> str:
    """Elige el mejor título disponible: ``<title>``, primer encabezado o URL."""

    title = _clean_title(html_title(page.html))
    if title:
        return title
    heading = _title_from_markdown(page.markdown)
    if len(heading) >= 8:
        return heading
    return _title_from_url(page.url)


SITE_SUFFIXES = (
    " - Carvajal S.A.",
    " | Carvajal S.A.",
    " - Carvajal",
    " | Carvajal",
    " - Organización Carvajal",
)


def _clean_title(title: str) -> str:
    """Quita el sufijo del sitio y recorta títulos desmesurados."""

    cleaned = title.strip()
    for suffix in SITE_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned[:140]


def _title_from_markdown(markdown: str) -> str:
    """Toma el primer encabezado del Markdown como título editorial."""

    for level in ("# ", "## "):
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith(level):
                return stripped[len(level) :].strip()
    return ""


def _title_from_url(url: str) -> str:
    """Deriva un título editorial simple a partir de la URL."""

    path = url.rstrip("/").rsplit("/", 1)[-1]
    return path.replace("-", " ").replace("_", " ").title() or "Home"
