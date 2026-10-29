"""Entregables del corpus: capas Bronze, Silver y Gold, más el índice JSONL."""

import json
from pathlib import Path
from urllib.parse import urlparse

from carvajal.models import CapturedPage

OFFICIAL_DOMAIN = "carvajal.com"


def domain_of(url: str) -> str:
    """Devuelve el dominio de la URL sin ``www.``."""

    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_type(url: str) -> str:
    """Clasifica la fuente como ``oficial`` (sitio de Carvajal) o ``tercero``."""

    host = domain_of(url)
    return (
        "oficial" if host == OFFICIAL_DOMAIN or host.endswith(f".{OFFICIAL_DOMAIN}") else "tercero"
    )


def to_gold_markdown(page: CapturedPage, title: str) -> str:
    """Serializa la página al formato Gold: front matter + cuerpo.

    El *front matter* registra la procedencia (``domain`` y ``source_type``), la sección
    editorial, la fecha de captura y la huella ``hash`` del contenido.

    Args:
        page: Página capturada con HTML y Markdown.
        title: Título editorial de la página.

    Returns:
        Markdown listo para versionarse en ``data/gold/``.
    """

    front_matter = (
        f"---\n"
        f"url: {page.url}\n"
        f"title: {title}\n"
        f"section: {page.section}\n"
        f"domain: {page.domain}\n"
        f"source_type: {source_type(page.url)}\n"
        f"captured_at: {page.captured_at.isoformat()}\n"
        f"hash: {page.content_hash}\n"
        f"chars: {len(page.markdown)}\n"
        f"---\n"
    )
    body = page.markdown.strip()
    return f"{front_matter}\n{body}\n" if body else front_matter


def index_entry(page: CapturedPage, title: str) -> dict[str, str | int]:
    """Construye la entrada del índice JSONL del corpus."""

    return {
        "url": page.url,
        "title": title,
        "slug": page.slug,
        "section": page.section,
        "domain": page.domain,
        "source_type": source_type(page.url),
        "captured_at": page.captured_at.isoformat(),
        "hash": page.content_hash,
        "chars": len(page.markdown),
        "tokens_estimate": page.tokens_estimate,
    }


def to_jsonl(entries: list[dict[str, str | int]]) -> str:
    """Serializa las entradas del índice Gold como JSONL."""

    return "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries)


def write_bronze(page: CapturedPage, raw_dir: Path) -> Path:
    """Guarda el HTML crudo de la página en la capa Bronze."""

    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"{page.slug}.html"
    target.write_text(page.html, encoding="utf-8")
    return target


def write_silver(page: CapturedPage, processed_dir: Path) -> Path:
    """Guarda el Markdown limpio de la página en la capa Silver."""

    processed_dir.mkdir(parents=True, exist_ok=True)
    target = processed_dir / f"{page.slug}.md"
    body = page.markdown.strip()
    target.write_text(f"{body}\n" if body else "", encoding="utf-8")
    return target


def write_gold(page: CapturedPage, title: str, gold_dir: Path) -> Path:
    """Escribe el entregable Gold (Markdown + front matter) en ``gold_dir``."""

    gold_dir.mkdir(parents=True, exist_ok=True)
    markdown = to_gold_markdown(page, title)
    target = gold_dir / f"{page.slug}.md"
    target.write_text(markdown, encoding="utf-8")
    return target


def write_index(entries: list[dict[str, str | int]], index_file: Path) -> Path:
    """Escribe el índice JSONL del corpus (una línea por documento)."""

    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(to_jsonl(entries), encoding="utf-8")
    return index_file
