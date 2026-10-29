"""Pruebas de la interfaz de línea de comandos."""

from carvajal.cli import build_parser


def test_parser_lista_subcomandos_validos() -> None:
    """El parser reconoce los subcomandos definidos."""

    parser = build_parser()

    assert parser.parse_args(["list"]) is not None
    assert parser.parse_args(["status"]) is not None


def test_parser_reconoce_las_tareas_de_llm() -> None:
    """Los subcomandos de Resumen y FAQ existen y aceptan su salida."""

    parser = build_parser()

    resumen = parser.parse_args(["summarize", "--focus", "empaques"])
    faq = parser.parse_args(["faq"])

    assert resumen.command == "summarize"
    assert resumen.focus == "empaques"
    assert faq.command == "faq"
    assert faq.output.name == "faq.md"
