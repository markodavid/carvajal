"""Pruebas del pipeline: capas Bronze/Silver/Gold, deduplicación y métricas."""

import json
from pathlib import Path

from carvajal.fetching import FetchError
from carvajal.pipeline import capture

HISTORIA = "https://www.carvajal.com/historia/"
EMPAQUES = "https://www.carvajal.com/empaques/"
NOTA = "https://www.larepublica.co/empresas/nota"

HTML_HISTORIA = "<html><body><h1>Historia</h1><p>Fundada en 1904 en Cali.</p></body></html>"
HTML_EMPAQUES = "<html><body><h1>Empaques</h1><p>Soluciones de empaque.</p></body></html>"
HTML_NOTA = "<html><body><h1>Resultados</h1><p>Ingresos por 3,9 billones.</p></body></html>"


class FakeClient:
    """Cliente HTTP de prueba con páginas en memoria."""

    def __init__(self, pages: dict[str, str], denied: set[str] | None = None) -> None:
        self.pages = pages
        self.denied = denied or set()
        self.fetched: list[str] = []

    def can_fetch(self, url: str) -> bool:
        return url not in self.denied

    def fetch(self, url: str) -> str:
        if url not in self.pages:
            raise FetchError(f"404 en {url}")
        self.fetched.append(url)
        return self.pages[url]


def _capture(tmp_path: Path, client: FakeClient, seeds: list[str]):
    """Ejecuta el pipeline contra directorios temporales."""

    return capture(
        seeds,
        client=client,
        gold_dir=tmp_path / "gold",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        index_file=tmp_path / "gold" / "index.jsonl",
    )


def test_capture_escribe_las_tres_capas(tmp_path: Path) -> None:
    """Cada página queda en Bronze (HTML), Silver (Markdown) y Gold (front matter)."""

    client = FakeClient({HISTORIA: HTML_HISTORIA})
    report = _capture(tmp_path, client, [HISTORIA])

    assert (tmp_path / "raw" / "historia.html").read_text(encoding="utf-8") == HTML_HISTORIA
    silver = (tmp_path / "processed" / "historia.md").read_text(encoding="utf-8")
    assert "Fundada en 1904" in silver
    assert "---" not in silver

    gold = (tmp_path / "gold" / "historia.md").read_text(encoding="utf-8")
    assert gold.startswith("---")
    assert "title: Historia" in gold
    assert "section: historia" in gold
    assert "source_type: oficial" in gold
    assert "hash: " in gold

    assert report.discovered == 1
    assert report.fetched == 1
    assert report.written == 1
    assert report.discarded == 0
    assert report.chars > 0


def test_capture_genera_indice_jsonl(tmp_path: Path) -> None:
    """El índice JSONL registra URL, sección, hash y tamaño de cada documento."""

    client = FakeClient({HISTORIA: HTML_HISTORIA, NOTA: HTML_NOTA})
    _capture(tmp_path, client, [HISTORIA, NOTA])

    lines = (tmp_path / "gold" / "index.jsonl").read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]

    assert len(entries) == 2
    assert {entry["url"] for entry in entries} == {HISTORIA, NOTA}
    assert entries[1]["source_type"] == "tercero"
    assert entries[1]["section"] == "prensa"
    assert all(len(entry["hash"]) == 64 for entry in entries)
    assert all(entry["tokens_estimate"] > 0 for entry in entries)


def test_capture_descarta_duplicados_por_hash(tmp_path: Path) -> None:
    """Dos URLs con el mismo contenido escrito solo se guardan una vez."""

    mismo_html = "<html><body><p>" + ("Contenido idéntico. " * 20) + "</p></body></html>"
    client = FakeClient({HISTORIA: mismo_html, EMPAQUES: mismo_html})

    report = _capture(tmp_path, client, [HISTORIA, EMPAQUES])

    assert report.written == 1
    assert report.duplicates == [EMPAQUES]
    assert len(list((tmp_path / "gold").glob("*.md"))) == 1


def test_capture_respeta_robots_y_registra_errores(tmp_path: Path) -> None:
    """Las URLs excluidas y las que fallan se cuentan sin romper la captura."""

    client = FakeClient({HISTORIA: HTML_HISTORIA}, denied={EMPAQUES})
    report = _capture(tmp_path, client, [HISTORIA, EMPAQUES, NOTA])

    assert report.discovered == 3
    assert report.written == 1
    assert report.robots_denied == [EMPAQUES]
    assert len(report.errors) == 1
    assert report.discarded == 2
