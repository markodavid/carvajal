"""Pruebas del entregable Gold (front matter y procedencia)."""

from pathlib import Path

from carvajal.gold import domain_of, source_type, to_gold_markdown, write_gold
from carvajal.models import CapturedPage


def _page(url: str) -> CapturedPage:
    """Construye una página capturada mínima para las pruebas."""

    return CapturedPage(url=url, html="<p>hola</p>", markdown="# Título\n\nCuerpo.")


def test_domain_of_quita_www() -> None:
    """El dominio se registra sin el prefijo ``www.``."""

    assert domain_of("https://www.carvajal.com/historia/") == "carvajal.com"


def test_source_type_distingue_oficial_de_tercero() -> None:
    """Solo el dominio de Carvajal se considera fuente oficial."""

    assert source_type("https://www.carvajal.com/historia/") == "oficial"
    assert source_type("https://www.larepublica.co/empresas/nota-4099828") == "tercero"
    assert source_type("https://carvajal.com.co/otro") == "tercero"


def test_to_gold_markdown_registra_procedencia() -> None:
    """El front matter incluye dominio y tipo de fuente junto a los metadatos base."""

    markdown = to_gold_markdown(_page("https://www.larepublica.co/empresas/nota"), "Nota")

    assert "url: https://www.larepublica.co/empresas/nota" in markdown
    assert "domain: larepublica.co" in markdown
    assert "source_type: tercero" in markdown
    assert "captured_at:" in markdown
    assert markdown.rstrip().endswith("Cuerpo.")


def test_to_gold_markdown_incluye_seccion_hash_y_tamano() -> None:
    """El front matter añade sección editorial, huella y número de caracteres."""

    page = _page("https://www.carvajal.com/inversionistas/inicio/")

    markdown = to_gold_markdown(page, "Inicio")

    assert "section: inversionistas" in markdown
    assert f"hash: {page.content_hash}" in markdown
    assert f"chars: {len(page.markdown)}" in markdown


def test_section_de_terceros_es_prensa() -> None:
    """Las fuentes externas se agrupan en la sección ``prensa``."""

    assert _page("https://www.elpais.com.co/economia/nota-0239.html").section == "prensa"
    assert _page("https://www.carvajal.com/").section == "home"


def test_to_gold_markdown_pagina_vacia_termina_en_un_salto() -> None:
    """Una página sin cuerpo no deja una línea en blanco al final del archivo."""

    page = CapturedPage(
        url="https://www.carvajal.com/sostenibilidad/",
        html="<html></html>",
        markdown="",
    )

    markdown = to_gold_markdown(page, "Sostenibilidad")

    assert markdown.endswith("---\n")
    assert not markdown.endswith("\n\n")


def test_write_gold_pagina_vacia_no_deja_linea_en_blanco(tmp_path: Path) -> None:
    """El archivo Gold escrito para una página vacía acaba en un único salto."""

    page = CapturedPage(url="https://www.carvajal.com/sostenibilidad/", html="", markdown="")

    target = write_gold(page, title="Sostenibilidad", gold_dir=tmp_path)

    assert target.read_text(encoding="utf-8").endswith("---\n")
