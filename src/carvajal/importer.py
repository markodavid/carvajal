"""Importación de un corpus externo al entregable Gold extendido.

El corpus donante se lee en modo solo lectura. El texto se vuelve a extraer del
HTML Bronze con el extractor propio y los PDF se toman de su texto ya extraído,
página por página. El resultado se escribe en ``data/external/<fuente>/`` con su
manifiesto, de modo que la importación sea reproducible y auditable.
"""

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from carvajal.config import (
    IMPORT_CATEGORIES,
    IMPORT_MAX_CHARS,
    IMPORT_MAX_DOC_CHARS,
    IMPORT_MAX_DOCS,
    IMPORT_MAX_PAGES,
    LAYER_EXTENDED,
)
from carvajal.extracting import html_to_markdown
from carvajal.gold import domain_of

CATALOG_FILE = Path("data") / "gold" / "modulo_1" / "scraping_todos.jsonl"
SOURCE_TYPE = "colaborador"
MIN_HTML_CHARS = 200


@dataclass(frozen=True)
class CatalogRecord:
    """Entrada del catálogo del corpus donante que apunta a texto recuperable."""

    source_id: str
    url: str
    title: str
    category: str
    entity: str
    priority: int
    depth: int
    year: str
    date_status: str
    fetched_at: str
    published_at: str
    content_type: str
    bronze_path: Path | None
    text_path: Path
    pages: int
    estimated_chars: int

    @property
    def is_pdf(self) -> bool:
        """Indica si la fuente es un PDF (su texto viene paginado)."""

        if self.content_type.startswith("application/pdf"):
            return True
        return self.bronze_path is not None and self.bronze_path.suffix.lower() == ".pdf"


@dataclass(frozen=True)
class ExternalDocument:
    """Documento listo para escribirse en la capa extendida."""

    record: CatalogRecord
    body: str
    page: int | None = None

    @property
    def slug(self) -> str:
        """Identificador estable del documento, trazable a su ``source_id``."""

        base = f"ext_{self.record.source_id}"
        return f"{base}_p{self.page:04d}" if self.page is not None else base

    @property
    def content_hash(self) -> str:
        """Huella SHA-256 del cuerpo limpio, usada para deduplicar."""

        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ImportReport:
    """Métricas de una importación del corpus externo."""

    source: str
    catalog_records: int
    selected: int
    imported: int
    duplicates: int
    empty: int
    over_budget: int
    chars: int
    duration_seconds: float

    @property
    def tokens_estimate(self) -> int:
        """Estimación de tokens del corpus importado (≈4 caracteres por token)."""

        return round(self.chars / 4)


def import_external(
    corpus_root: Path,
    output_dir: Path,
    source: str = "alejandro",
    categories: tuple[str, ...] = IMPORT_CATEGORIES,
    max_docs: int = IMPORT_MAX_DOCS,
    max_chars: int = IMPORT_MAX_CHARS,
    max_doc_chars: int = IMPORT_MAX_DOC_CHARS,
    max_pages: int = IMPORT_MAX_PAGES,
    min_chars: int = MIN_HTML_CHARS,
    release: str = "",
) -> ImportReport:
    """Importa un corpus externo a la capa extendida.

    Args:
        corpus_root: Raíz del repositorio donante (solo lectura).
        output_dir: Destino de la capa extendida (``data/external/<fuente>``).
        source: Nombre corto de la fuente, usado en ``origin`` y el manifiesto.
        categories: Categorías del catálogo donante que se quieren importar.
        max_docs: Máximo de documentos seleccionados.
        max_chars: Presupuesto de caracteres del cuerpo importado.
        max_doc_chars: Tamaño máximo estimado por documento.
        max_pages: Páginas máximas por PDF (``0`` desactiva los PDF).
        min_chars: Longitud mínima de un documento para conservarlo.
        release: Etiqueta de la captura donante (por ejemplo, ``corpus-2026-10-23``).

    Returns:
        Reporte con las métricas de la importación.
    """

    started = time.monotonic()
    records = read_catalog(corpus_root)
    selected = select_records(
        records,
        categories=categories,
        max_docs=max_docs,
        max_chars=max_chars,
        max_doc_chars=max_doc_chars,
        max_pages=max_pages,
    )
    documents, empty = _documents_for(selected, min_chars)
    kept, duplicates, over_budget = _deduplicate(documents, max_chars)

    staging = output_dir.with_name(f"{output_dir.name}.tmp")
    shutil.rmtree(staging, ignore_errors=True)
    _write_layer(
        staging,
        kept,
        source=source,
        release=release,
        filters={
            "categories": sorted(categories),
            "max_docs": max_docs,
            "max_chars": max_chars,
            "max_doc_chars": max_doc_chars,
            "max_pages": max_pages,
            "min_chars": min_chars,
        },
        corpus_root=str(corpus_root),
    )
    shutil.rmtree(output_dir, ignore_errors=True)
    staging.replace(output_dir)

    return ImportReport(
        source=source,
        catalog_records=len(records),
        selected=len(selected),
        imported=len(kept),
        duplicates=duplicates,
        empty=empty,
        over_budget=over_budget,
        chars=sum(len(document.body) for document in kept),
        duration_seconds=round(time.monotonic() - started, 2),
    )


def read_catalog(corpus_root: Path) -> list[CatalogRecord]:
    """Lee el catálogo JSONL del corpus donante y conserva lo recuperable."""

    catalog_file = corpus_root / CATALOG_FILE
    if not catalog_file.exists():
        raise FileNotFoundError(f"No se encontró el catálogo del corpus externo: {catalog_file}")

    records = [
        record
        for line in catalog_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
        if (record := _record_from_json(json.loads(line), corpus_root)) is not None
    ]
    return records


def select_records(
    records: list[CatalogRecord],
    categories: tuple[str, ...] = IMPORT_CATEGORIES,
    max_docs: int = IMPORT_MAX_DOCS,
    max_chars: int = IMPORT_MAX_CHARS,
    max_doc_chars: int = IMPORT_MAX_DOC_CHARS,
    max_pages: int = IMPORT_MAX_PAGES,
) -> list[CatalogRecord]:
    """Filtra el catálogo por categoría, tamaño y presupuesto."""

    allowed = {category.lower() for category in categories}
    candidates = [
        record
        for record in records
        if record.category in allowed
        and record.estimated_chars <= max_doc_chars
        and _within_page_limit(record, max_pages)
    ]
    candidates.sort(key=_selection_order)

    selected: list[CatalogRecord] = []
    estimated_total = 0
    for record in candidates:
        if len(selected) >= max_docs:
            break
        if selected and estimated_total + record.estimated_chars > max_chars:
            continue
        selected.append(record)
        estimated_total += record.estimated_chars
    return selected


def _record_from_json(raw: dict, corpus_root: Path) -> CatalogRecord | None:
    """Convierte una línea del catálogo en registro, o ``None`` si no es usable."""

    if raw.get("status") != "fetched" or not raw.get("text_present"):
        return None
    text_path = _resolve_path(raw.get("text_path"), corpus_root)
    if text_path is None or not text_path.exists():
        return None

    return CatalogRecord(
        source_id=str(raw.get("id", "")),
        url=str(raw.get("url", "")),
        title=str(raw.get("title") or ""),
        category=str(raw.get("category") or "sin_categoria"),
        entity=str(raw.get("entity") or ""),
        priority=_as_int(raw.get("priority"), default=99),
        depth=_as_int(raw.get("depth"), default=99),
        year=str(raw.get("year") or ""),
        date_status=str(raw.get("date_status") or ""),
        fetched_at=str(raw.get("fetched_at") or ""),
        published_at=str(raw.get("published_at") or ""),
        content_type=str(raw.get("content_type") or ""),
        bronze_path=_resolve_path(raw.get("path"), corpus_root),
        text_path=text_path,
        pages=_as_int(raw.get("pages"), default=0),
        estimated_chars=_as_int(raw.get("estimated_tokens"), default=0) * 4,
    )


def _resolve_path(value: object, corpus_root: Path) -> Path | None:
    """Resuelve una ruta del catálogo contra la raíz del corpus donante."""

    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else corpus_root / path


def _as_int(value: object, default: int) -> int:
    """Convierte un valor del catálogo a entero sin romper con datos incompletos."""

    if isinstance(value, bool):
        return default
    if isinstance(value, int | float | str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _within_page_limit(record: CatalogRecord, max_pages: int) -> bool:
    """Indica si el registro cabe en el límite de páginas para PDF."""

    if not record.is_pdf:
        return True
    if max_pages <= 0:
        return False
    return record.pages <= max_pages


def _selection_order(record: CatalogRecord) -> tuple[int, int, int, str]:
    """Ordena candidatos por prioridad, profundidad y año más reciente."""

    return (record.priority, record.depth, -_as_int(record.year, default=0), record.url)


def _documents_for(
    records: list[CatalogRecord], min_chars: int
) -> tuple[list[ExternalDocument], int]:
    """Construye los documentos de los registros y cuenta los que quedan vacíos."""

    documents: list[ExternalDocument] = []
    empty = 0
    for record in records:
        record_documents = _pdf_documents(record) if record.is_pdf else _html_documents(record)
        record_documents = [
            document for document in record_documents if len(document.body) >= min_chars
        ]
        if record_documents:
            documents.extend(record_documents)
        else:
            empty += 1
    return documents, empty


def _html_documents(record: CatalogRecord) -> list[ExternalDocument]:
    """Extrae una página HTML con el extractor propio, con respaldo al Silver."""

    body = _html_body(record) or _silver_body(record)
    return [ExternalDocument(record=record, body=body)] if body else []


def _html_body(record: CatalogRecord) -> str:
    """Convierte el HTML Bronze en Markdown limpio."""

    if record.bronze_path is None or not record.bronze_path.exists():
        return ""
    try:
        html = record.bronze_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return html_to_markdown(html).strip()


def _silver_body(record: CatalogRecord) -> str:
    """Concatena el texto Silver del registro como respaldo."""

    return "\n\n".join(_read_text_rows(record.text_path)).strip()


def _pdf_documents(record: CatalogRecord) -> list[ExternalDocument]:
    """Devuelve un documento por página de PDF, con su número de página."""

    rows = _read_jsonl(record.text_path)
    documents: list[ExternalDocument] = []
    for position, row in enumerate(rows, start=1):
        body = str(row.get("text") or "").strip()
        if not body:
            continue
        page = _as_int(row.get("page"), default=position)
        documents.append(ExternalDocument(record=record, body=body, page=page))
    return documents


def _read_text_rows(path: Path) -> list[str]:
    """Lee las filas de texto de un JSONL del corpus donante."""

    return [str(row.get("text") or "").strip() for row in _read_jsonl(path)]


def _read_jsonl(path: Path) -> list[dict]:
    """Lee un JSONL y descarta las líneas vacías o inválidas."""

    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _deduplicate(
    documents: list[ExternalDocument], max_chars: int
) -> tuple[list[ExternalDocument], int, int]:
    """Quita duplicados por hash/URL y respeta el presupuesto de caracteres."""

    seen_hashes: set[str] = set()
    seen_urls: set[tuple[str, int | None]] = set()
    kept: list[ExternalDocument] = []
    chars = 0
    duplicates = 0
    over_budget = 0

    for document in documents:
        url_key = (normalize_url(document.record.url), document.page)
        if document.content_hash in seen_hashes or url_key in seen_urls:
            duplicates += 1
            continue
        if kept and chars + len(document.body) > max_chars:
            over_budget += 1
            continue
        seen_hashes.add(document.content_hash)
        seen_urls.add(url_key)
        kept.append(document)
        chars += len(document.body)

    return kept, duplicates, over_budget


def normalize_url(url: str) -> str:
    """Normaliza una URL para comparar duplicados entre corpus."""

    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


def _write_layer(
    output_dir: Path,
    documents: list[ExternalDocument],
    source: str,
    release: str,
    filters: dict[str, object],
    corpus_root: str,
) -> None:
    """Escribe las capas Silver/Gold, el índice y el manifiesto de la importación."""

    silver_dir = output_dir / "silver"
    gold_dir = output_dir / "gold"
    silver_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str | int]] = []
    for document in documents:
        (silver_dir / f"{document.slug}.md").write_text(f"{document.body}\n", encoding="utf-8")
        markdown = _to_markdown(document, source=source, release=release)
        (gold_dir / f"{document.slug}.md").write_text(markdown, encoding="utf-8")
        entries.append(_index_entry(document, source=source, release=release))

    (gold_dir / "index.jsonl").write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            _manifest(
                documents,
                source=source,
                release=release,
                filters=filters,
                corpus_root=corpus_root,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _to_markdown(document: ExternalDocument, source: str, release: str) -> str:
    """Serializa un documento externo con su *front matter* de procedencia."""

    record = document.record
    front_matter = (
        f"---\n"
        f"url: {record.url}\n"
        f"title: {_title_for(record, document.body)}\n"
        f"section: {_section_for(record)}\n"
        f"domain: {domain_of(record.url)}\n"
        f"source_type: {SOURCE_TYPE}\n"
        f"category: {record.category}\n"
        f"entity: {record.entity}\n"
        f"origin: {source}\n"
        f"release: {release}\n"
        f"captured_at: {record.fetched_at}\n"
        f"published_at: {record.published_at}\n"
        f"date_status: {record.date_status}\n"
        f"page: {document.page if document.page is not None else ''}\n"
        f"pages: {record.pages}\n"
        f"hash: {document.content_hash}\n"
        f"chars: {len(document.body)}\n"
        f"layer: {LAYER_EXTENDED}\n"
        f"---\n"
    )
    return f"{front_matter}\n{document.body.strip()}\n"


def _index_entry(document: ExternalDocument, source: str, release: str) -> dict[str, str | int]:
    """Construye la entrada del índice JSONL de la capa extendida."""

    record = document.record
    return {
        "url": record.url,
        "title": _title_for(record, document.body),
        "slug": document.slug,
        "section": _section_for(record),
        "domain": domain_of(record.url),
        "source_type": SOURCE_TYPE,
        "category": record.category,
        "entity": record.entity,
        "origin": source,
        "release": release,
        "page": document.page if document.page is not None else "",
        "captured_at": record.fetched_at,
        "hash": document.content_hash,
        "chars": len(document.body),
        "tokens_estimate": max(1, round(len(document.body) / 4)),
        "layer": LAYER_EXTENDED,
    }


def _manifest(
    documents: list[ExternalDocument],
    source: str,
    release: str,
    filters: dict[str, object],
    corpus_root: str,
) -> dict[str, object]:
    """Resume la importación para auditar qué entró y con qué filtros."""

    by_category: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for document in documents:
        by_category[document.record.category] = by_category.get(document.record.category, 0) + 1
        domain = domain_of(document.record.url)
        by_domain[domain] = by_domain.get(domain, 0) + 1

    chars = sum(len(document.body) for document in documents)
    return {
        "schema_version": 1,
        "source": source,
        "release": release,
        "corpus_root": corpus_root,
        "generated_at": datetime.now(UTC).isoformat(),
        "filters": filters,
        "documents": len(documents),
        "chars": chars,
        "tokens_estimate": round(chars / 4),
        "by_category": dict(sorted(by_category.items())),
        "by_domain": dict(sorted(by_domain.items())),
    }


TITLE_SUFFIXES = (
    " - Carvajal S.A.",
    " | Carvajal S.A.",
    " - Carvajal",
    " | Carvajal",
    " - Organización Carvajal",
)


def _title_for(record: CatalogRecord, body: str) -> str:
    """Elige un título útil, evitando etiquetas genéricas del catálogo."""

    title = _clean_title(record.title)
    if len(title) >= 8 and title.lower() not in {"descargar pdf", "ver más", "pdf"}:
        return title
    for line in body.splitlines():
        if line.strip():
            return line.strip()[:140]
    return record.url.rstrip("/").rsplit("/", 1)[-1] or "Documento externo"


def _clean_title(title: str) -> str:
    """Colapsa espacios y quita el sufijo del sitio, como en el núcleo."""

    cleaned = " ".join(title.split())
    for suffix in TITLE_SUFFIXES:
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)].strip()[:140]
    return cleaned[:140]


def _section_for(record: CatalogRecord) -> str:
    """Usa la sección de la URL en el sitio oficial y la categoría fuera de él."""

    if domain_of(record.url) == "carvajal.com":
        segments = [segment for segment in urlsplit(record.url).path.split("/") if segment]
        return segments[0] if segments else "home"
    return record.category
