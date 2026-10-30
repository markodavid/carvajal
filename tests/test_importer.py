"""Pruebas de la importación del corpus externo a la capa extendida."""

import json
from pathlib import Path

from carvajal.importer import (
    CatalogRecord,
    import_external,
    normalize_url,
    read_catalog,
    select_records,
)

HTML = (
    "<html><body><nav>Menú</nav><h1>Historia</h1>"
    "<p>Fundada en 1904 en Cali, Colombia.</p><footer>Pie</footer></body></html>"
)


def _record(
    source_id: str,
    category: str = "identity",
    url: str = "https://www.carvajal.com/historia/",
    content_type: str = "text/html",
    pages: int = 0,
) -> dict:
    """Construye una línea de catálogo con las rutas de un corpus de prueba."""

    suffix = "pdf" if "pdf" in content_type else "html"
    return {
        "id": source_id,
        "url": url,
        "title": "Historia de Carvajal",
        "entity": "Carvajal S.A.",
        "category": category,
        "priority": 2,
        "depth": 1,
        "year": 2024,
        "date_status": "in_window",
        "fetched_at": "2026-10-23T19:46:16+00:00",
        "published_at": "",
        "content_type": content_type,
        "path": f"data/bronze/{category}/{source_id}.{suffix}",
        "text_path": f"data/silver/text/{source_id}.jsonl",
        "pages": pages,
        "estimated_tokens": 50,
        "status": "fetched",
        "text_present": True,
    }


def _build_corpus(root: Path, records: list[dict]) -> None:
    """Escribe el catálogo, el Bronze y el Silver de un corpus donante mínimo."""

    catalog = root / "data" / "gold" / "modulo_1" / "scraping_todos.jsonl"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    for record in records:
        bronze = root / str(record["path"])
        bronze.parent.mkdir(parents=True, exist_ok=True)
        if "pdf" in str(record["content_type"]):
            bronze.write_bytes(b"%PDF-1.4")
            rows = [
                {
                    "page": page,
                    "text": f"Contenido de la página {page}. " * 20,
                    "needs_ocr_review": False,
                }
                for page in range(1, int(record["pages"]) + 1)
            ]
        else:
            bronze.write_text(HTML, encoding="utf-8")
            rows = [{"page": None, "text": "Respaldo Silver.", "needs_ocr_review": False}]
        text = root / str(record["text_path"])
        text.parent.mkdir(parents=True, exist_ok=True)
        text.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )


def test_import_external_escribe_capa_extendida(tmp_path: Path) -> None:
    """La importación crea Gold, índice y manifiesto con la procedencia."""

    corpus = tmp_path / "donante"
    _build_corpus(corpus, [_record("abc123")])

    report = import_external(
        corpus,
        tmp_path / "external" / "alejandro",
        source="alejandro",
        categories=("identity",),
        min_chars=10,
        release="corpus-2026-10-23",
    )

    assert report.imported == 1
    gold = (tmp_path / "external" / "alejandro" / "gold" / "ext_abc123.md").read_text(
        encoding="utf-8"
    )
    assert "category: identity" in gold
    assert "source_type: colaborador" in gold
    assert "origin: alejandro" in gold
    assert "release: corpus-2026-10-23" in gold
    assert "layer: extended" in gold
    assert "# Historia" in gold
    assert "Menú" not in gold
    assert "Pie" not in gold

    index = (tmp_path / "external" / "alejandro" / "gold" / "index.jsonl").read_text(
        encoding="utf-8"
    )
    assert json.loads(index.splitlines()[0])["category"] == "identity"
    manifest = json.loads(
        (tmp_path / "external" / "alejandro" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["documents"] == 1
    assert manifest["by_category"] == {"identity": 1}
    assert manifest["filters"]["categories"] == ["identity"]


def test_import_external_deduplica_por_hash(tmp_path: Path) -> None:
    """Dos URLs con el mismo texto se importan una sola vez."""

    corpus = tmp_path / "donante"
    first = _record("uno", url="https://www.carvajal.com/historia/")
    second = _record("dos", url="https://www.carvajal.com/historia-espejo/")
    _build_corpus(corpus, [first, second])

    report = import_external(
        corpus,
        tmp_path / "external" / "alejandro",
        categories=("identity",),
        min_chars=10,
    )

    assert report.selected == 2
    assert report.imported == 1
    assert report.duplicates == 1


def test_import_external_filtra_por_categoria(tmp_path: Path) -> None:
    """Las categorías no solicitadas no entran a la capa extendida."""

    corpus = tmp_path / "donante"
    _build_corpus(corpus, [_record("identidad"), _record("descubrir", category="discovery")])

    report = import_external(
        corpus,
        tmp_path / "external" / "alejandro",
        categories=("identity",),
        min_chars=10,
    )

    assert report.catalog_records == 2
    assert report.selected == 1
    assert report.imported == 1


def test_import_external_excluye_pdf_por_defecto(tmp_path: Path) -> None:
    """Sin límite de páginas los PDF quedan fuera de la importación."""

    corpus = tmp_path / "donante"
    _build_corpus(
        corpus,
        [_record("pdf-1", category="financials", content_type="application/pdf", pages=2)],
    )

    report = import_external(
        corpus,
        tmp_path / "external" / "alejandro",
        categories=("financials",),
        min_chars=10,
    )

    assert report.selected == 0
    assert report.imported == 0


def test_import_external_divide_pdf_por_pagina(tmp_path: Path) -> None:
    """Con límite de páginas cada página del PDF es un documento citable."""

    corpus = tmp_path / "donante"
    _build_corpus(
        corpus,
        [_record("pdf-1", category="financials", content_type="application/pdf", pages=2)],
    )

    report = import_external(
        corpus,
        tmp_path / "external" / "alejandro",
        categories=("financials",),
        max_pages=5,
        min_chars=10,
    )

    assert report.imported == 2
    page_two = (tmp_path / "external" / "alejandro" / "gold" / "ext_pdf-1_p0002.md").read_text(
        encoding="utf-8"
    )
    assert "page: 2" in page_two
    assert "página 2" in page_two


def test_import_external_reemplaza_la_salida_anterior(tmp_path: Path) -> None:
    """Volver a importar no deja documentos de una corrida anterior."""

    corpus = tmp_path / "donante"
    _build_corpus(corpus, [_record("abc123")])
    output = tmp_path / "external" / "alejandro"
    import_external(corpus, output, categories=("identity",), min_chars=10)
    old = output / "gold" / "ext_abc123.md"
    assert old.exists()

    _build_corpus(corpus, [_record("nuevo", url="https://www.carvajal.com/nueva/")])
    import_external(corpus, output, categories=("identity",), min_chars=10)

    assert not old.exists()
    assert (output / "gold" / "ext_nuevo.md").exists()


def test_read_catalog_descarta_registros_sin_texto(tmp_path: Path) -> None:
    """El catálogo solo expone registros con texto recuperable."""

    corpus = tmp_path / "donante"
    record = _record("abc123")
    record["text_present"] = False
    _build_corpus(corpus, [record])

    assert read_catalog(corpus) == []


def test_select_records_respeta_el_presupuesto() -> None:
    """La selección no supera el máximo de documentos ni el presupuesto."""

    records = [
        CatalogRecord(
            source_id=str(index),
            url=f"https://x/{index}",
            title="T",
            category="identity",
            entity="",
            priority=1,
            depth=0,
            year="",
            date_status="",
            fetched_at="",
            published_at="",
            content_type="text/html",
            bronze_path=None,
            text_path=Path("texto.jsonl"),
            pages=0,
            estimated_chars=100,
        )
        for index in range(5)
    ]

    selected = select_records(records, categories=("identity",), max_docs=3, max_chars=250)

    assert len(selected) == 2


def test_normalize_url_iguala_variantes() -> None:
    """Las variantes de esquema, ``www`` y barra final convergen."""

    assert normalize_url("http://www.Carvajal.com/historia/") == "https://carvajal.com/historia"
    assert normalize_url("https://carvajal.com/historia#top") == "https://carvajal.com/historia"
