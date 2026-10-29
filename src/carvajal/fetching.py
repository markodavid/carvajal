"""Cliente HTTP educado para el sitio del corpus."""

import time
from typing import Protocol
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from carvajal.config import (
    BASE_URL,
    REQUEST_DELAY_SECONDS,
    RESPECT_ROBOTS,
    TIMEOUT_SECONDS,
    USER_AGENT,
)


class Fetcher(Protocol):
    """Contrato mínimo del cliente HTTP que consume el pipeline."""

    def can_fetch(self, url: str) -> bool:
        """Indica si la URL se puede descargar."""

        ...

    def fetch(self, url: str) -> str:
        """Devuelve el HTML de la URL."""

        ...


class FetchError(RuntimeError):
    """Error al descargar una página del sitio."""


class RobotsDenied(FetchError):
    """La URL está excluida por el ``robots.txt`` del sitio."""


def normalize_robots(text: str) -> list[str]:
    """Fusiona grupos repetidos y ordena las reglas por especificidad.

    ``urllib.robotparser`` tiene dos limitaciones frente al RFC 9309: conserva solo el
    primer grupo de ``User-agent: *`` cuando el archivo lo repite, y aplica la *primera*
    regla que coincide en lugar de la coincidencia más larga. Al fusionar las reglas por
    agente y ordenarlas de ruta más larga a más corta, el resultado coincide con el
    comportamiento de los rastreadores reales.

    Args:
        text: Contenido completo del ``robots.txt``.

    Returns:
        Líneas normalizadas, un grupo por agente y separados por línea en blanco.
    """

    groups: dict[str, list[tuple[str, str]]] = {}
    others: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        directive = key.strip().lower()
        if directive == "user-agent":
            current = value.strip().lower()
            groups.setdefault(current, [])
            others.setdefault(current, [])
        elif current is None:
            continue
        elif directive in {"allow", "disallow"}:
            groups[current].append((directive, value.strip()))
        elif directive in {"crawl-delay", "request-rate"}:
            others[current].append(f"{directive}: {value.strip()}")

    lines: list[str] = []
    for agent, rules in groups.items():
        # Coincidencia más larga primero; a igual longitud, gana "allow".
        ordered = sorted(rules, key=lambda rule: (-len(rule[1]), 0 if rule[0] == "allow" else 1))
        lines.append(f"User-agent: {agent}")
        lines.extend(others[agent])
        lines.extend(f"{directive}: {path}" for directive, path in ordered)
        lines.append("")
    return lines


class WebClient:
    """Sesión única con User-Agent identificable, timeout y rate limit.

    Respeta ``robots.txt`` por host (incluido ``Crawl-delay`` si lo declara) y espera
    ``delay`` segundos entre peticiones al mismo host.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = TIMEOUT_SECONDS,
        delay: float = REQUEST_DELAY_SECONDS,
        respect_robots: bool = RESPECT_ROBOTS,
    ) -> None:
        """Inicializa la sesión HTTP con la política de contacto educado."""

        self.base_url = base_url
        self.timeout = timeout
        self.delay = delay
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}

    def can_fetch(self, url: str) -> bool:
        """Indica si ``robots.txt`` permite descargar la URL."""

        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        parser = self._robots.get(host)
        if parser is None:
            parser = self._load_robots(url)
            self._robots[host] = parser
        return parser.can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> str:
        """Descarga el contenido HTML de una URL pública.

        Args:
            url: URL absoluta o relativa a la base del sitio.

        Returns:
            HTML crudo de la respuesta.

        Raises:
            RobotsDenied: Si ``robots.txt`` excluye la URL.
            FetchError: Si la respuesta no es exitosa.
        """

        if not self.can_fetch(url):
            raise RobotsDenied(f"robots.txt excluye {url}")
        self._throttle(url)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as error:
            raise FetchError(f"{url}: {error}") from error
        return response.text

    def _load_robots(self, url: str) -> RobotFileParser:
        """Descarga, normaliza y parsea el ``robots.txt`` del host de ``url``."""

        parser = RobotFileParser()
        robots_url = urljoin(url, "/robots.txt")
        try:
            response = self.session.get(robots_url, timeout=self.timeout)
            if response.ok:
                parser.parse(normalize_robots(response.text))
            else:
                parser.parse([])
        except requests.RequestException:
            parser.parse([])
        return parser

    def _throttle(self, url: str) -> None:
        """Espera el rate limit configurado (o el ``Crawl-delay``) antes de pedir."""

        host = urlparse(url).netloc
        wait = self._delay_for(host) - (time.monotonic() - self._last_request.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _delay_for(self, host: str) -> float:
        """Combina el rate limit configurado con el ``Crawl-delay`` del robots."""

        parser = self._robots.get(host)
        crawl_delay = 0.0
        if parser is not None:
            crawl_delay = parser.crawl_delay(USER_AGENT) or 0.0
        return max(self.delay, float(crawl_delay))
