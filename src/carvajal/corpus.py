"""Carga del corpus Gold (núcleo + capa extendida) sin el stack de RAG."""

from pathlib import Path

from langchain_core.documents import Document

from carvajal.config import EXTERNAL_DIR, GOLD_DIR, LAYER_CORE, LAYER_EXTENDED


def load_gold_documents(
    gold_dir: Path = GOLD_DIR,
    external_dir: Path | None = EXTERNAL_DIR,
) -> list[Document]:
    """Carga el núcleo y, si existe, la capa extendida importada.

    El núcleo es el corpus curado que se consolida en el prompt. La capa extendida
    solo participa en la recuperación: cada documento conserva su procedencia
    (``origin``, ``category``, ``entity`` y ``page``) para citarlo.

    Args:
        gold_dir: Directorio del núcleo (Markdown con *front matter*).
        external_dir: Raíz de la capa extendida; ``None`` la desactiva.

    Returns:
        Lista de documentos listos para embeddear y recuperar.
    """

    documents = _load_markdown_dir(gold_dir, layer=LAYER_CORE)
    if external_dir is None or not external_dir.exists():
        return documents

    for source_dir in _external_sources(external_dir):
        documents.extend(
            _load_markdown_dir(
                source_dir / "gold",
                layer=LAYER_EXTENDED,
                origin=source_dir.name,
            )
        )
    return documents


def _external_sources(external_dir: Path) -> list[Path]:
    """Lista las fuentes importadas, ignorando restos de una importación fallida."""

    return sorted(
        path
        for path in external_dir.iterdir()
        if path.is_dir() and not path.name.endswith(".tmp") and (path / "gold").exists()
    )


def _load_markdown_dir(directory: Path, layer: str, origin: str = "") -> list[Document]:
    """Carga los Markdown de un directorio con sus metadatos de procedencia."""

    documents: list[Document] = []
    if not directory.exists():
        return documents
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        front_matter = parse_front_matter(content)
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": str(path),
                    "slug": path.stem,
                    "title": front_matter.get("title", path.stem),
                    "url": front_matter.get("url", ""),
                    "domain": front_matter.get("domain", "carvajal.com"),
                    "source_type": front_matter.get("source_type", "oficial"),
                    "category": front_matter.get("category", ""),
                    "entity": front_matter.get("entity", ""),
                    "origin": front_matter.get("origin", origin),
                    "page": front_matter.get("page", ""),
                    "published_at": front_matter.get("published_at", ""),
                    "date_status": front_matter.get("date_status", ""),
                    "layer": layer,
                },
            )
        )
    return documents


def load_core_documents(gold_dir: Path = GOLD_DIR) -> list[Document]:
    """Devuelve solo el núcleo, que es lo que entra al prompt de sistema."""

    return _load_markdown_dir(gold_dir, layer=LAYER_CORE)


def parse_front_matter(content: str) -> dict[str, str]:
    """Lee el *front matter* YAML simple del Markdown Gold (clave: valor)."""

    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) != 3:
        return {}
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            metadata[key.strip()] = value.strip()
    return metadata
