"""Carga del corpus Gold (módulo ligero, sin el stack de RAG)."""

from pathlib import Path

from langchain_core.documents import Document

from carvajal.config import GOLD_DIR


def load_gold_documents(gold_dir: Path = GOLD_DIR) -> list[Document]:
    """Carga los entregables Gold (Markdown con *front matter*) como documentos.

    Se mantiene separado de :mod:`carvajal.rag` para que la interfaz pueda listar el
    corpus sin pagar el coste de importar ``langchain``, ``faiss`` y los clientes de LLM.

    Args:
        gold_dir: Directorio con los Markdown del corpus.

    Returns:
        Lista de documentos listos para embeddear y recuperar.
    """

    documents: list[Document] = []
    if not gold_dir.exists():
        return documents
    for path in sorted(gold_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        front_matter = parse_front_matter(content)
        metadata = {
            "source": str(path),
            "slug": path.stem,
            "title": front_matter.get("title", path.stem),
            "domain": front_matter.get("domain", "carvajal.com"),
            "source_type": front_matter.get("source_type", "oficial"),
        }
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


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
