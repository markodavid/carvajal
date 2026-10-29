"""Pruebas del cliente HTTP: robots.txt y rate limit."""

from urllib.robotparser import RobotFileParser

import pytest

from carvajal.config import USER_AGENT
from carvajal.fetching import RobotsDenied, WebClient, normalize_robots


def _parser(*lines: str) -> RobotFileParser:
    """Construye un robots.txt en memoria."""

    parser = RobotFileParser()
    parser.parse(list(lines))
    return parser


def test_can_fetch_permite_rutas_publicas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una ruta no excluida por robots.txt se puede descargar."""

    client = WebClient(delay=0.0)
    parser = _parser("User-agent: *", "Disallow: /privado")
    monkeypatch.setattr(client, "_load_robots", lambda url: parser)

    assert client.can_fetch("https://www.carvajal.com/historia/") is True


def test_can_fetch_bloquea_rutas_excluidas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una ruta con Disallow queda bloqueada."""

    client = WebClient(delay=0.0)
    parser = _parser("User-agent: *", "Disallow: /privado")
    monkeypatch.setattr(client, "_load_robots", lambda url: parser)

    assert client.can_fetch("https://www.carvajal.com/privado/secreto") is False


def test_fetch_lanza_robots_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """``fetch`` no descarga URLs excluidas y avisa con un error tipado."""

    client = WebClient(delay=0.0)
    parser = _parser("User-agent: *", "Disallow: /privado")
    monkeypatch.setattr(client, "_load_robots", lambda url: parser)

    with pytest.raises(RobotsDenied):
        client.fetch("https://www.carvajal.com/privado/secreto")


def test_ignore_robots_permite_todo() -> None:
    """Con ``respect_robots=False`` no se consulta robots.txt."""

    client = WebClient(respect_robots=False)

    assert client.can_fetch("https://www.carvajal.com/cualquier/ruta") is True


def test_throttle_espera_el_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """La primera petición a un host espera el rate limit configurado."""

    client = WebClient(delay=1.0, respect_robots=False)
    slept: list[float] = []
    monkeypatch.setattr("carvajal.fetching.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr("carvajal.fetching.time.monotonic", lambda: 0.0)

    client._throttle("https://www.carvajal.com/historia/")

    assert slept == [1.0]


def test_throttle_respeta_crawl_delay_del_robots() -> None:
    """Si el robots.txt declara un Crawl-delay mayor, se usa ese valor."""

    client = WebClient(delay=0.5, respect_robots=False)
    client._robots["www.carvajal.com"] = _parser(
        "User-agent: *", "Crawl-delay: 3", "Disallow: /privado"
    )

    assert client._delay_for("www.carvajal.com") == 3.0


def test_normalize_robots_fusiona_grupos_repetidos() -> None:
    """Un robots.txt con dos grupos ``User-agent: *`` conserva todas sus reglas.

    Es el patrón real de larepublica.co: ``Allow: /`` en un grupo y los ``Disallow``
    en otro. Sin normalizar, ``urllib.robotparser`` descarta el segundo grupo.
    """

    text = "User-agent: *\nAllow: /\nUser-agent: *\nDisallow: /vista-previa/\n"
    parser = RobotFileParser()
    parser.parse(normalize_robots(text))

    assert parser.can_fetch(USER_AGENT, "https://x.com/empresas/nota") is True
    assert parser.can_fetch(USER_AGENT, "https://x.com/vista-previa/nota") is False


def test_normalize_robots_aplica_la_coincidencia_mas_larga() -> None:
    """Gana la regla de ruta más específica, como exige el RFC 9309."""

    text = "User-agent: *\nAllow: /empresas/\nDisallow: /empresas/privado\n"
    parser = RobotFileParser()
    parser.parse(normalize_robots(text))

    assert parser.can_fetch(USER_AGENT, "https://x.com/empresas/nota") is True
    assert parser.can_fetch(USER_AGENT, "https://x.com/empresas/privado/x") is False
