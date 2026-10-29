"""Modelos del dominio del corpus web."""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

OFFICIAL_DOMAIN = "carvajal.com"


@dataclass(frozen=True)
class CapturedPage:
    """Página pública capturada del sitio, con su Markdown listo para curar."""

    url: str
    html: str
    markdown: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def slug(self) -> str:
        """Devuelve el slug legible de la página para el entregable Gold."""

        path = urlparse(self.url).path.strip("/")
        segment = path.rsplit("/", 1)[-1] if path else "home"
        segment = segment.replace("-", "_").replace(".", "")
        return segment or "home"

    @property
    def domain(self) -> str:
        """Dominio de la página, sin el prefijo ``www.``."""

        host = urlparse(self.url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    @property
    def is_official(self) -> bool:
        """Indica si la página pertenece al sitio oficial de Carvajal."""

        return self.domain == OFFICIAL_DOMAIN or self.domain.endswith(f".{OFFICIAL_DOMAIN}")

    @property
    def section(self) -> str:
        """Sección editorial derivada de la URL.

        En el sitio oficial es el primer segmento de la ruta (``inversionistas``,
        ``quienes-somos``…) y ``home`` para la portada. En fuentes de terceros la
        sección es ``prensa``: el medio se conserva aparte, en ``domain``.
        """

        if not self.is_official:
            return "prensa"
        segments = [segment for segment in urlparse(self.url).path.split("/") if segment]
        return segments[0] if segments else "home"

    @property
    def content_hash(self) -> str:
        """Huella SHA-256 del Markdown, usada para deduplicar el corpus."""

        return hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()

    @property
    def tokens_estimate(self) -> int:
        """Estimación burda de tokens (≈4 caracteres por token)."""

        return max(1, round(len(self.markdown) / 4))
