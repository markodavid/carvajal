"""Pruebas de la carga del corpus Gold (módulo ligero)."""

from pathlib import Path

from carvajal.corpus import load_gold_documents, parse_front_matter


def test_parse_front_matter_lee_clave_valor() -> None:
    """El front matter se interpreta como pares clave/valor."""

    content = "---\nurl: https://x/\ntitle: Título\nsection: prensa\n---\n\nCuerpo."

    metadata = parse_front_matter(content)

    assert metadata == {"url": "https://x/", "title": "Título", "section": "prensa"}


def test_parse_front_matter_sin_bloque_devuelve_vacio() -> None:
    """Un Markdown sin front matter no produce metadatos."""

    assert parse_front_matter("# Solo cuerpo") == {}


def test_load_gold_documents_expone_metadatos(tmp_path: Path) -> None:
    """Cada documento conserva título, dominio y tipo de fuente."""

    (tmp_path / "nota.md").write_text(
        "---\ntitle: Nota\ndomain: larepublica.co\nsource_type: tercero\n---\n\nContenido.",
        encoding="utf-8",
    )

    documents = load_gold_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].metadata["title"] == "Nota"
    assert documents[0].metadata["domain"] == "larepublica.co"
    assert documents[0].metadata["source_type"] == "tercero"
