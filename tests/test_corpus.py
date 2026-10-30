"""Pruebas de la carga del corpus Gold (módulo ligero)."""

from pathlib import Path

from carvajal.corpus import load_core_documents, load_gold_documents, parse_front_matter


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

    documents = load_gold_documents(tmp_path, include_extended=False)

    assert len(documents) == 1
    assert documents[0].metadata["title"] == "Nota"
    assert documents[0].metadata["domain"] == "larepublica.co"
    assert documents[0].metadata["source_type"] == "tercero"
    assert documents[0].metadata["layer"] == "core"


def test_load_gold_documents_mezcla_nucleo_y_capa_extendida(tmp_path: Path) -> None:
    """El núcleo y la capa extendida conviven con su procedencia y capa."""

    core_dir = tmp_path / "gold"
    external_dir = tmp_path / "external"
    (core_dir).mkdir()
    (external_dir / "alejandro" / "gold").mkdir(parents=True)
    (core_dir / "historia.md").write_text(
        "---\ntitle: Historia\ndomain: carvajal.com\nsource_type: oficial\n---\n\nNúcleo.",
        encoding="utf-8",
    )
    (external_dir / "alejandro" / "gold" / "ext_abc.md").write_text(
        "---\ntitle: Empaques\nurl: https://carvajalempaques.com/\n"
        "domain: carvajalempaques.com\nsource_type: colaborador\n"
        "category: business\nentity: Carvajal Empaques\norigin: alejandro\n"
        "page: 3\nlayer: extended\n---\n\nCapa extendida.",
        encoding="utf-8",
    )

    documents = load_gold_documents(core_dir, external_dir, include_extended=True)
    by_layer = {document.metadata["layer"]: document for document in documents}

    assert len(documents) == 2
    assert by_layer["core"].metadata["title"] == "Historia"
    extended = by_layer["extended"]
    assert extended.metadata["origin"] == "alejandro"
    assert extended.metadata["category"] == "business"
    assert extended.metadata["entity"] == "Carvajal Empaques"
    assert extended.metadata["page"] == "3"


def test_load_core_documents_omite_la_capa_extendida(tmp_path: Path) -> None:
    """El prompt solo recibe el núcleo curado."""

    (tmp_path / "gold").mkdir()
    (tmp_path / "external" / "alejandro" / "gold").mkdir(parents=True)
    (tmp_path / "gold" / "historia.md").write_text(
        "---\ntitle: Historia\n---\n\nNúcleo.", encoding="utf-8"
    )
    (tmp_path / "external" / "alejandro" / "gold" / "ext_abc.md").write_text(
        "---\ntitle: Externo\nlayer: extended\n---\n\nExtendido.", encoding="utf-8"
    )

    documents = load_core_documents(tmp_path / "gold")

    assert len(documents) == 1
    assert documents[0].metadata["slug"] == "historia"


def test_capa_extendida_desactivada_por_defecto(tmp_path: Path) -> None:
    """Sin activarla, `load_gold_documents` devuelve solo el núcleo."""

    (tmp_path / "gold").mkdir()
    (tmp_path / "external" / "alejandro" / "gold").mkdir(parents=True)
    (tmp_path / "gold" / "historia.md").write_text(
        "---\ntitle: Historia\n---\n\nNúcleo.", encoding="utf-8"
    )
    (tmp_path / "external" / "alejandro" / "gold" / "ext_abc.md").write_text(
        "---\ntitle: Externo\n---\n\nExtendido.", encoding="utf-8"
    )

    documents = load_gold_documents(tmp_path / "gold", tmp_path / "external")

    assert [document.metadata["slug"] for document in documents] == ["historia"]
