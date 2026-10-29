"""Extracción de Markdown desde HTML crudo."""

from bs4 import BeautifulSoup, Tag

SKIPPED_TAGS = {
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "noscript",
    "svg",
    "iframe",
    "template",
}

NOISE_CLASS_HINTS = (
    "menu",
    "breadcrumb",
    "navbar",
    "site-header",
    "site-footer",
    "cookie",
    "modal",
)

NOISE_ELEMENTOR_TYPES = {"header", "footer"}

CONTENT_TAGS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "figcaption",
    "td",
    "th",
    "dt",
    "dd",
    "pre",
)


def html_title(html: str) -> str:
    """Extrae el título editorial del ``<title>`` del documento.

    Args:
        html: HTML crudo ya descargado.

    Returns:
        Título normalizado, o cadena vacía si el documento no declara uno.
    """

    soup = BeautifulSoup(html, "lxml")
    if soup.title is None or not soup.title.string:
        return ""
    return _normalize(soup.title.string)


def html_to_markdown(html: str) -> str:
    """Convierte HTML crudo a Markdown conservando el contenido editorial.

    Descarta subárboles de navegación, menús, formularios y pie de página, y emite
    solo los bloques de contenido de nivel superior para no duplicar el texto de
    los contenedores padre.

    Args:
        html: HTML crudo ya descargado (sin depender de la red).

    Returns:
        Representación Markdown legible.
    """

    soup = BeautifulSoup(html, "lxml")
    _remove_noise(soup)

    container = soup.body if soup.body is not None else soup
    blocks: list[str] = []
    seen: set[str] = set()
    for element in container.find_all(CONTENT_TAGS):
        if _has_content_ancestor(element):
            continue
        text = _normalize(element.get_text(" ", strip=True))
        if not text:
            continue
        block = _format_block(element.name, text)
        if block in seen:
            continue
        seen.add(block)
        blocks.append(block)

    return "\n\n".join(blocks)


def _remove_noise(soup: BeautifulSoup) -> None:
    """Elimina del árbol los subárboles que no son contenido editorial."""

    for element in soup.find_all(True):
        if element.decomposed:
            continue
        if element.name in SKIPPED_TAGS or _is_noise(element):
            element.decompose()


def _is_noise(element: Tag) -> bool:
    """Indica si un elemento pertenece a *chrome* del sitio (menús, banners)."""

    if element.get("data-elementor-type") in NOISE_ELEMENTOR_TYPES:
        return True
    classes = element.get("class")
    identifier = element.get("id")
    haystack = f"{classes} {identifier}".lower()
    return any(hint in haystack for hint in NOISE_CLASS_HINTS)


def _has_content_ancestor(element: Tag) -> bool:
    """Indica si el elemento ya está contenido en otro bloque de contenido."""

    return any(
        isinstance(parent, Tag) and parent.name in CONTENT_TAGS for parent in element.parents
    )


def _format_block(tag: str, text: str) -> str:
    """Da formato Markdown a un bloque de contenido según su etiqueta."""

    if tag == "h1":
        return f"# {text}"
    if tag == "h2":
        return f"## {text}"
    if tag == "h3":
        return f"### {text}"
    if tag in {"h4", "h5", "h6"}:
        return f"#### {text}"
    if tag == "li":
        return f"- {text}"
    if tag == "blockquote":
        return f"> {text}"
    if tag == "pre":
        return f"```\n{text}\n```"
    return text


def _normalize(text: str) -> str:
    """Colapsa espacios y saltos de línea sobrantes."""

    return " ".join(text.split())
